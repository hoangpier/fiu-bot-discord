# main.py (Phiên bản Nâng Cấp - Trình đọc ảnh chính xác cao)

import discord
from discord.ext import commands
import os
import re
import requests
import io
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from dotenv import load_dotenv
import threading
from flask import Flask
import asyncio

# --- PHẦN 1: CẤU HÌNH WEB SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    """Trang chủ đơn giản để hiển thị bot đang hoạt động."""
    return "Bot Discord đang hoạt động."

def run_web_server():
    """Chạy web server Flask trên cổng được cấu hình."""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# --- PHẦN 2: CẤU HÌNH VÀ CÁC HÀM CỦA BOT DISCORD ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
KARUTA_ID = 646937666251915264
NEW_CHARACTERS_FILE = "new_characters.txt"
HEART_DATABASE_FILE = "tennhanvatvasotim.txt"

def load_heart_data(file_path):
    """
    Tải dữ liệu số tim của nhân vật từ một file.
    Dữ liệu được lưu trữ trong một dictionary (cơ sở dữ liệu trong bộ nhớ).
    """
    heart_db = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('♡') or not line:
                    continue
                parts = line.split('·')
                if len(parts) >= 2:
                    try:
                        heart_str = parts[0].replace('♡', '').replace(',', '').strip()
                        hearts = int(heart_str)
                        name = parts[-1].lower().strip()
                        if name:
                            heart_db[name] = hearts
                    except (ValueError, IndexError):
                        continue
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy tệp dữ liệu '{file_path}'.")
    except Exception as e:
        print(f"Lỗi khi đọc tệp dữ liệu: {e}")
    print(f"✅ Đã tải thành công {len(heart_db)} nhân vật vào cơ sở dữ liệu số tim.")
    return heart_db

HEART_DATABASE = load_heart_data(HEART_DATABASE_FILE)

def log_new_character(character_name):
    """
    Ghi lại tên nhân vật mới chưa có trong cơ sở dữ liệu số tim vào một file.
    Đảm bảo không ghi trùng lặp tên.
    """
    try:
        existing_names = set()
        if os.path.exists(NEW_CHARACTERS_FILE):
            with open(NEW_CHARACTERS_FILE, 'r', encoding='utf-8') as f:
                existing_names = set(line.strip().lower() for line in f)
        
        if character_name and character_name.lower() not in existing_names:
            with open(NEW_CHARACTERS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{character_name}\n")
            print(f"  [LOG] ⭐ Đã lưu nhân vật mới '{character_name}' vào file {NEW_CHARACTERS_FILE}")
    except Exception as e:
        print(f"Lỗi khi đang lưu nhân vật mới: {e}")

def get_names_from_image_upgraded(image_bytes):
    """
    Hàm đọc ảnh được nâng cấp với kỹ thuật cắt ảnh chính xác và tiền xử lý ảnh
    cải tiến để tăng độ chính xác của OCR.
    """
    try:
        main_image = Image.open(io.BytesIO(image_bytes))
        width, height = main_image.size

        if not (width > 800 and height > 200):
            print(f"  [LOG] Kích thước ảnh không giống ảnh drop Karuta: {width}x{height}. Bỏ qua.")
            return []

        card_width = 278
        card_height = 248
        x_coords = [0, 279, 558] 

        extracted_names = []
        
        # Cấu hình Tesseract OCR:
        # --psm 7: Treat the image as a single text line. Rất phù hợp với vùng tên đã được cắt.
        # --oem 3: Sử dụng cả công cụ OCR cũ và mới.
        custom_config = r'--psm 7 --oem 3' 

        for i in range(3):
            card_box = (x_coords[i], 0, x_coords[i] + card_width, card_height)
            card_img = main_image.crop(card_box)

            # Điều chỉnh tọa độ cắt vùng tên nhân vật theo docanh.py
            name_box = (15, 15, card_width - 15, 50) # Chiều cao vùng cắt tên là 50 (từ y=15 đến y=50)
            name_img = card_img.crop(name_box)

            # Tiền xử lý ảnh đơn giản hóa: chỉ chuyển sang xám, tăng tương phản và làm sắc nét
            name_img = name_img.convert('L') # 1. Chuyển sang ảnh xám
            
            # 2. Tăng độ tương phản (có thể thử các giá trị khác như 2.0, 2.5)
            enhancer = ImageEnhance.Contrast(name_img)
            name_img = enhancer.enhance(2.0) # Quay lại mức tương phản 2.0

            # 3. Làm sắc nét 2 lần
            name_img = name_img.filter(ImageFilter.SHARPEN)
            name_img = name_img.filter(ImageFilter.SHARPEN)
            
            # Gỡ bỏ các bước đảo màu và nhị phân hóa cứng nhắc, để Tesseract xử lý ảnh xám đã làm rõ.
            # >>>>> DÒNG DEBUG MỚI ĐƯỢC THÊM VÀO ĐÂY <<<<<
            # Đảm bảo thư mục 'debug_images' tồn tại
            os.makedirs("debug_images", exist_ok=True)
            name_img.save(f"debug_images/debug_card_name_{i}.png") # Lưu ảnh sau tiền xử lý để kiểm tra
            print(f"  [DEBUG] Đã lưu ảnh thẻ {i} sau tiền xử lý tại debug_images/debug_card_name_{i}.png")
            # >>>>> KẾT THÚC DÒNG DEBUG <<<<<


            text = pytesseract.image_to_string(name_img, config=custom_config)
            
            # Hậu xử lý tên:
            cleaned_name = text.strip().replace("\n", " ").replace(" ", " ") # Chuẩn hóa khoảng trắng
            
            # Loại bỏ các ký tự không phải chữ cái (a-z, A-Z), số (0-9), khoảng trắng, dấu nháy đơn hoặc dấu gạch nối
            cleaned_name = re.sub(r'[^a-zA-Z0-9\s\'-]', '', cleaned_name) # Cho phép cả dấu nháy đơn ' và dấu gạch nối -
            
            # Thêm một bước làm sạch nữa: loại bỏ các chuỗi ký tự đơn lẻ hoặc rất ngắn
            # thường là nhiễu nếu đứng một mình
            words = cleaned_name.split()
            filtered_words = [word for word in words if len(word) > 1 or word.lower() in ['a', 'i', 'o', 'of', 'the', 's', 'ii']] # Giữ lại các từ ngắn có nghĩa phổ biến và 'ii'
            cleaned_name = " ".join(filtered_words)

            # Xử lý các trường hợp đặc biệt thường bị đọc sai (có thể bổ sung thêm khi gặp lỗi mới)
            cleaned_name = cleaned_name.replace("Miog", "Mio")
            # Ví dụ: nếu "Genocide" bị đọc sai (ví dụ Genocde), có thể thêm:
            # cleaned_name = cleaned_name.replace("Genocde", "Genocide")


            if len(cleaned_name) > 1 and not all(char.isspace() for char in cleaned_name):
                extracted_names.append(cleaned_name)
            else:
                extracted_names.append("Không đọc được")

        return extracted_names
    except Exception as e:
        print(f"  [LỖI] Xảy ra lỗi trong quá trình xử lý ảnh: {e}")
        return ["Lỗi OCR (Thẻ 1)", "Lỗi OCR (Thẻ 2)", "Lỗi OCR (Thẻ 3)"]

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command()
async def ping(ctx):
    """Lệnh ping đơn giản để kiểm tra bot có hoạt động không."""
    await ctx.send("Pong!")

@bot.event
async def on_ready():
    """Sự kiện khi bot đã đăng nhập thành công vào Discord."""
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy với trình đọc ảnh nâng cấp.')

@bot.event
async def on_message(message):
    """
    Sự kiện xử lý mỗi khi có tin nhắn mới.
    Bot sẽ kiểm tra nếu tin nhắn đến từ Karuta và có ảnh đính kèm để xử lý.
    """
    await bot.process_commands(message)
    
    if not (message.author.id == KARUTA_ID and message.attachments):
        return

    attachment = message.attachments[0]
    if not attachment.content_type.startswith('image/'):
        return

    print("\n" + "="*40)
    print(f"🔎 [LOG] Phát hiện ảnh drop từ KARUTA. Bắt đầu xử lý...")
    print(f"  - URL ảnh: {attachment.url}")
    print(f"  - Kích thước ảnh dự kiến: {attachment.width}x{attachment.height}")

    try:
        response = requests.get(attachment.url)
        response.raise_for_status()
        image_bytes = response.content

        character_names = get_names_from_image_upgraded(image_bytes)
        
        print(f"  -> Kết quả nhận dạng tên: {character_names}")

        if not character_names or all(name == "Không đọc được" or name.startswith("Lỗi OCR") for name in character_names):
            print("  -> Không nhận dạng được tên nào hoặc có lỗi nhận dạng. Bỏ qua.")
            print("="*40 + "\n")
            if all(name == "Không đọc được" or name.startswith("Lỗi OCR") for name in character_names):
                 await message.reply("Xin lỗi, tôi không thể đọc được tên nhân vật từ ảnh này. Vui lòng thử lại với ảnh rõ hơn hoặc báo cáo lỗi nếu vấn đề tiếp diễn.")
            return

        async with message.channel.typing():
            await asyncio.sleep(1)

            reply_lines = []
            for i, name in enumerate(character_names):
                display_name = name if name and not name.startswith("Lỗi OCR") else "Không đọc được"
                lookup_name = name.lower().strip() if name and not name.startswith("Lỗi OCR") else ""
                
                if lookup_name and lookup_name not in HEART_DATABASE and lookup_name != "không đọc được":
                    log_new_character(name)

                heart_value = HEART_DATABASE.get(lookup_name, 0)
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}`")
            
            reply_content = "\n".join(reply_lines)
            await message.reply(reply_content)
            print("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")

    except requests.exceptions.RequestException as e:
        print(f"  [LỖI] Không thể tải ảnh từ URL: {e}")
        await message.reply(f"Xin lỗi, tôi không thể tải ảnh từ URL này. Lỗi: {e}")
    except Exception as e:
        print(f"  [LỖI] Đã xảy ra lỗi không xác định: {e}")
        await message.reply(f"Đã xảy ra lỗi khi xử lý ảnh của bạn. Lỗi: {e}")

    print("="*40 + "\n")


# --- PHẦN KHỞI ĐỘNG ---
if __name__ == "__main__":
    # Lưu ý: Nếu Tesseract không nằm trong PATH, bạn cần thêm dòng sau:
    # pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    # hoặc đường dẫn đến file tesseract.exe trên hệ thống của bạn.

    if TOKEN:
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server để giữ bot hoạt động...")
        run_web_server()
    else:
        print("LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env. Vui lòng tạo file .env và thêm TOKEN của bot.")

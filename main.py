# main.py (Phiên bản Nâng Cấp - Trình đọc ảnh chính xác cao)
import discord
from discord.ext import commands
import os
import re
import requests
import io
import pytesseract
from PIL import Image, ImageEnhance
from dotenv import load_dotenv
import threading
from flask import Flask
import asyncio

# --- PHẦN 1: CẤU HÌNH WEB SERVER ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot Discord đang hoạt động."
def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# --- PHẦN 2: CẤU HÌNH VÀ CÁC HÀM CỦA BOT DISCORD ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
KARUTA_ID = 646937666251915264
NEW_CHARACTERS_FILE = "new_characters.txt"

def load_heart_data(file_path):
    heart_db = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('♡'): continue
                parts = line.split('·')
                if len(parts) >= 2:
                    try:
                        heart_str = parts[0].replace('♡', '').replace(',', '').strip()
                        hearts = int(heart_str)
                        # Giả định tên nhân vật là phần cuối cùng sau dấu ·
                        name = parts[-1].lower().strip()
                        if name: heart_db[name] = hearts
                    except (ValueError, IndexError): continue
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy tệp dữ liệu '{file_path}'.")
    except Exception as e:
        print(f"Lỗi khi đọc tệp dữ liệu: {e}")
    print(f"✅ Đã tải thành công {len(heart_db)} nhân vật vào cơ sở dữ liệu.")
    return heart_db

HEART_DATABASE = load_heart_data("tennhanvatvasotim.txt")

def log_new_character(character_name):
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
    Hàm đọc ảnh được nâng cấp với kỹ thuật cắt ảnh và xử lý ảnh tiên tiến hơn.
    """
    try:
        main_image = Image.open(io.BytesIO(image_bytes))
        width, height = main_image.size

        if not (width > 800 and height > 200):
            print(f"  [LOG] Kích thước ảnh không giống ảnh drop: {width}x{height}")
            return []

        card_width = 278
        card_height = 248
        x_coords = [0, 279, 558]

        extracted_names = []
        custom_config = r'--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '

        for i in range(3):
            card_box = (x_coords[i], 0, x_coords[i] + card_width, card_height)
            card_img = main_image.crop(card_box)

            name_box = (15, 15, card_width - 15, 60)
            name_img = card_img.crop(name_box)

            # --- PHẦN NÂNG CẤP ---
            # 1. Chuyển sang ảnh xám
            name_img = name_img.convert('L')
            # 2. Tăng độ tương phản
            enhancer = ImageEnhance.Contrast(name_img)
            name_img = enhancer.enhance(2.5)
            # 3. Lọc đen trắng (Thresholding) - Giúp loại bỏ nền nhiễu
            threshold = 120 # Bạn có thể thử thay đổi giá trị này, từ 100 đến 150
            name_img = name_img.point(lambda p: 255 if p > threshold else 0)
            # --------------------

            text = pytesseract.image_to_string(name_img, config=custom_config)
            cleaned_name = text.strip().replace("\n", " ")
            
            if len(cleaned_name) > 2: # Tăng yêu cầu độ dài tên để lọc rác tốt hơn
                extracted_names.append(cleaned_name)
            else:
                extracted_names.append("")

        return extracted_names
    except Exception as e:
        print(f"  [LỖI] Xảy ra lỗi trong quá trình xử lý ảnh: {e}")
        return ["Lỗi OCR", "Lỗi OCR", "Lỗi OCR"]

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.event
async def on_ready():
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy với trình đọc ảnh nâng cấp.')

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    
    # **ĐIỀU KIỆN MỚI**: Phát hiện tin nhắn từ Karuta VÀ có file đính kèm
    if not (message.author.id == KARUTA_ID and message.attachments):
        return

    # Chỉ xử lý nếu file đính kèm là ảnh
    attachment = message.attachments[0]
    if not attachment.content_type.startswith('image/'):
        return
    
    print("\n" + "="*40)
    print(f"🔎 [LOG] Phát hiện ảnh drop từ KARUTA. Bắt đầu xử lý...")
    print(f"  - URL ảnh: {attachment.url}")

    try:
        # Tải ảnh về
        response = requests.get(attachment.url)
        response.raise_for_status() # Báo lỗi nếu tải thất bại
        image_bytes = response.content

        # Gọi hàm xử lý ảnh nâng cấp
        character_names = get_names_from_image_upgraded(image_bytes)
        
        print(f"  -> Kết quả nhận dạng tên: {character_names}")

        if not character_names:
            print("  -> Không nhận dạng được tên nào. Bỏ qua.")
            print("="*40 + "\n")
            return

        async with message.channel.typing():
            await asyncio.sleep(1) # Chờ 1 giây cho tự nhiên
            reply_lines = []
            for i, name in enumerate(character_names):
                display_name = name if name else "Không đọc được"
                lookup_name = name.lower().strip() if name else ""
                
                if lookup_name and lookup_name not in HEART_DATABASE:
                    log_new_character(name)
                    
                heart_value = HEART_DATABASE.get(lookup_name, 0)
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}`")
            
            reply_content = "\n".join(reply_lines)
            await message.reply(reply_content)
            print("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")

    except requests.exceptions.RequestException as e:
        print(f"  [LỖI] Không thể tải ảnh từ URL: {e}")
    except Exception as e:
        print(f"  [LỖI] Đã xảy ra lỗi không xác định: {e}")

    print("="*40 + "\n")


# --- PHẦN KHỞI ĐỘNG ---
if __name__ == "__main__":
    # Lưu ý: Nếu Tesseract không nằm trong PATH, bạn cần thêm dòng sau:
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    if TOKEN:
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server...")
        run_web_server()
    else:
        print("LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env.")

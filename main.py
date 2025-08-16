# main.py (Phiên bản kết hợp và nâng cấp)
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

# --- PHẦN 1: CẤU HÌNH WEB SERVER (Giữ cho bot luôn hoạt động) ---
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
HEART_DATA_FILE = "tennhanvatvasotim.txt"

# --- CÁC HÀM TIỆN ÍCH ---

def load_heart_data(file_path):
    """Tải dữ liệu tim từ file vào một dictionary."""
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
                        # Lấy phần cuối cùng làm tên và chuyển thành chữ thường
                        name = parts[-1].lower().strip()
                        if name: heart_db[name] = hearts
                    except (ValueError, IndexError):
                        # Bỏ qua các dòng không đúng định dạng
                        continue
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy tệp dữ liệu '{file_path}'. Bot sẽ hoạt động nhưng không có dữ liệu tim.")
    except Exception as e:
        print(f"Lỗi nghiêm trọng khi đọc tệp dữ liệu: {e}")
    print(f"✅ Đã tải thành công {len(heart_db)} nhân vật vào cơ sở dữ liệu tim.")
    return heart_db

def log_new_character(character_name):
    """Ghi lại tên nhân vật mới chưa có trong cơ sở dữ liệu tim."""
    try:
        existing_names = set()
        if os.path.exists(NEW_CHARACTERS_FILE):
            with open(NEW_CHARACTERS_FILE, 'r', encoding='utf-8') as f:
                existing_names = set(line.strip().lower() for line in f)
        
        if character_name and character_name.lower() not in existing_names:
            with open(NEW_CHARACTERS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{character_name}\n")
            print(f"⭐ Đã lưu nhân vật mới '{character_name}' vào file {NEW_CHARACTERS_FILE}")
    except Exception as e:
        print(f"Lỗi khi đang lưu nhân vật mới: {e}")

def preprocess_image_for_ocr(image_obj):
    """Cải thiện chất lượng ảnh để OCR đọc chính xác hơn."""
    # Chuyển ảnh sang ảnh xám
    img = image_obj.convert('L')
    # Tăng độ tương phản
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    return img

# --- HÀM XỬ LÝ ẢNH NÂNG CAO (TÍCH HỢP TỪ DOCANH.PY) ---
def get_names_from_image_advanced(image_url):
    """
    Hàm xử lý ảnh drop nâng cao, tự động nhận diện 3 hoặc 4 thẻ và trích xuất tên.
    """
    try:
        response = requests.get(image_url)
        if response.status_code != 200:
            print(f"Lỗi khi tải ảnh: Status code {response.status_code}")
            return []
            
        main_image = Image.open(io.BytesIO(response.content))
        width, height = main_image.size
        
        card_count = 0
        # Kích thước chuẩn của một thẻ Karuta
        card_width, card_height = 278, 248

        # Nhận diện số lượng thẻ dựa trên kích thước ảnh drop
        if width >= 834 and height >= 248 and height < 300: # Drop 3 thẻ
            card_count = 3
        elif width >= 834 and height >= 330 and height < 400: # Drop 4 thẻ
            card_count = 4
        else:
            print(f"Kích thước ảnh không được hỗ trợ: {width}x{height}")
            return []

        print(f"🔎 Đã phát hiện drop {card_count} thẻ. Bắt đầu xử lý OCR...")
        
        extracted_names = []
        x_coords = [0, 279, 558, 0] # Tọa độ x cho thẻ 1, 2, 3, và 4 (thẻ 4 ở hàng 2)

        for i in range(card_count):
            # Thẻ 1, 2, 3 ở hàng đầu, thẻ 4 ở hàng hai
            y_offset = 0 if i < 3 else card_height + 2 

            # Tọa độ vùng cắt cho toàn bộ thẻ (left, upper, right, lower)
            card_box = (x_coords[i], y_offset, x_coords[i] + card_width, y_offset + card_height)
            card_img = main_image.crop(card_box)

            # Tọa độ vùng cắt chỉ chứa tên nhân vật (phía trên thẻ)
            name_box = (15, 15, card_width - 15, 50)
            name_img = card_img.crop(name_box)

            # Tiền xử lý ảnh tên để tăng độ chính xác
            processed_name_img = preprocess_image_for_ocr(name_img)

            # Sử dụng Tesseract để đọc chữ
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(processed_name_img, config=custom_config)
            
            # Dọn dẹp kết quả đọc được
            cleaned_name = text.strip().replace("\n", " ")
            extracted_names.append(cleaned_name)
            
        print(f"   -> Kết quả OCR: {extracted_names}")
        return extracted_names

    except Exception as e:
        print(f"Lỗi nghiêm trọng trong quá trình xử lý ảnh: {e}")
        return []

def get_names_from_embed_fields(embed):
    """Trích xuất tên nhân vật từ các field của embed (dành cho drop chữ)."""
    extracted_names = []
    try:
        for field in embed.fields:
            # Tên thường được đặt trong cặp dấu **
            match = re.search(r'\*\*(.*?)\*\*', field.value)
            if match:
                extracted_names.append(match.group(1).strip())
        return extracted_names
    except Exception as e:
        print(f"Lỗi khi xử lý embed fields: {e}")
        return []

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents) # Đổi prefix về !

HEART_DATABASE = load_heart_data(HEART_DATA_FILE)

@bot.command(name='ping')
async def ping(ctx):
    """Lệnh để kiểm tra bot có đang hoạt động không."""
    await ctx.send('Pong!')

@bot.event
async def on_ready():
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đã sẵn sàng hoạt động với OCR nâng cấp.')

@bot.event
async def on_message(message):
    # Bỏ qua tin nhắn từ chính bot
    if message.author == bot.user:
        return

    # Xử lý các command (ví dụ: !ping) trước
    await bot.process_commands(message)

    # Chỉ xử lý tin nhắn từ Karuta
    if message.author.id == KARUTA_ID:
        print("\n" + "="*40)
        print("🔎 ĐÃ PHÁT HIỆN TIN NHẮN TỪ KARUTA")
        
        # Kiểm tra điều kiện là tin nhắn drop
        if "dropping" in message.content and message.embeds:
            print("   -> Đây là tin nhắn drop, bắt đầu xử lý...")
            embed = message.embeds[0]
            character_names = []

            # Ưu tiên xử lý ảnh nếu có
            if embed.image and embed.image.url:
                print("   -> Drop dạng Ảnh. Sử dụng OCR nâng cao...")
                character_names = get_names_from_image_advanced(embed.image.url)
            # Nếu không có ảnh, xử lý embed dạng chữ
            elif embed.fields:
                print("   -> Drop dạng Chữ/Embed. Đọc dữ liệu fields...")
                character_names = get_names_from_embed_fields(embed)
            
            # Nếu đã nhận dạng được tên, tiến hành phản hồi
            if character_names:
                async with message.channel.typing():
                    reply_lines = []
                    for i, name in enumerate(character_names):
                        display_name = name if name else "Không đọc được"
                        lookup_name = name.lower().strip() if name else ""
                        
                        # Nếu nhân vật chưa có trong DB, ghi lại để cập nhật sau
                        if lookup_name and lookup_name not in HEART_DATABASE:
                            log_new_character(name)
                            
                        heart_value = HEART_DATABASE.get(lookup_name, 0)
                        heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                        
                        reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}`")
                    
                    reply_content = "\n".join(reply_lines)
                    await message.reply(reply_content)
                    print("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")
            else:
                print("   -> KHÔNG THỂ nhận dạng được nhân vật nào. Bỏ qua.")
        else:
            print("   -> Không phải tin nhắn drop. Bỏ qua.")
        print("="*40 + "\n")


# --- PHẦN KHỞI ĐỘNG ---
if __name__ == "__main__":
    if TOKEN:
        # Chạy bot Discord trong một luồng riêng
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        
        # Chạy web server ở luồng chính để giữ bot hoạt động
        print("🚀 Khởi động Web Server để duy trì hoạt động...")
        run_web_server()
    else:
        print("LỖI NGHIÊM TRỌNG: Không tìm thấy DISCORD_TOKEN trong tệp .env hoặc biến môi trường.")

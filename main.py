# main.py (Phiên bản OCR Tại Chỗ - Tối ưu hóa với Executor)

import discord
from discord.ext import commands
import os
import re
import requests
import io
from PIL import Image
from dotenv import load_dotenv
import threading
from flask import Flask
import asyncio
import pytesseract

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

# Cấu hình Tesseract nếu cần
# Ví dụ trên Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

KARUTA_ID = 646937666251915264
NEW_CHARACTERS_FILE = "new_characters.txt"
HEART_DATABASE_FILE = "tennhanvatvasotim.txt"

def load_heart_data(file_path):
    """Tải dữ liệu số tim của nhân vật từ một file."""
    heart_db = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('♡') or not line: continue
                parts = line.split('·')
                if len(parts) >= 2:
                    try:
                        heart_str = parts[0].replace('♡', '').replace(',', '').strip()
                        hearts = int(heart_str)
                        name = parts[-1].lower().strip()
                        if name: heart_db[name] = hearts
                    except (ValueError, IndexError): continue
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy tệp dữ liệu '{file_path}'.")
    
    print(f"✅ Đã tải thành công {len(heart_db)} nhân vật vào cơ sở dữ liệu số tim.")
    return heart_db

HEART_DATABASE = load_heart_data(HEART_DATABASE_FILE)

def log_new_character(character_name):
    """Ghi lại tên nhân vật mới."""
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

# <<< THAY ĐỔI: Chuyển hàm thành hàm đồng bộ (synchronous) để chạy trong executor >>>
def get_names_from_image_ocr(image_bytes):
    """
    Sử dụng PIL để cắt ảnh và Tesseract để đọc chữ.
    Đây là một hàm blocking (tốn CPU), nên được chạy trong một luồng riêng.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        
        # Giả sử kích thước ảnh drop 3 thẻ là 836x312
        if width < 830 or height < 300:
            print(f"  [OCR] Kích thước ảnh không phù hợp ({width}x{height}), bỏ qua.")
            return []

        # Tọa độ và kích thước cố định cho mỗi thẻ
        card_width = 278
        card_height = 248
        x_coords = [0, 279, 558] # Tọa độ x bắt đầu của mỗi thẻ
        y_offset = 32            # Tọa độ y bắt đầu của các thẻ

        processed_data = []

        for i in range(3): # Xử lý 3 thẻ
            box = (x_coords[i], y_offset, x_coords[i] + card_width, y_offset + card_height)
            card_img = img.crop(box)

            top_box = (20, 20, card_width - 20, 60)
            top_img = card_img.crop(top_box)
            
            print_box = (100, card_height - 30, card_width - 20, card_height - 10)
            print_img = card_img.crop(print_box)

            char_name_config = r"--psm 7 --oem 3"
            print_num_config = r"--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789"

            char_name = pytesseract.image_to_string(top_img, config=char_name_config).strip().replace("\n", " ")
            print_number = pytesseract.image_to_string(print_img, config=print_num_config).strip()
            
            if char_name:
                processed_data.append((char_name, print_number or "???"))

        print(f"  [OCR] Kết quả nhận dạng từ luồng phụ: {processed_data}")
        return processed_data

    except Exception as e:
        print(f"  [LỖI OCR] Đã xảy ra lỗi khi xử lý ảnh trong luồng phụ: {e}")
        return []

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Sự kiện khi bot đã đăng nhập thành công vào Discord."""
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy với trình đọc ảnh OCR Tại Chỗ (PIL + Tesseract) được tối ưu hóa.')

@bot.event
async def on_message(message):
    """Sự kiện xử lý mỗi khi có tin nhắn mới."""
    if not (message.author.id == KARUTA_ID and message.attachments):
        return

    attachment = message.attachments[0]
    if not attachment.content_type.startswith('image/'):
        return

    print("\n" + "="*40)
    print(f"🔎 [LOG] Phát hiện ảnh drop từ KARUTA. Bắt đầu xử lý OCR không chặn...")
    print(f"  - URL ảnh: {attachment.url}")

    try:
        response = requests.get(attachment.url)
        response.raise_for_status()
        image_bytes = response.content

        # <<< THAY ĐỔI: Chạy hàm OCR trong một luồng riêng để không chặn bot >>>
        loop = asyncio.get_running_loop()
        # Chạy hàm get_names_from_image_ocr trong executor mặc định của event loop
        character_data = await loop.run_in_executor(
            None, get_names_from_image_ocr, image_bytes
        )
        
        print(f"  -> Kết quả nhận dạng cuối cùng: {character_data}")

        if not character_data:
            print("  -> Không nhận dạng được dữ liệu nào từ ảnh. Bỏ qua.")
            print("="*40 + "\n")
            return

        async with message.channel.typing():
            # <<< BỎ: Loại bỏ độ trễ không cần thiết >>>
            # await asyncio.sleep(1) 
            
            reply_lines = []
            for i, (name, print_number) in enumerate(character_data):
                display_name = name if name else "Không đọc được"
                lookup_name = name.lower().strip() if name else ""
                
                if lookup_name and lookup_name not in HEART_DATABASE:
                    log_new_character(name)

                heart_value = HEART_DATABASE.get(lookup_name, 0)
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}` `#{print_number}`")
            
            reply_content = "\n".join(reply_lines)
            await message.reply(reply_content)
            print("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")

    except Exception as e:
        print(f"  [LỖI] Đã xảy ra lỗi không xác định: {e}")
    print("="*40 + "\n")

# --- PHẦN KHỞI ĐỘNG ---
if __name__ == "__main__":
    if TOKEN:
        print("✅ Đã tìm thấy DISCORD_TOKEN.")
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server để giữ bot hoạt động...")
        run_web_server()
    else:
        print("❌ LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env.")

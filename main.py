# main.py (Phiên bản OCR Tại Chỗ - Tọa độ từ docanh.py)

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
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

KARUTA_ID = 646937666251915264
NEW_CHARACTERS_FILE = "new_characters.txt"
HEART_DATABASE_FILE = "tennhanvatvasotim.txt"

def load_heart_data(file_path):
    # ... (Nội dung hàm giữ nguyên)
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
    # ... (Nội dung hàm giữ nguyên)
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

# <<< THAY THẾ HOÀN TOÀN: Hàm xử lý ảnh với logic và tọa độ từ docanh.py >>>
async def get_names_from_image_ocr(image_bytes):
    """
    Sử dụng PIL để cắt ảnh và Tesseract để đọc chữ.
    Logic và tọa độ được chuyển từ file docanh.py.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        
        card_count = 0
        card_width, card_height = 278, 248

        # Logic phát hiện số thẻ từ docanh.py
        if width >= 834 and height >= 248 and height < 300: # Drop 3 thẻ
            card_count = 3
        elif width >= 834 and height >= 330 and height < 400: # Drop 4 thẻ
            card_count = 4
        else:
            print(f"Kích thước ảnh không được hỗ trợ: {width}x{height}")
            return []

        print(f"  [OCR] Phát hiện {card_count} thẻ trong ảnh.")

        # Tọa độ từ docanh.py
        x_coords = [0, 279, 558, 0]

        processed_data = []

        for i in range(card_count):
            # Logic tọa độ y từ docanh.py
            y_offset = 0 if i < 3 else card_height + 2

            # Tọa độ vùng cắt thẻ
            box = (x_coords[i], y_offset, x_coords[i] + card_width, y_offset + card_height)
            card_img = img.crop(box)

            # Tọa độ vùng tên nhân vật từ docanh.py
            top_box = (15, 15, card_width - 15, 50)
            top_img = card_img.crop(top_box)
            
            # Giữ nguyên tọa độ vùng mã số (vì docanh.py không có)
            print_box = (100, card_height - 30, card_width - 20, card_height - 10)
            print_img = card_img.crop(print_box)

            # Đọc chữ bằng Tesseract
            char_name_config = r"--psm 6 --oem 3"
            print_num_config = r"--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789"

            char_name = pytesseract.image_to_string(top_img, config=char_name_config).strip().replace("\n", " ")
            print_number = pytesseract.image_to_string(print_img, config=print_num_config).strip()
            
            if char_name:
                processed_data.append((char_name, print_number or "???"))

        print(f"  [OCR] Kết quả nhận dạng: {processed_data}")
        return processed_data

    except Exception as e:
        print(f"  [LỖI OCR] Đã xảy ra lỗi khi xử lý ảnh: {e}")
        return []

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Sự kiện khi bot đã đăng nhập thành công vào Discord."""
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy với trình đọc ảnh OCR Tại Chỗ (PIL + Tesseract).')

@bot.event
async def on_message(message):
    if not (message.author.id == KARUTA_ID and message.attachments):
        return
    
    attachment = message.attachments[0]
    if not attachment.content_type.startswith('image/'):
        return

    print("\n" + "="*40)
    print(f"🔎 [LOG] Phát hiện ảnh drop từ KARUTA. Bắt đầu xử lý OCR...")
    print(f"  - URL ảnh: {attachment.url}")

    try:
        response = requests.get(attachment.url)
        response.raise_for_status()
        image_bytes = response.content

        character_data = await get_names_from_image_ocr(image_bytes)
        
        print(f"  -> Kết quả nhận dạng cuối cùng: {character_data}")

        if not character_data:
            print("  -> Không nhận dạng được dữ liệu nào từ ảnh. Bỏ qua.")
            print("="*40 + "\n")
            return

        async with message.channel.typing():
            await asyncio.sleep(1)
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

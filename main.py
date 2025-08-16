# main.py (Phiên bản Hoàn Chỉnh - OpenCV + Tesseract)
# Tự động tìm thẻ trong ảnh và nhận dạng ký tự tại chỗ.

import discord
from discord.ext import commands
import os
import re
import requests
import io
from PIL import Image, ImageEnhance, ImageOps
from dotenv import load_dotenv
import threading
from flask import Flask
import asyncio

# <<< THÊM: Các thư viện cho xử lý ảnh nâng cao >>>
import pytesseract
import cv2
import numpy as np

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

# <<< THÊM: Cấu hình đường dẫn cho Tesseract (chỉ cần cho Windows nếu không add vào PATH) >>>
# Bỏ comment và sửa đường dẫn nếu cần thiết
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

# <<< HÀM NÂNG CAO: Tự động tìm thẻ trong ảnh bằng OpenCV và xử lý bằng Tesseract >>>
async def process_drop_dynamically(image_bytes):
    try:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        full_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Bước 1: Tiền xử lý ảnh để tìm cạnh
        gray = cv2.cvtColor(full_image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        # Bước 2: Tìm tất cả các đường viền
        contours, _ = cv2.findContours(edges.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        found_cards = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            aspect_ratio = w / float(h)
            area = cv2.contourArea(c)

            # Bước 3: Lọc các đường viền để tìm thẻ bài
            # !!! Bạn có thể cần tinh chỉnh các giá trị này !!!
            if area > 50000 and 0.6 < aspect_ratio < 0.8:
                found_cards.append((x, y, w, h))

        if not found_cards:
            print("  [OpenCV] Không tìm thấy thẻ bài nào phù hợp.")
            return []

        found_cards.sort(key=lambda item: item[0])
        print(f"  [OpenCV] Đã tìm thấy {len(found_cards)} thẻ bài.")
        
        final_results = []
        # Bước 4: Cắt và xử lý OCR cho từng thẻ tìm được
        for (x, y, w, h) in found_cards:
            card_image_pil = Image.fromarray(full_image[y:y+h, x:x+w])
            
            card_w, card_h = card_image_pil.size
            name_area = card_image_pil.crop((int(card_w*0.07), int(card_h*0.04), int(card_w*0.93), int(card_h*0.15)))
            number_area = card_image_pil.crop((int(card_w*0.5), int(card_h*0.9), int(card_w*0.95), int(card_h*0.96)))
            
            number_area_processed = ImageOps.grayscale(number_area)
            number_area_processed = ImageOps.invert(number_area_processed)
            enhancer = ImageEnhance.Contrast(number_area_processed)
            number_area_processed = enhancer.enhance(2.5)
            
            custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
            
            char_name = pytesseract.image_to_string(name_area).strip()
            print_number = pytesseract.image_to_string(number_area_processed, config=custom_config).strip()
            
            char_name_cleaned = " ".join(re.split(r'\s+', char_name))

            if char_name_cleaned and print_number:
                final_results.append((char_name_cleaned, print_number))

        return final_results

    except Exception as e:
        print(f"  [LỖI OpenCV/Tesseract] Đã xảy ra lỗi: {e}")
        return []

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
    print('Bot đang chạy với trình đọc ảnh nâng cao (OpenCV + Tesseract).')

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    
    if not (message.author.id == KARUTA_ID and message.attachments):
        return

    attachment = message.attachments[0]
    if not attachment.content_type.startswith('image/'):
        return

    print("\n" + "="*40)
    print(f"🔎 [LOG] Phát hiện ảnh drop từ KARUTA. Bắt đầu xử lý...")
    print(f"  - URL ảnh: {attachment.url}")

    try:
        response = requests.get(attachment.url)
        response.raise_for_status()
        image_bytes = response.content

        # <<< GỌI HÀM XỬ LÝ ẢNH NÂNG CAO >>>
        character_data = await process_drop_dynamically(image_bytes)
        
        print(f"  -> Kết quả nhận dạng cuối cùng: {character_data}")

        if not character_data:
            print("  -> Không nhận dạng được dữ liệu nào từ ảnh. Bỏ qua.")
            print("="*40 + "\n")
            return

        async with message.channel.typing():
            await asyncio.sleep(1)
            reply_lines = []
            for i, (name, print_number) in enumerate(character_data):
                display_name = name
                lookup_name = name.lower().strip()
                
                if lookup_name and lookup_name not in HEART_DATABASE:
                    log_new_character(name)

                heart_value = HEART_DATABASE.get(lookup_name, 0)
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}` `#{print_number}`")
            
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
    if TOKEN:
        print("✅ Đã tìm thấy DISCORD_TOKEN.")
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server để giữ bot hoạt động...")
        run_web_server()
    else:
        print("❌ LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env. Vui lòng thêm TOKEN của bot vào tệp .env.")

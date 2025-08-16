# main.py (Phiên bản cuối cùng - Tích hợp trang Debug)
import discord
from discord.ext import commands
import os
import requests
import io
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
from dotenv import load_dotenv
import threading
from flask import Flask, send_from_directory, render_template_string
import asyncio
import logging
from datetime import datetime

# =================================================================================
# PHẦN 0: CẤU HÌNH TRUNG TÂM
# =================================================================================

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
KARUTA_ID = 646937666251915264
HEART_DATA_FILE = "tennhanvatvasotim.txt"
NEW_CHARACTERS_FILE = "new_characters.txt"

DEBUG_MODE = True 
DEBUG_IMAGE_DIR = "static/debug_images" # Thư mục lưu ảnh debug

OCR_THRESHOLDS_TO_TRY = [120, 100, 130, 90, 140]
OCR_TESSERACT_CONFIG = r'--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '

# =================================================================================
# PHẦN 1: CÀI ĐẶT LOGGING VÀ WEB SERVER (CÓ CẬP NHẬT)
# =================================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])

app = Flask(__name__)

# Tự động tạo thư mục debug nếu chưa có
os.makedirs(DEBUG_IMAGE_DIR, exist_ok=True)

@app.route('/')
def home(): return "Bot Discord đang hoạt động. Truy cập /debug để xem ảnh."

# --- TRANG WEB DEBUG ---
DEBUG_PAGE_TEMPLATE = """
<!doctype html>
<html>
<head><title>Debug Images</title></head>
<body>
  <h1>Debug Images</h1>
  <p>Đây là các ảnh được lưu lại từ quá trình OCR. Click để xem và đo tọa độ.</p>
  <ul>
    {% for file in files %}
      <li><a href="/debug/{{ file }}">{{ file }}</a></li>
    {% endfor %}
  </ul>
</body>
</html>
"""
@app.route('/debug')
def list_debug_images():
    files = sorted(os.listdir(DEBUG_IMAGE_DIR), reverse=True)
    return render_template_string(DEBUG_PAGE_TEMPLATE, files=files)

@app.route('/debug/<path:filename>')
def serve_debug_image(filename):
    return send_from_directory(DEBUG_IMAGE_DIR, filename)
# --------------------

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    from waitress import serve
    serve(app, host='0.0.0.0', port=port)

# =================================================================================
# PHẦN 2: CÁC HÀM TIỆN ÍCH (Không thay đổi)
# =================================================================================
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
                        name = parts[-1].lower().strip()
                        if name: heart_db[name] = hearts
                    except (ValueError, IndexError): continue
    except FileNotFoundError:
        logging.error(f"Không tìm thấy tệp dữ liệu '{file_path}'.")
    except Exception as e:
        logging.error(f"Lỗi khi đọc tệp dữ liệu: {e}")
    logging.info(f"Đã tải thành công {len(heart_db)} nhân vật vào CSDL.")
    return heart_db

def log_new_character(character_name):
    try:
        existing_names = set()
        if os.path.exists(NEW_CHARACTERS_FILE):
            with open(NEW_CHARACTERS_FILE, 'r', encoding='utf-8') as f:
                existing_names = set(line.strip().lower() for line in f)
        if character_name and character_name.lower() not in existing_names:
            with open(NEW_CHARACTERS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{character_name}\n")
            logging.info(f"⭐ Đã lưu nhân vật mới '{character_name}' vào file {NEW_CHARACTERS_FILE}")
    except Exception as e:
        logging.error(f"Lỗi khi đang lưu nhân vật mới: {e}")

# =================================================================================
# PHẦN 3: LOGIC XỬ LÝ ẢNH (CẬP NHẬT ĐƯỜNG DẪN LƯU)
# =================================================================================

def _preprocess_for_ocr(image: Image.Image, threshold: int):
    img = image.convert('L')
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    processed_normal = img.point(lambda p: 255 if p > threshold else 0)
    processed_inverted = ImageOps.invert(processed_normal)
    return processed_normal, processed_inverted

def get_names_from_image_robust(image_bytes: bytes) -> list[str]:
    try:
        main_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        card_width, card_height = 278, 248
        x_coords = [0, 279, 558]
        extracted_names = []

        for i in range(3):
            card_box = (x_coords[i], 0, x_coords[i] + card_width, card_height)
            card_img = main_image.crop(card_box)
            name_box = (15, 15, card_width - 15, 60)
            name_img_original = card_img.crop(name_box)

            if DEBUG_MODE:
                timestamp = datetime.now().strftime("%H%M%S")
                card_img.save(os.path.join(DEBUG_IMAGE_DIR, f"card_{i}_original_{timestamp}.png"))
                name_img_original.save(os.path.join(DEBUG_IMAGE_DIR, f"name_box_{i}_original_{timestamp}.png"))

            found_name = ""
            for threshold in OCR_THRESHOLDS_TO_TRY:
                if found_name: break
                normal_img, inverted_img = _preprocess_for_ocr(name_img_original.copy(), threshold)
                
                for img_to_try, img_type in [(normal_img, "Normal"), (inverted_img, "Inverted")]:
                    text = pytesseract.image_to_string(img_to_try, config=OCR_TESSERACT_CONFIG)
                    cleaned_name = text.strip().replace("\n", " ")
                    
                    if len(cleaned_name) > 3:
                        found_name = cleaned_name
                        logging.info(f"Thẻ #{i+1}: OK! Ngưỡng={threshold}, Loại={img_type} -> '{found_name}'")
                        break
                if found_name: break

            if not found_name:
                logging.warning(f"Thẻ #{i+1}: Thất bại sau khi thử mọi ngưỡng.")
            extracted_names.append(found_name)

        return extracted_names
    except Exception as e:
        logging.error(f"Xảy ra lỗi trong quá trình xử lý ảnh: {e}", exc_info=True)
        return ["Lỗi OCR", "Lỗi OCR", "Lỗi OCR"]

# =================================================================================
# PHẦN 4 & 5: LOGIC BOT VÀ KHỞI ĐỘNG (Không thay đổi)
# =================================================================================
HEART_DATABASE = load_heart_data(HEART_DATA_FILE)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logging.info(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    logging.info('Bot đang chạy với trang web debug tích hợp.')

@bot.event
async def on_message(message: discord.Message):
    if message.author.id != KARUTA_ID or not message.attachments: return
    attachment = message.attachments[0]
    if not attachment.content_type or not attachment.content_type.startswith('image/'): return
    
    logging.info("="*40)
    logging.info(f"🔎 Phát hiện ảnh drop từ KARUTA. Bắt đầu xử lý...")
    try:
        response = await asyncio.to_thread(requests.get, attachment.url)
        response.raise_for_status()
        image_bytes = response.content
        character_names = get_names_from_image_robust(image_bytes)
        
        logging.info(f"-> Kết quả nhận dạng cuối cùng: {character_names}")
        if not any(character_names):
            logging.warning("-> Không nhận dạng được tên nào. Bỏ qua.")
            logging.info("="*40)
            return

        async with message.channel.typing():
            await asyncio.sleep(1)
            reply_lines = []
            for i, name in enumerate(character_names):
                display_name = name if name else "Không đọc được"
                lookup_name = name.lower().strip() if name else ""
                if lookup_name and lookup_name not in HEART_DATABASE:
                    log_new_character(name)
                heart_value = HEART_DATABASE.get(lookup_name, 0)
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}`")
            
            await message.reply("\n".join(reply_lines))
            logging.info("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")

    except Exception as e:
        logging.error(f"Đã xảy ra lỗi không xác định trong on_message: {e}", exc_info=True)
    logging.info("="*40)

if __name__ == "__main__":
    if not TOKEN:
        logging.critical("LỖI: Không tìm thấy DISCORD_TOKEN.")
    else:
        web_thread = threading.Thread(target=run_web_server)
        web_thread.daemon = True
        web_thread.start()
        logging.info("🚀 Khởi động Web Server...")
        bot.run(TOKEN)

# main.py (Phiên bản Siêu Cấp - Xử lý WEBP & Âm bản)
import discord
from discord.ext import commands
import os
import requests
import io
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
from dotenv import load_dotenv
import threading
from flask import Flask
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
OCR_THRESHOLDS_TO_TRY = [120, 100, 130, 90, 140]
OCR_TESSERACT_CONFIG = r'--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '

# =================================================================================
# PHẦN 1: CÀI ĐẶT LOGGING VÀ WEB SERVER
# =================================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Discord đang hoạt động."

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
# PHẦN 3: LOGIC XỬ LÝ ẢNH (OCR) NÂNG CẤP
# =================================================================================

def _preprocess_for_ocr(image: Image.Image, threshold: int):
    """Hàm phụ: Trả về cả ảnh đã xử lý và phiên bản âm bản của nó."""
    img = image.convert('L')
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    
    # Tạo ảnh trắng trên nền đen
    processed_normal = img.point(lambda p: 255 if p > threshold else 0)
    
    # Tạo ảnh đen trên nền trắng (âm bản)
    processed_inverted = ImageOps.invert(processed_normal)
    
    return processed_normal, processed_inverted

def get_names_from_image_robust(image_bytes: bytes) -> list[str]:
    """Hàm đọc ảnh siêu cấp, xử lý WEBP và thử cả ảnh thường lẫn âm bản."""
    try:
        main_image = Image.open(io.BytesIO(image_bytes))
        
        # BẮT BUỘC: Chuyển đổi từ WEBP (hoặc định dạng khác) sang RGB chuẩn
        main_image = main_image.convert("RGB")

        width, height = main_image.size
        if not (width > 800 and height > 200):
            logging.warning(f"Kích thước ảnh {width}x{height} không giống ảnh drop, bỏ qua.")
            return []

        card_width, card_height = 278, 248
        x_coords = [0, 279, 558]
        extracted_names = []

        for i in range(3):
            card_box = (x_coords[i], 0, x_coords[i] + card_width, card_height)
            card_img = main_image.crop(card_box)

            name_box = (15, 15, card_width - 15, 60)
            name_img_original = card_img.crop(name_box)

            found_name = ""
            for threshold in OCR_THRESHOLDS_TO_TRY:
                if found_name: break # Nếu đã tìm thấy tên thì không cần thử nữa

                normal_img, inverted_img = _preprocess_for_ocr(name_img_original.copy(), threshold)
                
                # Vòng lặp thử ảnh thường và ảnh âm bản
                for attempt_num, (img_to_try, img_type) in enumerate([(normal_img, "Normal"), (inverted_img, "Inverted")]):
                    if DEBUG_MODE:
                        timestamp = datetime.now().strftime("%H%M%S")
                        img_to_try.save(f"debug_card_{i}_thresh_{threshold}_{img_type}_{timestamp}.png")

                    text = pytesseract.image_to_string(img_to_try, config=OCR_TESSERACT_CONFIG)
                    cleaned_name = text.strip().replace("\n", " ")
                    
                    if len(cleaned_name) > 2:
                        found_name = cleaned_name
                        logging.info(f"Thẻ #{i+1}: OK! Ngưỡng={threshold}, Loại={img_type} -> '{found_name}'")
                        break # Thoát khỏi vòng lặp thử âm bản

            if not found_name:
                logging.warning(f"Thẻ #{i+1}: Thất bại sau khi thử mọi ngưỡng và cả âm bản.")
            
            extracted_names.append(found_name)

        return extracted_names
    except Exception as e:
        logging.error(f"Xảy ra lỗi nghiêm trọng trong quá trình xử lý ảnh: {e}", exc_info=True)
        return ["Lỗi OCR", "Lỗi OCR", "Lỗi OCR"]

# =================================================================================
# PHẦN 4: LOGIC CHÍNH CỦA BOT DISCORD (Không thay đổi)
# =================================================================================

HEART_DATABASE = load_heart_data(HEART_DATA_FILE)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logging.info(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    logging.info('Bot đang chạy với trình đọc ảnh siêu cấp.')

@bot.event
async def on_message(message: discord.Message):
    if message.author.id != KARUTA_ID or not message.attachments:
        return

    attachment = message.attachments[0]
    if not attachment.content_type or not attachment.content_type.startswith('image/'):
        return
    
    logging.info("="*40)
    logging.info(f"🔎 Phát hiện ảnh drop từ KARUTA. Bắt đầu xử lý...")
    logging.info(f"  - URL ảnh: {attachment.url}")

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
            
            reply_content = "\n".join(reply_lines)
            await message.reply(reply_content)
            logging.info("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")

    except requests.exceptions.RequestException as e:
        logging.error(f"Không thể tải ảnh từ URL: {e}")
    except Exception as e:
        logging.error(f"Đã xảy ra lỗi không xác định trong on_message: {e}", exc_info=True)

    logging.info("="*40)

# =================================================================================
# PHẦN 5: KHỞI ĐỘNG BOT
# =================================================================================

if __name__ == "__main__":
    if not TOKEN:
        logging.critical("LỖI: Không tìm thấy DISCORD_TOKEN.")
    else:
        web_thread = threading.Thread(target=run_web_server)
        web_thread.daemon = True
        web_thread.start()
        logging.info("🚀 Khởi động Web Server...")
        bot.run(TOKEN)

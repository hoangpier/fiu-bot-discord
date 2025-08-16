# main.py (Phiên bản OCR Tại Chỗ - Sử dụng PIL + Tesseract - ĐÃ SỬA LỖI)

import discord
from discord.ext import commands
import os
import re
import requests
import io
from PIL import Image, ImageEnhance
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

# CẤU HÌNH TESSERACT - QUAN TRỌNG!
# Trên Linux/Ubuntu (Render.com):
# pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
# Trên Windows:
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

def preprocess_image_for_ocr(image):
    """Tiền xử lý ảnh để cải thiện độ chính xác OCR"""
    # Chuyển sang grayscale
    if image.mode != 'L':
        image = image.convert('L')
    
    # Tăng contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    # Tăng kích thước ảnh để OCR đọc tốt hơn
    width, height = image.size
    image = image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
    
    return image

async def get_names_from_image_ocr(image_bytes):
    """
    Sử dụng PIL để cắt ảnh và Tesseract để đọc chữ.
    SỬA LỖI: Tọa độ và cách xử lý ảnh
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        
        print(f"  [OCR] Kích thước ảnh gốc: {width}x{height}")
        
        # SỬA LỖI: Kiểm tra kích thước ảnh linh hoạt hơn
        if width < 600 or height < 200:
            print(f"  [OCR] Kích thước ảnh quá nhỏ ({width}x{height}), bỏ qua.")
            return []

        # SỬA LỖI: Tọa độ động dựa trên kích thước ảnh thực tế
        # Chia ảnh thành 3 phần bằng nhau theo chiều ngang
        card_width = width // 3
        card_height = height
        
        processed_data = []

        for i in range(3):  # Xử lý 3 thẻ
            # SỬA LỖI: Tọa độ động
            x_start = i * card_width
            x_end = x_start + card_width
            
            # Cắt ảnh thẻ
            card_img = img.crop((x_start, 0, x_end, card_height))
            
            # SỬA LỖI: Vùng tên nhân vật - dựa trên tỷ lệ
            name_height = int(card_height * 0.25)  # 25% phía trên
            name_img = card_img.crop((10, 10, card_width - 10, name_height))
            
            # SỬA LỖI: Vùng mã số - phía dưới cùng
            print_height = int(card_height * 0.1)  # 10% phía dưới
            print_img = card_img.crop((20, card_height - print_height - 10, card_width - 20, card_height - 10))

            # Tiền xử lý ảnh
            name_img = preprocess_image_for_ocr(name_img)
            print_img = preprocess_image_for_ocr(print_img)
            
            # SỬA LỖI: Cấu hình Tesseract tốt hơn
            try:
                # Đọc tên nhân vật
                char_name_config = r"--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
                char_name = pytesseract.image_to_string(name_img, config=char_name_config).strip()
                char_name = re.sub(r'\s+', ' ', char_name)  # Loại bỏ khoảng trắng thừa
                
                # Đọc mã số
                print_num_config = r"--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789#"
                print_number = pytesseract.image_to_string(print_img, config=print_num_config).strip()
                
                # SỬA LỖI: Làm sạch kết quả
                if char_name and len(char_name) > 1:
                    # Loại bỏ ký tự lạ
                    char_name = re.sub(r'[^\w\s]', '', char_name).strip()
                    if char_name:
                        processed_data.append((char_name, print_number or "???"))
                        print(f"  [OCR] Thẻ {i+1}: '{char_name}' - #{print_number}")
                
            except Exception as ocr_error:
                print(f"  [LỖI OCR] Lỗi khi đọc thẻ {i+1}: {ocr_error}")
                continue

        print(f"  [OCR] Tổng kết quả nhận dạng: {len(processed_data)} thẻ")
        return processed_data

    except Exception as e:
        print(f"  [LỖI OCR] Lỗi tổng quát khi xử lý ảnh: {e}")
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
    
    # TEST TESSERACT
    try:
        test_result = pytesseract.get_tesseract_version()
        print(f'✅ Tesseract version: {test_result}')
    except Exception as e:
        print(f'❌ LỖI: Không thể khởi động Tesseract: {e}')
        print('   Hãy đảm bảo Tesseract đã được cài đặt đúng cách!')

@bot.event
async def on_message(message):
    """Sự kiện xử lý mỗi khi có tin nhắn mới."""
    
    # SỬA LỖI: Kiểm tra điều kiện chính xác hơn
    if message.author.id != KARUTA_ID:
        return
    
    if not message.attachments:
        return
    
    attachment = message.attachments[0]
    if not attachment.content_type or not attachment.content_type.startswith('image/'):
        return

    print("\n" + "="*50)
    print(f"🔎 [LOG] Phát hiện ảnh drop từ KARUTA!")
    print(f"  - Tệp: {attachment.filename}")
    print(f"  - Loại: {attachment.content_type}")
    print(f"  - Kích thước: {attachment.size} bytes")
    print(f"  - URL: {attachment.url}")

    try:
        # SỬA LỖI: Tăng timeout và xử lý lỗi kết nối
        response = requests.get(attachment.url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
        print(f"  ✅ Tải ảnh thành công ({len(image_bytes)} bytes)")

        # Gọi hàm OCR đã sửa lỗi
        character_data = await get_names_from_image_ocr(image_bytes)
        
        if not character_data:
            print("  ❌ Không nhận dạng được dữ liệu nào từ ảnh.")
            print("="*50 + "\n")
            return

        # SỬA LỖI: Thời gian chờ phù hợp hơn
        async with message.channel.typing():
            await asyncio.sleep(0.5)  # Giảm thời gian chờ
            
            reply_lines = []
            for i, (name, print_number) in enumerate(character_data):
                display_name = name if name else "Không đọc được"
                lookup_name = name.lower().strip() if name else ""
                
                # Ghi log nhân vật mới
                if lookup_name and lookup_name not in HEART_DATABASE:
                    log_new_character(name)

                # Tra cứu số tim
                heart_value = HEART_DATABASE.get(lookup_name, 0)
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                
                # SỬA LỖI: Format hiển thị đẹp hơn
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}` `#{print_number}`")
            
            reply_content = "\n".join(reply_lines)
            await message.reply(reply_content)
            print("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")
            print(f"  Nội dung: {reply_content}")

    except requests.RequestException as e:
        print(f"  [LỖI MẠNG] Không thể tải ảnh: {e}")
    except Exception as e:
        print(f"  [LỖI TỔNG QUÁT] {e}")
        import traceback
        traceback.print_exc()
    
    print("="*50 + "\n")

# SỬA LỖI: Thêm lệnh test OCR
@bot.command(name='test')
async def test_ocr(ctx):
    """Lệnh test OCR với ảnh từ URL"""
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if attachment.content_type.startswith('image/'):
            response = requests.get(attachment.url)
            character_data = await get_names_from_image_ocr(response.content)
            await ctx.send(f"Kết quả test: {character_data}")
    else:
        await ctx.send("Vui lòng đính kèm một ảnh để test!")

# --- PHẦN KHỞI ĐỘNG ---
if __name__ == "__main__":
    if TOKEN:
        print("✅ Đã tìm thấy DISCORD_TOKEN.")
        
        # SỬA LỖI: Khởi động bot trong thread riêng với xử lý lỗi
        def run_bot():
            try:
                bot.run(TOKEN)
            except Exception as e:
                print(f"❌ Lỗi khi chạy bot: {e}")
        
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True  # Đảm bảo thread kết thúc khi main process kết thúc
        bot_thread.start()
        
        print("🚀 Khởi động Web Server để giữ bot hoạt động...")
        run_web_server()
    else:
        print("❌ LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env.")

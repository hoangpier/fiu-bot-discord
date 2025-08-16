# main.py (Phiên bản OCR NÂNG CẤP - Cải thiện thuật toán cắt ảnh)

import discord
from discord.ext import commands
import os
import re
import requests
import io
from PIL import Image, ImageEnhance, ImageFilter
from dotenv import load_dotenv
import threading
from flask import Flask
import asyncio
import pytesseract
import numpy as np

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
HEART_DATABASE_FILE = "tennhanvatvasotim.txt"

def load_heart_data(file_path):
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

def advanced_image_preprocessing(image):
    """Tiền xử lý ảnh nâng cao cho OCR"""
    try:
        # Chuyển sang RGB nếu cần
        if image.mode not in ['RGB', 'L']:
            image = image.convert('RGB')
        
        # Chuyển sang grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Tăng kích thước gấp 3 lần
        width, height = image.size
        image = image.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
        
        # Tăng độ sắc nét
        image = image.filter(ImageFilter.SHARPEN)
        
        # Tăng contrast mạnh
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.5)
        
        # Tăng độ sáng một chút
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.2)
        
        return image
    except Exception as e:
        print(f"  [LỖI] Lỗi tiền xử lý ảnh: {e}")
        return image

def extract_card_regions(img):
    """
    Trích xuất chính xác 3 vùng thẻ bài từ ảnh Karuta
    Dựa trên phân tích cấu trúc ảnh thực tế
    """
    width, height = img.size
    print(f"  [EXTRACT] Phân tích ảnh kích thước: {width}x{height}")
    
    # Karuta thường có layout cố định với 3 thẻ xếp ngang
    # Mỗi thẻ chiếm ~1/3 chiều rộng
    
    cards = []
    card_width = width // 3
    
    for i in range(3):
        # Tính toán vùng cho mỗi thẻ
        x_start = i * card_width
        x_end = x_start + card_width
        
        # Cắt toàn bộ thẻ
        card_img = img.crop((x_start, 0, x_end, height))
        
        # Phân tích vùng tên và mã số
        card_height = card_img.size[1]
        card_width_actual = card_img.size[0]
        
        # VÙNG TÊN: Thường ở phần trên của thẻ (20-35% từ trên xuống)
        name_top = int(card_height * 0.05)    # 5% từ trên
        name_bottom = int(card_height * 0.35)  # 35% từ trên
        name_left = int(card_width_actual * 0.05)  # 5% từ trái
        name_right = int(card_width_actual * 0.95) # 95% từ trái
        
        name_region = card_img.crop((name_left, name_top, name_right, name_bottom))
        
        # VÙNG MÃ SỐ: Thường ở góc dưới phải (85-95% từ trên xuống)
        code_top = int(card_height * 0.85)     # 85% từ trên
        code_bottom = int(card_height * 0.98)  # 98% từ trên  
        code_left = int(card_width_actual * 0.3)   # 30% từ trái
        code_right = int(card_width_actual * 0.95) # 95% từ trái
        
        code_region = card_img.crop((code_left, code_top, code_right, code_bottom))
        
        cards.append({
            'index': i + 1,
            'full_card': card_img,
            'name_region': name_region,
            'code_region': code_region
        })
        
        print(f"  [EXTRACT] Thẻ {i+1}: Tên({name_left},{name_top},{name_right},{name_bottom}) | Mã({code_left},{code_top},{code_right},{code_bottom})")
    
    return cards

async def get_names_from_image_ocr(image_bytes):
    """
    OCR nâng cao với thuật toán cải tiến
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        original_size = img.size
        print(f"  [OCR] Ảnh gốc: {original_size[0]}x{original_size[1]}")
        
        # Kiểm tra kích thước hợp lệ
        if original_size[0] < 500 or original_size[1] < 200:
            print(f"  [OCR] Ảnh quá nhỏ, bỏ qua.")
            return []
        
        # Trích xuất các vùng thẻ
        cards = extract_card_regions(img)
        processed_data = []
        
        for card in cards:
            try:
                print(f"  [OCR] Xử lý thẻ {card['index']}...")
                
                # Tiền xử lý vùng tên
                name_img = advanced_image_preprocessing(card['name_region'])
                
                # Tiền xử lý vùng mã
                code_img = advanced_image_preprocessing(card['code_region'])
                
                # Cấu hình OCR cho tên (cho phép chữ cái, số, dấu cách, dấu chấm, dấu gạch)
                name_config = r"--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .'-"
                
                # Cấu hình OCR cho mã số (chỉ số và dấu #)
                code_config = r"--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789#"
                
                # Thực hiện OCR
                char_name = pytesseract.image_to_string(name_img, config=name_config, lang='eng').strip()
                print_number = pytesseract.image_to_string(code_img, config=code_config, lang='eng').strip()
                
                # Làm sạch kết quả tên
                if char_name:
                    # Loại bỏ ký tự không mong muốn
                    char_name = re.sub(r'[^\w\s.\'-]', '', char_name)
                    # Loại bỏ khoảng trắng thừa
                    char_name = re.sub(r'\s+', ' ', char_name).strip()
                    
                    # Kiểm tra độ dài hợp lý (tên thật thường > 2 ký tự)
                    if len(char_name) >= 2:
                        # Làm sạch mã số
                        if print_number:
                            print_number = re.sub(r'[^0123456789#]', '', print_number)
                            if not print_number.startswith('#') and print_number.isdigit():
                                print_number = '#' + print_number
                        else:
                            print_number = "???"
                        
                        processed_data.append((char_name, print_number))
                        print(f"  [OCR] ✅ Thẻ {card['index']}: '{char_name}' - '{print_number}'")
                    else:
                        print(f"  [OCR] ❌ Thẻ {card['index']}: Tên quá ngắn: '{char_name}'")
                else:
                    print(f"  [OCR] ❌ Thẻ {card['index']}: Không đọc được tên")
                    
            except Exception as card_error:
                print(f"  [OCR] ❌ Lỗi xử lý thẻ {card['index']}: {card_error}")
                continue
        
        print(f"  [OCR] 🎯 Hoàn thành: {len(processed_data)}/{len(cards)} thẻ được nhận dạng")
        return processed_data
        
    except Exception as e:
        print(f"  [OCR] ❌ Lỗi tổng quát: {e}")
        import traceback
        traceback.print_exc()
        return []

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('🔧 Bot sử dụng OCR nâng cao với thuật toán cải tiến')
    
    # Test Tesseract
    try:
        version = pytesseract.get_tesseract_version()
        print(f'✅ Tesseract version: {version}')
        
        # Test OCR đơn giản
        test_img = Image.new('L', (100, 30), color=255)
        test_result = pytesseract.image_to_string(test_img).strip()
        print(f'✅ Tesseract test: OK')
        
    except Exception as e:
        print(f'❌ LỖI Tesseract: {e}')
        print('💡 Hướng dẫn cài đặt:')
        print('   - Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-eng')
        print('   - Windows: Tải từ GitHub UB-Mannheim/tesseract')

@bot.event
async def on_message(message):
    # Kiểm tra tin nhắn từ Karuta với ảnh đính kèm
    if message.author.id != KARUTA_ID or not message.attachments:
        return
    
    attachment = message.attachments[0]
    if not (attachment.content_type and attachment.content_type.startswith('image/')):
        return

    print("\n" + "🎴"*20 + " KARUTA DETECTED " + "🎴"*20)
    print(f"📎 File: {attachment.filename}")
    print(f"📏 Size: {attachment.size:,} bytes")
    print(f"🔗 URL: {attachment.url}")

    try:
        # Tải ảnh với timeout tăng
        print("⬇️  Đang tải ảnh...")
        response = requests.get(attachment.url, timeout=45)
        response.raise_for_status()
        image_bytes = response.content
        print(f"✅ Tải thành công: {len(image_bytes):,} bytes")

        # Bắt đầu OCR
        print("🔍 Bắt đầu nhận dạng OCR...")
        character_data = await get_names_from_image_ocr(image_bytes)
        
        if not character_data:
            print("❌ Không nhận dạng được dữ liệu từ ảnh")
            print("🎴" + "="*58 + "🎴\n")
            return

        # Gửi phản hồi
        async with message.channel.typing():
            await asyncio.sleep(0.8)  # Thời gian typing tự nhiên
            
            reply_lines = []
            for i, (name, print_number) in enumerate(character_data):
                lookup_name = name.lower().strip()
                
                # Log nhân vật mới
                if lookup_name not in HEART_DATABASE:
                    log_new_character(name)

                # Tra cứu số tim
                heart_value = HEART_DATABASE.get(lookup_name, 0)
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{name}` `{print_number}`")
            
            reply_content = "\n".join(reply_lines)
            await message.reply(reply_content)
            
            print("📤 Phản hồi đã gửi:")
            for line in reply_lines:
                print(f"   {line}")

    except requests.Timeout:
        print("⏰ Timeout khi tải ảnh")
    except requests.RequestException as e:
        print(f"🌐 Lỗi mạng: {e}")
    except Exception as e:
        print(f"💥 Lỗi không xác định: {e}")
        import traceback
        traceback.print_exc()
    
    print("🎴" + "="*58 + "🎴\n")

@bot.command(name='testocr')
async def test_ocr_command(ctx):
    """Lệnh test OCR - gửi kèm ảnh"""
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if attachment.content_type and attachment.content_type.startswith('image/'):
            try:
                response = requests.get(attachment.url, timeout=30)
                response.raise_for_status()
                
                await ctx.send("🔍 Đang test OCR...")
                character_data = await get_names_from_image_ocr(response.content)
                
                if character_data:
                    result = "\n".join([f"{i+1}. `{name}` `{code}`" for i, (name, code) in enumerate(character_data)])
                    await ctx.send(f"📋 Kết quả OCR:\n{result}")
                else:
                    await ctx.send("❌ Không nhận dạng được gì từ ảnh")
                    
            except Exception as e:
                await ctx.send(f"❌ Lỗi test OCR: {e}")
        else:
            await ctx.send("❌ File đính kèm không phải là ảnh")
    else:
        await ctx.send("❌ Vui lòng đính kèm một ảnh để test OCR\nSử dụng: `!testocr` + đính kèm ảnh")

# --- KHỞI ĐỘNG ---
if __name__ == "__main__":
    if TOKEN:
        print("🔑 Discord token found")
        
        def run_bot():
            try:
                bot.run(TOKEN)
            except Exception as e:
                print(f"❌ Bot error: {e}")
        
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        
        print("🚀 Starting web server...")
        run_web_server()
    else:
        print("❌ DISCORD_TOKEN not found in .env file")

# main.py (Phiên bản v4 - Hybrid - Đọc được mọi loại Embed)

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
import pytesseract

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

# QUAN TRỌNG: Cấu hình Tesseract nếu cần thiết cho môi trường của bạn
# Ví dụ trên Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

KARUTA_ID = 646937666251915264
NEW_CHARACTERS_FILE = "new_characters.txt"
HEART_DATABASE_FILE = "tennhanvatvasotim.txt"

def load_heart_data(file_path):
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

async def get_names_from_image_ocr(image_bytes):
    """Hàm OCR để đọc tên và mã số từ hình ảnh thẻ bài."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        if width < 830 or height < 300: return []

        card_width, card_height = 278, 248
        x_coords, y_offset = [0, 279, 558], 32
        processed_data = []

        for i in range(3):
            box = (x_coords[i], y_offset, x_coords[i] + card_width, y_offset + card_height)
            card_img = img.crop(box)
            top_box = (20, 20, card_width - 20, 60)
            print_box = (100, card_height - 30, card_width - 20, card_height - 10)
            
            char_name = pytesseract.image_to_string(card_img.crop(top_box), config=r"--psm 7 --oem 3").strip().replace("\n", " ")
            print_number = pytesseract.image_to_string(card_img.crop(print_box), config=r"--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789").strip()
            
            if char_name:
                processed_data.append((char_name, print_number or "???"))
        
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
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy với phiên bản Hybrid v4 mạnh mẽ nhất.')

@bot.event
async def on_message(message):
    if not (message.author.id == KARUTA_ID and message.embeds):
        return

    try:
        embed = message.embeds[0]
        character_data = []
        print("\n" + "="*40)
        print("🔎 [LOG] Bắt đầu xử lý embed Karuta với phương pháp Hybrid...")

        # --- ƯU TIÊN 1: ĐỌC TEXT (PHƯƠNG PHÁP THÁM TỬ) ---
        print("  -> Bước 1: Cố gắng đọc dữ liệu text (cách nhanh)...")
        text_sources = []
        if embed.title: text_sources.append(embed.title)
        if embed.description: text_sources.append(embed.description)
        if embed.footer.text: text_sources.append(embed.footer.text)
        if embed.author.name: text_sources.append(embed.author.name)
        for field in embed.fields:
            if field.name: text_sources.append(field.name)
            if field.value: text_sources.append(field.value)
        
        cleaned_text = "\n".join(text_sources).replace('\u200b', '')
        pattern = r"`#(\d+)`.*· `(.*?)`"
        matches = re.findall(pattern, cleaned_text)
        
        if matches:
            character_data = [(name, print_num) for print_num, name in matches]
            print("  ✅ Thành công! Đã tìm thấy dữ liệu text.")

        # --- ƯU TIÊN 2: DỰ PHÒNG BẰNG OCR (NẾU ĐỌC TEXT THẤT BẠI) ---
        if not character_data and embed.image.url:
            print("  ⚠️ Không tìm thấy text. Chuyển sang phương án dự phòng OCR (cách chậm)...")
            try:
                response = requests.get(embed.image.url)
                response.raise_for_status()
                image_bytes = response.content
                character_data = await get_names_from_image_ocr(image_bytes)
                if character_data: print("  ✅ Thành công! OCR đã nhận dạng được thẻ.")
                else: print("  ❌ OCR không nhận dạng được dữ liệu từ ảnh.")
            except Exception as ocr_error:
                print(f"  ❌ Lỗi trong quá trình OCR: {ocr_error}")

        # --- GỬI PHẢN HỒI (NẾU CÓ DỮ LIỆU) ---
        if not character_data:
            print("  -> Thất bại: Không thể trích xuất dữ liệu bằng cả hai phương pháp. Bỏ qua.")
            print("="*40 + "\n")
            return

        print(f"  -> Dữ liệu cuối cùng: {character_data}")
        async with message.channel.typing():
            reply_lines = []
            for i, (name, print_number) in enumerate(character_data):
                display_name = name
                lookup_name = name.lower().strip()
                if lookup_name and lookup_name not in HEART_DATABASE: log_new_character(name)
                heart_value = HEART_DATABASE.get(lookup_name, 0)
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}` `#{print_number}`")
            reply_content = "\n".join(reply_lines)
            await message.reply(reply_content, mention_author=False)
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

# main.py (Phiên bản kết hợp logic xử lý ảnh nâng cao)
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

def log_new_character(character_name, series_name):
    """Lưu tên nhân vật và series mới vào file."""
    try:
        log_entry = f"{character_name} · {series_name}"
        existing_names = set()
        if os.path.exists(NEW_CHARACTERS_FILE):
            with open(NEW_CHARACTERS_FILE, 'r', encoding='utf-8') as f:
                existing_names = set(line.strip().lower() for line in f)
        
        if log_entry.lower() not in existing_names:
            with open(NEW_CHARACTERS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{log_entry}\n")
            print(f"⭐ Đã phát hiện và lưu nhân vật mới: {log_entry}")
    except Exception as e:
        print(f"Lỗi khi đang lưu nhân vật mới: {e}")

# --- LOGIC XỬ LÝ ẢNH NÂNG CAO (TỪ DOCANH.PY) ---
def get_card_info_from_image(image_url):
    """
    Hàm kết hợp: Tải ảnh, nhận diện drop 3/4 thẻ, cắt và đọc OCR trong bộ nhớ.
    Trả về một danh sách các dictionary, mỗi dictionary chứa 'character' và 'series'.
    """
    try:
        response = requests.get(image_url)
        if response.status_code != 200:
            print("Lỗi: Không thể tải ảnh từ URL.")
            return []
        
        img = Image.open(io.BytesIO(response.content))
        width, height = img.size
        card_count = 0
        card_width, card_height = 278, 248

        # Nhận diện loại drop dựa trên kích thước ảnh
        if width >= 834 and height >= 248 and height < 300: # Drop 3 thẻ
            card_count = 3
        elif width >= 834 and height >= 330 and height < 400: # Drop 4 thẻ
            card_count = 4
        else:
            print(f"Kích thước ảnh không được hỗ trợ: {width}x{height}")
            return []

        print(f"  -> Phát hiện {card_count} thẻ trong ảnh.")

        all_card_info = []
        x_coords = [0, 279, 558, 0] # Tọa độ x cho mỗi thẻ
        custom_config = r"--psm 7 --oem 3" # Cấu hình OCR cho một dòng văn bản

        for i in range(card_count):
            y_offset = 0 if i < 3 else card_height + 2
            box = (x_coords[i], y_offset, x_coords[i] + card_width, y_offset + card_height)
            card_img = img.crop(box)

            # Cắt và đọc tên nhân vật (phía trên)
            top_box = (15, 15, card_width - 15, 50)
            top_img = ImageEnhance.Contrast(card_img.crop(top_box).convert('L')).enhance(2.0)
            char_text = pytesseract.image_to_string(top_img, config=custom_config).strip().replace("\n", " ")

            # Cắt và đọc tên anime (phía dưới)
            bottom_box = (15, card_height - 55, card_width - 15, card_height - 15)
            bottom_img = ImageEnhance.Contrast(card_img.crop(bottom_box).convert('L')).enhance(2.0)
            anime_text = pytesseract.image_to_string(bottom_img, config=custom_config).strip().replace("\n", " ")
            
            all_card_info.append({"character": char_text, "series": anime_text})

        return all_card_info

    except Exception as e:
        print(f"Lỗi nghiêm trọng trong quá trình xử lý ảnh: {e}")
        return []

def get_names_from_embed_fields(embed):
    extracted_names = []
    try:
        for field in embed.fields:
            match = re.search(r'\*\*(.*?)\*\*', field.value)
            if match:
                extracted_names.append({"character": match.group(1).strip(), "series": "N/A"})
        return extracted_names
    except Exception as e:
        print(f"Lỗi khi xử lý embed fields: {e}")
        return []

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')

async def process_karuta_drop(message):
    embed = message.embeds[0]
    card_data = []
    print(f"🔎 Phát hiện drop từ Karuta. Bắt đầu xử lý...")

    if embed.image and embed.image.url:
        print("  -> Đây là Drop dạng Ảnh. Sử dụng logic OCR nâng cao...")
        card_data = get_card_info_from_image(embed.image.url)
    elif embed.fields:
        print("  -> Đây là Drop dạng Chữ/Embed. Đọc dữ liệu fields...")
        card_data = get_names_from_embed_fields(embed)

    if not card_data:
        print("  Lỗi: Không thể trích xuất thông tin thẻ từ drop.")
        return

    print("  -> Kết quả nhận dạng:")
    for i, card in enumerate(card_data):
        print(f"    Thẻ {i+1}: {card.get('character', 'Lỗi')} · {card.get('series', 'Lỗi')}")

    async with message.channel.typing():
        reply_lines = []
        for i, card in enumerate(card_data):
            name = card.get("character")
            series = card.get("series")
            
            display_name = name if name else "Không đọc được"
            lookup_name = name.lower().strip() if name else ""
            
            if lookup_name and lookup_name not in HEART_DATABASE:
                log_new_character(name, series)
            
            heart_value = HEART_DATABASE.get(lookup_name, 0)
            heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
            
            reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}`")

        reply_content = "\n".join(reply_lines)
        await message.reply(reply_content)
        print("✅ Đã gửi phản hồi thành công.")

@bot.event
async def on_message(message):
    if message.author.id == KARUTA_ID and "dropping" in message.content and message.embeds:
        await process_karuta_drop(message)

@bot.event
async def on_message_edit(before, after):
    if after.author.id == KARUTA_ID and "dropping" in after.content and after.embeds:
        if not before.embeds:
            await process_karuta_drop(after)

# --- PHẦN KHỞI ĐỘNG ---
if __name__ == "__main__":
    if TOKEN:
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server...")
        run_web_server()
    else:
        print("LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env.")

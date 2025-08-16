# main.py (Phiên bản Chẩn đoán Sâu)
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

# ... (Toàn bộ các hàm load_heart_data, log_new_character, và xử lý ảnh giữ nguyên như cũ)
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

def log_new_character(character_name):
    try:
        existing_names = set()
        if os.path.exists(NEW_CHARACTERS_FILE):
            with open(NEW_CHARACTERS_FILE, 'r', encoding='utf-8') as f:
                existing_names = set(line.strip().lower() for line in f)
        if character_name and character_name.lower() not in existing_names:
            with open(NEW_CHARACTERS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{character_name}\n")
            print(f"⭐ Đã phát hiện và lưu nhân vật mới: {character_name}")
    except Exception as e:
        print(f"Lỗi khi đang lưu nhân vật mới: {e}")

def get_names_from_image(image_url):
    try:
        response = requests.get(image_url)
        if response.status_code != 200: return []
        main_image = Image.open(io.BytesIO(response.content))
        img_width, img_height = main_image.size
        card_width = img_width // 3
        extracted_names = []
        for i in range(3):
            left, right = i * card_width, (i + 1) * card_width
            card_image = main_image.crop((left, 0, right, img_height))
            name_region = card_image.crop((20, 30, card_width - 40, 100))
            processed_region = ImageEnhance.Contrast(card_image.convert('L')).enhance(2.0)
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(processed_region, config=custom_config)
            cleaned_name = text.split('\n')[0].strip()
            extracted_names.append(cleaned_name)
        return extracted_names
    except Exception as e:
        print(f"Lỗi trong quá trình xử lý ảnh: {e}")
        return []

def get_names_from_embed_fields(embed):
    extracted_names = []
    try:
        for field in embed.fields:
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
bot = commands.Bot(command_prefix="!", intents=intents)

processed_message_ids = set() # Set để lưu ID các tin nhắn đã xử lý

async def process_karuta_drop(message):
    """Hàm xử lý logic chung."""
    if message.id in processed_message_ids:
        print(f"  [CHẨN ĐOÁN] Bỏ qua tin nhắn ID {message.id} vì đã xử lý rồi.")
        return
    
    embed = message.embeds[0]
    character_names = []
    print(f"🔎 Bắt đầu xử lý drop cho tin nhắn ID: {message.id}")

    if embed.image and embed.image.url:
        print("  -> Đây là Drop dạng Ảnh. Sử dụng OCR...")
        character_names = get_names_from_image(embed.image.url)
    elif embed.fields:
        print("  -> Đây là Drop dạng Chữ/Embed. Đọc dữ liệu fields...")
        character_names = get_names_from_embed_fields(embed)

    while len(character_names) < 3:
        character_names.append("")

    print(f"  Nhận dạng các tên: {character_names}")

    async with message.channel.typing():
        reply_lines = []
        for i in range(3):
            name = character_names[i]
            display_name = name if name else "Không đọc được"
            lookup_name = name.lower().strip() if name else ""
            if lookup_name and lookup_name not in HEART_DATABASE:
                log_new_character(name)
            heart_value = HEART_DATABASE.get(lookup_name, 0)
            heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
            reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}`")
        reply_content = "\n".join(reply_lines)
        await message.reply(reply_content)
        processed_message_ids.add(message.id) # Đánh dấu tin nhắn này đã xử lý
        print(f"✅ Đã gửi phản hồi thành công cho tin nhắn ID: {message.id}")

@bot.event
async def on_ready():
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy ở chế độ CHẨN ĐOÁN SÂU.')

@bot.event
async def on_message(message):
    if message.author.id == KARUTA_ID:
        print("\n" + "="*50)
        print(f"🔥 SỰ KIỆN ON_MESSAGE TỪ KARUTA (ID: {message.id})")
        print(f"  - Nội dung: '{message.content}'")
        print(f"  - Có embeds không?: {bool(message.embeds)}")
        if message.embeds:
            print(f"  - Embed[0] có ảnh không?: {bool(message.embeds[0].image.url)}")
        
        if "dropping" in message.content and message.embeds:
            await process_karuta_drop(message)
        print("="*50 + "\n")

@bot.event
async def on_message_edit(before, after):
    if after.author.id == KARUTA_ID:
        print("\n" + "="*50)
        print(f"🔥 SỰ KIỆN ON_MESSAGE_EDIT TỪ KARUTA (ID: {after.id})")
        print(f"  - Nội dung: '{after.content}'")
        print(f"  - TRƯỚC: Có embeds không?: {bool(before.embeds)}")
        print(f"  - SAU: Có embeds không?: {bool(after.embeds)}")
        if after.embeds:
            print(f"  - SAU: Embed[0] có ảnh không?: {bool(after.embeds[0].image.url)}")

        if "dropping" in after.content and after.embeds:
            await process_karuta_drop(after)
        print("="*50 + "\n")


# --- PHẦN 3: KHỞI ĐỘNG BOT VÀ WEB SERVER ---
if __name__ == "__main__":
    if TOKEN:
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server...")
        run_web_server()
    else:
        print("LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env.")

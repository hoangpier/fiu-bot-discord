# main.py (Phiên bản cuối cùng - Sửa lỗi thời gian tải embed)
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
import asyncio # Thêm thư viện asyncio để dùng hàm sleep

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

def log_new_character(character_name):
    try:
        existing_names = set()
        if os.path.exists(NEW_CHARACTERS_FILE):
            with open(NEW_CHARACTERS_FILE, 'r', encoding='utf-8') as f:
                existing_names = set(line.strip().lower() for line in f)
        if character_name and character_name.lower() not in existing_names:
            with open(NEW_CHARACTERS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{character_name}\n")
            print(f"  [CHẨN ĐOÁN] ⭐ Đã lưu '{character_name}' vào file {NEW_CHARACTERS_FILE}")
    except Exception as e:
        print(f"Lỗi khi đang lưu nhân vật mới: {e}")

def preprocess_image_for_ocr(image_obj):
    img = image_obj.convert('L')
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    return img

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
            processed_region = preprocess_image_for_ocr(name_region)
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(processed_region, config=custom_config)
            cleaned_name = text.split('\n')[0].strip()
            extracted_names.append(cleaned_name)
        return extracted_names
    except Exception as e:
        print(f"  [CHẨN ĐOÁN] Lỗi trong quá trình xử lý ảnh: {e}")
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
        print(f"  [CHẨN ĐOÁN] Lỗi khi xử lý embed fields: {e}")
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
    print('Bot đang chạy ở chế độ chẩn đoán.')

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    # Chỉ xử lý tin nhắn từ Karuta và có chứa chữ "dropping"
    if not (message.author.id == KARUTA_ID and "dropping" in message.content):
        return

    # LOGIC MỚI: Chờ một chút để embed được tải đầy đủ
    print("\n" + "="*40)
    print(f"🔎 [CHẨN ĐOÁN] Phát hiện tin nhắn drop tiềm năng từ KARUTA. Chờ 1 giây để embed tải...")
    print(f"  - ID Tin nhắn: {message.id}")
    
    try:
        # Chờ 1 giây
        await asyncio.sleep(1)
        
        # Lấy lại thông tin đầy đủ của tin nhắn từ Discord
        updated_message = await message.channel.fetch_message(message.id)
        print("  -> Đã lấy lại tin nhắn cập nhật.")

        # Bây giờ, kiểm tra embed trên tin nhắn đã được cập nhật
        if updated_message.embeds:
            print("  -> Embed đã được tìm thấy! Bắt đầu xử lý...")
            embed = updated_message.embeds[0]
            
            character_names = []
            if embed.image and embed.image.url:
                print("    -> Đây là Drop dạng Ảnh. Sử dụng OCR...")
                character_names = get_names_from_image(embed.image.url)
            elif embed.fields:
                print("    -> Đây là Drop dạng Chữ/Embed. Đọc dữ liệu fields...")
                character_names = get_names_from_embed_fields(embed)

            while len(character_names) < 3:
                character_names.append("")

            print(f"    -> Kết quả nhận dạng tên: {character_names}")

            async with updated_message.channel.typing():
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
                await updated_message.reply(reply_content)
                print("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")

        else:
            print("  -> Sau khi chờ, vẫn không tìm thấy embed. Bỏ qua.")

    except discord.NotFound:
        print("  -> Tin nhắn đã bị xóa trong khi chờ. Bỏ qua.")
    except Exception as e:
        print(f"  -> Đã xảy ra lỗi khi xử lý: {e}")

    print("="*40 + "\n")


# --- PHẦN KHỞI ĐỘNG ---
if __name__ == "__main__":
    if TOKEN:
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server...")
        run_web_server()
    else:
        print("LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env.")

# main.py (Phiên bản Hoàn Chỉnh - Đọc Tên + Mã Số & Chống Lỗi 429)

import discord
from discord.ext import commands
import os
import re
import requests
import io
import base64
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from dotenv import load_dotenv
import threading
from flask import Flask
import asyncio
import time # <<< THÊM: Thư viện thời gian cho Cooldown

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
load_dotenv() # Tải các biến môi trường từ tệp .env

# Lấy TOKEN và API KEY từ file .env
TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

KARUTA_ID = 646937666251915264
NEW_CHARACTERS_FILE = "new_characters.txt"
HEART_DATABASE_FILE = "tennhanvatvasotim.txt"

# <<< THÊM: Cấu hình cho Cooldown để chống lỗi 429 >>>
last_api_call_time = 0
COOLDOWN_SECONDS = 3 # Thời gian chờ giữa các lần gọi API (giây)

def load_heart_data(file_path):
    """
    Tải dữ liệu số tim của nhân vật từ một file.
    """
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
    """
    Ghi lại tên nhân vật mới chưa có trong cơ sở dữ liệu số tim vào một file.
    """
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

async def get_names_from_image_via_gemini_api(image_bytes):
    """
    Sử dụng Gemini API để nhận diện tên nhân vật VÀ MÃ SỐ từ ảnh.
    Trả về một danh sách các tuple, mỗi tuple chứa (tên, mã số).
    """
    if not GEMINI_API_KEY:
        print("  [LỖI API] Biến môi trường GEMINI_API_KEY chưa được thiết lập.")
        return [("Lỗi API (Key)", "0"), ("Lỗi API (Key)", "0"), ("Lỗi API (Key)", "0")]

    try:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        prompt = "Từ hình ảnh thẻ bài Karuta này, hãy trích xuất tên nhân vật và dãy số ở góc dưới cùng bên phải của mỗi thẻ. Trả về kết quả theo thứ tự từ trái sang phải, mỗi nhân vật trên một dòng, theo định dạng chính xác: Tên nhân vật #DãySố"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/webp",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
        }
        
        apiUrl = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
        print("  [API] Đang gửi ảnh đến Gemini API để nhận dạng (Tên + Mã số)...")
        
        response = requests.post(apiUrl, headers={'Content-Type': 'application/json'}, json=payload)
        response.raise_for_status()
        result = response.json()
        
        if result and result.get('candidates') and result['candidates'][0].get('content') and result['candidates'][0]['content'].get('parts'):
            api_text = result['candidates'][0]['content']['parts'][0]['text']
            
            processed_data = []
            lines = api_text.strip().split('\n')
            
            for line in lines:
                if '#' in line:
                    parts = line.split('#', 1)
                    name = parts[0].strip()
                    print_number = parts[1].strip()
                    
                    cleaned_name = re.sub(r'[^a-zA-Z0-9\s\'-.]', '', name)
                    cleaned_name = ' '.join(cleaned_name.split())
                    
                    processed_data.append((cleaned_name, print_number))
                else:
                    processed_data.append((line.strip(), "???"))

            print(f"  [API] Nhận dạng từ Gemini API: {processed_data}")
            return processed_data
        else:
            print("  [API] Phản hồi từ Gemini API không chứa dữ liệu hợp lệ.")
            return [("Không đọc được (API)", "0"), ("Không đọc được (API)", "0"), ("Không đọc được (API)", "0")]

    except requests.exceptions.RequestException as e:
        print(f"  [LỖI API] Lỗi khi gọi Gemini API: {e}")
        return [("Lỗi API (Request)", "0"), ("Lỗi API (Request)", "0"), ("Lỗi API (Request)", "0")]
    except Exception as e:
        print(f"  [LỖI API] Đã xảy ra lỗi không xác định khi xử lý API: {e}")
        return [("Lỗi API (Unknown)", "0"), ("Lỗi API (Unknown)", "0"), ("Lỗi API (Unknown)", "0")]

async def get_names_from_image_upgraded(image_bytes):
    """Hàm đọc ảnh được nâng cấp, sử dụng Gemini API."""
    return await get_names_from_image_via_gemini_api(image_bytes)

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command()
async def ping(ctx):
    """Lệnh ping đơn giản để kiểm tra bot có hoạt động không."""
    await ctx.send("Pong!")

@bot.event
async def on_ready():
    """Sự kiện khi bot đã đăng nhập thành công vào Discord."""
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy với trình đọc ảnh nâng cấp (sử dụng Gemini API).')

@bot.event
async def on_message(message):
    """
    Sự kiện xử lý mỗi khi có tin nhắn mới.
    Đã tích hợp cơ chế Cooldown để tránh lỗi 429.
    """
    global last_api_call_time

    await bot.process_commands(message)
    
    if not (message.author.id == KARUTA_ID and message.attachments):
        return

    # <<< BẮT ĐẦU: Logic kiểm tra Cooldown >>>
    current_time = time.time()
    if current_time - last_api_call_time < COOLDOWN_SECONDS:
        print(f"🔎 [COOLDOWN] Yêu cầu bị bỏ qua do còn trong thời gian chờ. Chờ {COOLDOWN_SECONDS - (current_time - last_api_call_time):.1f}s nữa.")
        return
    
    last_api_call_time = current_time
    # <<< KẾT THÚC: Logic kiểm tra Cooldown >>>

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

        character_data = await get_names_from_image_upgraded(image_bytes)
        
        print(f"  -> Kết quả nhận dạng (Tên, Mã số): {character_data}")

        if not character_data or any(name.startswith("Lỗi API") for name, num in character_data):
            print("  -> Lỗi API hoặc không nhận dạng được. Bỏ qua.")
            last_api_call_time = current_time - COOLDOWN_SECONDS 
            print("="*40 + "\n")
            await message.reply("Xin lỗi, tôi không thể đọc được dữ liệu từ ảnh này. Vui lòng thử lại với ảnh rõ hơn hoặc báo cáo lỗi nếu vấn đề tiếp diễn.")
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

    except requests.exceptions.RequestException as e:
        print(f"  [LỖI] Không thể tải ảnh từ URL: {e}")
        await message.reply(f"Xin lỗi, tôi không thể tải ảnh từ URL này. Lỗi: {e}")
    except Exception as e:
        print(f"  [LỖI] Đã xảy ra lỗi không xác định: {e}")
        await message.reply(f"Đã xảy ra lỗi khi xử lý ảnh của bạn. Lỗi: {e}")

    print("="*40 + "\n")


# --- PHẦN KHỞI ĐỘNG ---
if __name__ == "__main__":
    if TOKEN and GEMINI_API_KEY:
        print("✅ Đã tìm thấy DISCORD_TOKEN và GEMINI_API_KEY.")
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server để giữ bot hoạt động...")
        run_web_server()
    else:
        if not TOKEN:
            print("❌ LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env. Vui lòng thêm TOKEN của bot vào tệp .env.")
        if not GEMINI_API_KEY:
            print("❌ LỖI: Không tìm thấy GEMINI_API_KEY trong tệp .env. Vui lòng thêm key của Gemini API vào tệp .env.")

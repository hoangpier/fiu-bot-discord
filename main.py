# main.py (Phiên bản Nâng Cấp - Trình đọc ảnh chính xác cao với Gemini API)

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
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') # <<< THAY ĐỔI QUAN TRỌNG

KARUTA_ID = 646937666251915264
NEW_CHARACTERS_FILE = "new_characters.txt"
HEART_DATABASE_FILE = "tennhanvatvasotim.txt"

def load_heart_data(file_path):
    """
    Tải dữ liệu số tim của nhân vật từ một file.
    Dữ liệu được lưu trữ trong một dictionary (cơ sở dữ liệu trong bộ nhớ).
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
    Đảm bảo không ghi trùng lặp tên.
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
    Sử dụng Gemini API để nhận diện tên nhân vật từ ảnh.
    Trả về danh sách tên nhân vật.
    """
    # <<< THAY ĐỔI QUAN TRỌNG: Kiểm tra xem API Key có tồn tại không
    if not GEMINI_API_KEY:
        print("  [LỖI API] Biến môi trường GEMINI_API_KEY chưa được thiết lập.")
        return ["Lỗi API (Key)", "Lỗi API (Key)", "Lỗi API (Key)"]
        
    try:
        # Mã hóa ảnh sang Base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Định nghĩa prompt để hỏi AI về tên nhân vật
        prompt = "Từ hình ảnh thẻ bài Karuta này, hãy trích xuất và liệt kê tên các nhân vật theo thứ tự từ trái sang phải. Chỉ trả về tên, mỗi tên trên một dòng."

        # Cấu trúc payload cho Gemini API
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/webp", # MIME type của ảnh drop Karuta thường là webp
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
        }
        
        # Cấu hình URL với API Key đã được tải từ .env
        apiUrl = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY # <<< THAY ĐỔI QUAN TRỌNG
        # Đã cập nhật lên model gemini-1.5-flash mới hơn và ổn định hơn

        print("  [API] Đang gửi ảnh đến Gemini API để nhận dạng...")
        
        # Gửi yêu cầu đến Gemini API
        response = requests.post(apiUrl, headers={'Content-Type': 'application/json'}, json=payload)
        response.raise_for_status() # Báo lỗi nếu có lỗi HTTP

        result = response.json()
        
        # Phân tích phản hồi từ API
        if result and result.get('candidates') and result['candidates'][0].get('content') and result['candidates'][0]['content'].get('parts'):
            api_text = result['candidates'][0]['content']['parts'][0]['text']
            names = [name.strip() for name in api_text.split('\n') if name.strip()]
            
            # Hậu xử lý nhỏ (loại bỏ ký tự không cần thiết)
            processed_names = []
            for name in names:
                cleaned = re.sub(r'[^a-zA-Z0-9\s\'-.]', '', name)
                cleaned = ' '.join(cleaned.split())
                processed_names.append(cleaned)

            print(f"  [API] Nhận dạng từ Gemini API: {processed_names}")
            return processed_names
        else:
            print("  [API] Phản hồi từ Gemini API không chứa dữ liệu hợp lệ.")
            return ["Không đọc được (API)", "Không đọc được (API)", "Không đọc được (API)"]

    except requests.exceptions.RequestException as e:
        print(f"  [LỖI API] Lỗi khi gọi Gemini API: {e}")
        return ["Lỗi API (Request)", "Lỗi API (Request)", "Lỗi API (Request)"]
    except Exception as e:
        print(f"  [LỖI API] Đã xảy ra lỗi không xác định khi xử lý API: {e}")
        return ["Lỗi API (Unknown)", "Lỗi API (Unknown)", "Lỗi API (Unknown)"]

async def get_names_from_image_upgraded(image_bytes):
    """
    Hàm đọc ảnh được nâng cấp, sử dụng Gemini API.
    """
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
    Bot sẽ kiểm tra nếu tin nhắn đến từ Karuta và có ảnh đính kèm để xử lý.
    """
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

        # Gọi hàm xử lý ảnh nâng cấp
        character_names = await get_names_from_image_upgraded(image_bytes)
        
        print(f"  -> Kết quả nhận dạng tên: {character_names}")

        if not character_names or any(name.startswith("Lỗi API") for name in character_names):
            print("  -> Lỗi API hoặc không nhận dạng được tên. Bỏ qua.")
            print("="*40 + "\n")
            await message.reply("Xin lỗi, tôi không thể đọc được tên nhân vật từ ảnh này. Vui lòng thử lại với ảnh rõ hơn hoặc báo cáo lỗi nếu vấn đề tiếp diễn.")
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
    # <<< THAY ĐỔI QUAN TRỌNG: Kiểm tra cả TOKEN và GEMINI_API_KEY trước khi chạy
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

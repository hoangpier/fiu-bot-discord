# main.py (Phiên bản Nâng Cấp - Trình đọc ảnh chính xác cao với Gemini API)

import discord
from discord.ext import commands
import os
import re
import requests
import io
import pytesseract # Vẫn giữ lại cho cấu hình Tesseract ban đầu, nhưng sẽ không được dùng trực tiếp cho OCR nữa
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from dotenv import load_dotenv
import threading
from flask import Flask
import asyncio
import base64 # Thêm thư viện base64 để mã hóa ảnh

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
    try:
        # Mã hóa ảnh sang Base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Định nghĩa prompt để hỏi AI về tên nhân vật
        prompt = "Từ hình ảnh thẻ bài Karuta này, hãy trích xuất và liệt kê tên các nhân vật theo thứ tự từ trái sang phải. Nếu có thể, hãy ghi cả tên của người cha của Tsukasa nếu không phải chỉ là 'Tsukasa's Father'. Chỉ trả về tên, mỗi tên trên một dòng."

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
        
        # Cấu hình API key và URL
        # API key sẽ được Canvas cung cấp tự động khi để trống
        apiKey = "" 
        apiUrl = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key=" + apiKey

        print("  [API] Đang gửi ảnh đến Gemini API để nhận dạng...")
        
        # Gửi yêu cầu đến Gemini API
        # Sử dụng requests.post thay vì fetch trong Python
        response = requests.post(apiUrl, headers={'Content-Type': 'application/json'}, json=payload)
        response.raise_for_status() # Báo lỗi nếu có lỗi HTTP

        result = response.json()
        
        # Phân tích phản hồi từ API
        if result and result.get('candidates') and result['candidates'][0].get('content') and result['candidates'][0]['content'].get('parts'):
            # Lấy văn bản phản hồi từ AI
            api_text = result['candidates'][0]['content']['parts'][0]['text']
            
            # Tách tên nhân vật từ phản hồi (mỗi tên trên một dòng)
            names = [name.strip() for name in api_text.split('\n') if name.strip()]
            
            # Hậu xử lý nhỏ (có thể thêm nhiều quy tắc nếu AI vẫn trả về sai)
            processed_names = []
            for name in names:
                # Loại bỏ các ký tự không phải chữ cái, số, khoảng trắng, ', -, .
                cleaned = re.sub(r'[^a-zA-Z0-9\s\'-.]', '', name)
                # Xử lý khoảng trắng thừa
                cleaned = ' '.join(cleaned.split())
                # Chuyển đổi tên để xử lý một số lỗi phổ biến nếu có
                # Ví dụ: nếu AI trả về "Tsukasa's Father" mà bạn muốn "Tsukasa no Chichi"
                # if cleaned == "Tsukasa's Father":
                #     cleaned = "Tsukasa no Chichi"
                processed_names.append(cleaned)

            print(f"  [API] Nhận dạng từ Gemini API: {processed_names}")
            return processed_names
        else:
            print("  [API] Phản hồi từ Gemini API không chứa dữ liệu hợp lệ.")
            return ["Không đọc được (API)", "Không đọc được (API)", "Không đọc được (API)"]

    except requests.exceptions.RequestException as e:
        print(f"  [LỖI API] Lỗi khi gọi Gemini API: {e}")
        return ["Lỗi API (Thẻ 1)", "Lỗi API (Thẻ 2)", "Lỗi API (Thẻ 3)"]
    except Exception as e:
        print(f"  [LỖI API] Đã xảy ra lỗi không xác định khi xử lý API: {e}")
        return ["Lỗi API (Thẻ 1)", "Lỗi API (Thẻ 2)", "Lỗi API (Thẻ 3)"]


def get_names_from_image_upgraded(image_bytes):
    """
    Hàm đọc ảnh được nâng cấp.
    Đã được thay đổi để sử dụng Gemini API thay vì Tesseract cục bộ.
    """
    # Gọi hàm sử dụng Gemini API
    return asyncio.run(get_names_from_image_via_gemini_api(image_bytes))


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
    print(f"  - Kích thước ảnh dự kiến: {attachment.width}x{attachment.height}")

    try:
        response = requests.get(attachment.url)
        response.raise_for_status()
        image_bytes = response.content

        # Gọi hàm xử lý ảnh nâng cấp (hiện tại sử dụng Gemini API)
        character_names = get_names_from_image_upgraded(image_bytes)
        
        print(f"  -> Kết quả nhận dạng tên: {character_names}")

        if not character_names or all(name == "Không đọc được" or name.startswith("Lỗi OCR") or name.startswith("Lỗi API") for name in character_names):
            print("  -> Không nhận dạng được tên nào hoặc có lỗi nhận dạng. Bỏ qua.")
            print("="*40 + "\n")
            if all(name == "Không đọc được" or name.startswith("Lỗi OCR") or name.startswith("Lỗi API") for name in character_names):
                 await message.reply("Xin lỗi, tôi không thể đọc được tên nhân vật từ ảnh này. Vui lòng thử lại với ảnh rõ hơn hoặc báo cáo lỗi nếu vấn đề tiếp diễn.")
            return

        async with message.channel.typing():
            await asyncio.sleep(1)

            reply_lines = []
            for i, name in enumerate(character_names):
                display_name = name if name and not name.startswith("Lỗi OCR") and not name.startswith("Lỗi API") else "Không đọc được"
                lookup_name = name.lower().strip() if name and not name.startswith("Lỗi OCR") and not name.startswith("Lỗi API") else ""
                
                if lookup_name and lookup_name not in HEART_DATABASE and lookup_name != "không đọc được":
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
    # Lưu ý: Nếu Tesseract không nằm trong PATH, bạn cần thêm dòng sau:
    # pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    # hoặc đường dẫn đến file tesseract.exe trên hệ thống của bạn.
    
    # Do hiện tại đang dùng Gemini API, nên Tesseract.pytesseract.tesseract_cmd không còn cần thiết
    # trừ khi bạn muốn fallback về Tesseract khi API lỗi.

    if TOKEN:
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server để giữ bot hoạt động...")
        run_web_server()
    else:
        print("LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env. Vui lòng tạo file .env và thêm TOKEN của bot.")

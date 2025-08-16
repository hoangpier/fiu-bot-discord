# main.py (Phiên bản Nâng Cấp - Trình đọc ảnh chính xác cao)

import discord
from discord.ext import commands
import os
import re
import requests
import io
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps # Thêm ImageFilter và ImageOps
from dotenv import load_dotenv
import threading
from flask import Flask
import asyncio

# --- PHẦN 1: CẤU HÌNH WEB SERVER ---
# Khởi tạo ứng dụng Flask để giữ bot hoạt động trên các nền tảng hosting
app = Flask(__name__)

@app.route('/')
def home():
    """Trang chủ đơn giản để hiển thị bot đang hoạt động."""
    return "Bot Discord đang hoạt động."

def run_web_server():
    """Chạy web server Flask trên cổng được cấu hình."""
    port = int(os.environ.get('PORT', 10000)) # Lấy cổng từ biến môi trường, mặc định 10000
    app.run(host='0.0.0.0', port=port) # Chạy ứng dụng trên tất cả các interface

# --- PHẦN 2: CẤU HÌNH VÀ CÁC HÀM CỦA BOT DISCORD ---
load_dotenv() # Tải các biến môi trường từ file .env
TOKEN = os.getenv('DISCORD_TOKEN') # Lấy Discord Bot Token
KARUTA_ID = 646937666251915264 # ID của bot Karuta, dùng để lọc tin nhắn
NEW_CHARACTERS_FILE = "new_characters.txt" # File lưu tên nhân vật mới phát hiện
HEART_DATABASE_FILE = "tennhanvatvasotim.txt" # File dữ liệu tên nhân vật và số tim

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
                # Bỏ qua các dòng không bắt đầu bằng '♡' hoặc trống
                if not line.startswith('♡') or not line:
                    continue
                parts = line.split('·')
                if len(parts) >= 2:
                    try:
                        # Trích xuất số tim, loại bỏ '♡' và dấu phẩy, sau đó chuyển sang số nguyên
                        heart_str = parts[0].replace('♡', '').replace(',', '').strip()
                        hearts = int(heart_str)
                        # Tên nhân vật là phần cuối cùng sau dấu ·, chuyển về chữ thường để tra cứu
                        name = parts[-1].lower().strip()
                        if name:
                            heart_db[name] = hearts
                    except (ValueError, IndexError):
                        # Bỏ qua các dòng không đúng định dạng
                        continue
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy tệp dữ liệu '{file_path}'.")
    except Exception as e:
        print(f"Lỗi khi đọc tệp dữ liệu: {e}")
    print(f"✅ Đã tải thành công {len(heart_db)} nhân vật vào cơ sở dữ liệu số tim.")
    return heart_db

# Tải cơ sở dữ liệu số tim khi bot khởi động
HEART_DATABASE = load_heart_data(HEART_DATABASE_FILE)

def log_new_character(character_name):
    """
    Ghi lại tên nhân vật mới chưa có trong cơ sở dữ liệu số tim vào một file.
    Đảm bảo không ghi trùng lặp tên.
    """
    try:
        existing_names = set()
        # Đọc các tên đã có để tránh trùng lặp
        if os.path.exists(NEW_CHARACTERS_FILE):
            with open(NEW_CHARACTERS_FILE, 'r', encoding='utf-8') as f:
                existing_names = set(line.strip().lower() for line in f)
        
        # Nếu tên nhân vật hợp lệ và chưa có trong danh sách, thì ghi vào file
        if character_name and character_name.lower() not in existing_names:
            with open(NEW_CHARACTERS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{character_name}\n")
            print(f"  [LOG] ⭐ Đã lưu nhân vật mới '{character_name}' vào file {NEW_CHARACTERS_FILE}")
    except Exception as e:
        print(f"Lỗi khi đang lưu nhân vật mới: {e}")

def get_names_from_image_upgraded(image_bytes):
    """
    Hàm đọc ảnh được nâng cấp với kỹ thuật cắt ảnh chính xác và tiền xử lý ảnh
    cải tiến để tăng độ chính xác của OCR.
    """
    try:
        main_image = Image.open(io.BytesIO(image_bytes))
        width, height = main_image.size

        # Giả định đây là ảnh drop 3 thẻ của Karuta, có kích thước đặc trưng
        # Kiểm tra kích thước tổng thể để đảm bảo đây là ảnh drop hợp lệ
        if not (width > 800 and height > 200):
            print(f"  [LOG] Kích thước ảnh không giống ảnh drop Karuta: {width}x{height}. Bỏ qua.")
            return []

        # Kích thước chuẩn của một thẻ Karuta trong ảnh drop (được ước tính)
        card_width = 278
        card_height = 248
        # Tọa độ X bắt đầu của mỗi thẻ trong ảnh tổng thể
        x_coords = [0, 279, 558] 

        extracted_names = []
        
        # Cấu hình Tesseract OCR nâng cao
        # --psm 6: Giả định một khối văn bản thống nhất. Tốt cho một dòng văn bản.
        # --oem 3: Sử dụng cả công cụ OCR cũ (Legacy) và mới (LSTM).
        # -c tessedit_char_whitelist: Chỉ nhận diện các ký tự được liệt kê. 
        #   Giúp giảm lỗi nhận dạng ký tự rác. Bao gồm chữ cái tiếng Anh và khoảng trắng.
        custom_config = r'--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '

        for i in range(3): # Lặp qua 3 thẻ bài
            # Bước 1: Cắt thẻ bài riêng lẻ từ ảnh lớn
            card_box = (x_coords[i], 0, x_coords[i] + card_width, card_height)
            card_img = main_image.crop(card_box)

            # Bước 2: Cắt vùng tên nhân vật từ thẻ bài
            # Tọa độ này được tinh chỉnh để bao phủ chính xác vùng tên
            # Tọa độ (left, top, right, bottom)
            name_box = (15, 15, card_width - 15, 60) 
            name_img = card_img.crop(name_box)

            # Tiền xử lý ảnh để tăng độ nét và tương phản cho OCR
            name_img = name_img.convert('L') # 1. Chuyển sang ảnh xám (Grayscale)
            
            # 2. Tăng độ tương phản (Contrast)
            enhancer = ImageEnhance.Contrast(name_img)
            name_img = enhancer.enhance(2.0) # Có thể thử các giá trị khác như 1.8, 2.2

            # 3. Làm sắc nét (Sharpening) để làm nổi bật các cạnh của chữ
            name_img = name_img.filter(ImageFilter.SHARPEN)

            # 4. Nhị phân hóa (Binarization) để chuyển ảnh thành chỉ đen và trắng hoàn toàn.
            # Điều này giúp Tesseract dễ dàng phân biệt chữ và nền.
            # Bước 4a: Đảo màu để chữ đen trên nền trắng (Tesseract thường hoạt động tốt hơn với chữ đen trên nền trắng)
            name_img = ImageOps.invert(name_img) 
            # Bước 4b: Áp dụng ngưỡng để biến pixel thành đen hoặc trắng
            # Sử dụng 128 làm ngưỡng: pixel nào sáng hơn 128 sẽ thành trắng (255), tối hơn thành đen (0)
            name_img = name_img.point(lambda x: 0 if x < 128 else 255) 
            # Bước 4c: Đảo lại màu về chữ trắng trên nền đen nếu cần (hoặc giữ nguyên tùy hiệu quả)
            # Trong trường hợp này, chữ trắng trên nền đen thường xuất hiện trong Karuta, 
            # nên giữ nguyên sau bước invert đầu tiên nếu nó đã tạo ra chữ đen trên nền trắng, 
            # rồi lại invert lần nữa để trả về chữ trắng trên nền đen (nếu cần). 
            # Hoặc chỉ cần invert một lần và để Tesseract xử lý.
            # Để đảm bảo chữ trắng trên nền tối (như Karuta), ta sẽ giữ nguyên sau invert ban đầu
            # và sau đó nhị phân hóa. Nếu Tesseract vẫn kém, có thể thử giữ chữ đen trên nền trắng.
            
            # Để tốt nhất cho Karuta, thường chữ trắng trên nền tối, Tesseract đôi khi thích chữ đen trên nền trắng.
            # Thử nghiệm với việc chỉ invert một lần và binarize.
            # Sau khi invert và binarize, ta có thể có chữ đen trên nền trắng hoặc ngược lại.
            # Tesseract thường xử lý tốt cả hai, nhưng chữ đen trên nền trắng thường tốt hơn một chút.
            
            # Để đảm bảo chữ đen trên nền trắng:
            # name_img = name_img.point(lambda x: 0 if x < 128 else 255) # Chữ đen (0) nếu < 128, nền trắng (255) nếu >= 128
            # name_img = ImageOps.invert(name_img) # Đảo lại thành chữ trắng trên nền đen
            # => Hoặc giữ nguyên sau invert đầu tiên + binarize
            # Với ảnh Karuta gốc, tên là chữ trắng trên nền màu, nên sau invert sẽ là chữ đen trên nền trắng.
            # Vậy nên ta sẽ không invert lần thứ hai.
            
            # Bước 3: Nhận diện ký tự bằng Tesseract
            text = pytesseract.image_to_string(name_img, config=custom_config)
            
            # Dọn dẹp tên: loại bỏ khoảng trắng thừa, ký tự xuống dòng
            cleaned_name = text.strip().replace("\n", " ") 
            
            # Lọc bỏ các tên quá ngắn hoặc rỗng, có thể là lỗi nhận dạng
            if len(cleaned_name) > 1 and not all(char.isspace() for char in cleaned_name):
                extracted_names.append(cleaned_name)
            else:
                extracted_names.append("Không đọc được") # Nếu không đọc được hoặc quá ngắn thì gán giá trị này

        return extracted_names
    except Exception as e:
        print(f"  [LỖI] Xảy ra lỗi trong quá trình xử lý ảnh: {e}")
        # Trả về lỗi để bot có thể thông báo lại cho người dùng
        return ["Lỗi OCR (Thẻ 1)", "Lỗi OCR (Thẻ 2)", "Lỗi OCR (Thẻ 3)"]

# --- PHẦN CHÍNH CỦA BOT ---
# Khởi tạo Intents của Discord để bot có quyền đọc nội dung tin nhắn và file đính kèm
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents) # Đặt prefix cho các lệnh của bot

@bot.command()
async def ping(ctx):
    """Lệnh ping đơn giản để kiểm tra bot có hoạt động không."""
    await ctx.send("Pong!")

@bot.event
async def on_ready():
    """Sự kiện khi bot đã đăng nhập thành công vào Discord."""
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy với trình đọc ảnh nâng cấp.')

@bot.event
async def on_message(message):
    """
    Sự kiện xử lý mỗi khi có tin nhắn mới.
    Bot sẽ kiểm tra nếu tin nhắn đến từ Karuta và có ảnh đính kèm để xử lý.
    """
    # Xử lý các lệnh thông thường trước (ví dụ: !ping)
    await bot.process_commands(message)
    
    # **ĐIỀU KIỆN QUAN TRỌNG**:
    # 1. Tin nhắn phải từ bot Karuta (dùng KARUTA_ID để kiểm tra).
    # 2. Tin nhắn phải có file đính kèm.
    if not (message.author.id == KARUTA_ID and message.attachments):
        return # Nếu không thỏa mãn điều kiện, bỏ qua tin nhắn

    # Chỉ xử lý nếu file đính kèm đầu tiên là ảnh
    attachment = message.attachments[0]
    if not attachment.content_type.startswith('image/'):
        return # Nếu không phải ảnh, bỏ qua

    print("\n" + "="*40)
    print(f"🔎 [LOG] Phát hiện ảnh drop từ KARUTA. Bắt đầu xử lý...")
    print(f"  - URL ảnh: {attachment.url}")
    print(f"  - Kích thước ảnh dự kiến: {attachment.width}x{attachment.height}")

    try:
        # Tải ảnh về từ URL đính kèm
        response = requests.get(attachment.url)
        response.raise_for_status() # Gây ra lỗi HTTPError nếu phản hồi mã lỗi (4xx hoặc 5xx)
        image_bytes = response.content # Lấy nội dung ảnh dưới dạng byte

        # Gọi hàm xử lý ảnh nâng cấp để nhận dạng tên nhân vật
        character_names = get_names_from_image_upgraded(image_bytes)
        
        print(f"  -> Kết quả nhận dạng tên: {character_names}")

        # Nếu không nhận dạng được tên nào hoặc chỉ toàn lỗi
        if not character_names or all(name == "Không đọc được" or name.startswith("Lỗi OCR") for name in character_names):
            print("  -> Không nhận dạng được tên nào hoặc có lỗi nhận dạng. Bỏ qua.")
            print("="*40 + "\n")
            # Có thể phản hồi lỗi nếu tất cả đều là "Không đọc được"
            if all(name == "Không đọc được" or name.startswith("Lỗi OCR") for name in character_names):
                 await message.reply("Xin lỗi, tôi không thể đọc được tên nhân vật từ ảnh này. Vui lòng thử lại với ảnh rõ hơn hoặc báo cáo lỗi nếu vấn đề tiếp diễn.")
            return

        # Bật trạng thái 'đang gõ' để thông báo bot đang xử lý
        async with message.channel.typing():
            await asyncio.sleep(1) # Chờ một chút để tạo cảm giác tự nhiên

            reply_lines = []
            for i, name in enumerate(character_names):
                display_name = name if name and not name.startswith("Lỗi OCR") else "Không đọc được"
                # Chuyển tên về chữ thường và loại bỏ khoảng trắng để tra cứu trong database
                lookup_name = name.lower().strip() if name and not name.startswith("Lỗi OCR") else ""
                
                # Nếu đây là tên mới và hợp lệ, ghi vào file log
                if lookup_name and lookup_name not in HEART_DATABASE and lookup_name != "không đọc được":
                    log_new_character(name) # Ghi tên gốc (chưa lower/strip)

                # Lấy số tim từ database, nếu không có thì mặc định là 0
                heart_value = HEART_DATABASE.get(lookup_name, 0)
                # Định dạng hiển thị số tim
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                
                # Thêm dòng phản hồi vào danh sách
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}`")
            
            # Gộp các dòng phản hồi thành một tin nhắn duy nhất
            reply_content = "\n".join(reply_lines)
            await message.reply(reply_content) # Gửi phản hồi lên kênh Discord
            print("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")

    except requests.exceptions.RequestException as e:
        # Xử lý lỗi khi không thể tải ảnh
        print(f"  [LỖI] Không thể tải ảnh từ URL: {e}")
        await message.reply(f"Xin lỗi, tôi không thể tải ảnh từ URL này. Lỗi: {e}")
    except Exception as e:
        # Xử lý các lỗi không xác định khác
        print(f"  [LỖI] Đã xảy ra lỗi không xác định: {e}")
        await message.reply(f"Đã xảy ra lỗi khi xử lý ảnh của bạn. Lỗi: {e}")

    print("="*40 + "\n")


# --- PHẦN KHỞI ĐỘNG ---
if __name__ == "__main__":
    # Lưu ý: Nếu Tesseract không nằm trong PATH, bạn cần thêm dòng sau:
    # pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    # hoặc đường dẫn đến file tesseract.exe trên hệ thống của bạn.

    if TOKEN:
        # Khởi động bot Discord trong một luồng riêng biệt
        bot_thread = threading.Thread(target=bot.run, args=(TOKEN,))
        bot_thread.start()
        print("🚀 Khởi động Web Server để giữ bot hoạt động...")
        # Khởi động web server Flask trong luồng chính (hoặc luồng khác nếu cần)
        run_web_server()
    else:
        print("LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env. Vui lòng tạo file .env và thêm TOKEN của bot.")

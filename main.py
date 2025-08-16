# main.py
import discord
from discord.ext import commands
import os
import re
import requests
import io
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from dotenv import load_dotenv

# --- CẤU HÌNH BAN ĐẦU ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
KARUTA_ID = 646937666251915264

# --- HÀM TẢI VÀ XỬ LÝ DỮ LIỆU TIM ---

def load_heart_data(file_path):
    """
    Tải dữ liệu từ file txt và chuyển thành một dictionary để tra cứu.
    Key: tên nhân vật (viết thường), Value: số tim (dạng số nguyên).
    """
    heart_db = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Dùng regex để trích xuất tim và tên một cách chính xác
                match = re.search(r'♡([\d,]+)\s·\s(?:.*?)\s·\s(.+)', line)
                if match:
                    # Lấy số tim, loại bỏ dấu phẩy và chuyển thành số
                    heart_str = match.group(1).replace(',', '')
                    hearts = int(heart_str)
                    
                    # Lấy tên, chuyển thành chữ thường và xóa khoảng trắng thừa
                    name = match.group(2).lower().strip()
                    
                    heart_db[name] = hearts
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy tệp dữ liệu '{file_path}'. Vui lòng đảm bảo tệp này tồn tại.")
    except Exception as e:
        print(f"Lỗi khi đọc tệp dữ liệu: {e}")
        
    print(f"Đã tải thành công {len(heart_db)} nhân vật vào cơ sở dữ liệu.")
    return heart_db

# Tải dữ liệu ngay khi bot khởi động
HEART_DATABASE = load_heart_data("tennhanvatvasotim.txt")

# --- HÀM XỬ LÝ ẢNH VÀ OCR ---

def preprocess_image_for_ocr(image_obj):
    """Tiền xử lý ảnh để tăng độ chính xác cho OCR."""
    img = image_obj.convert('L')  # Chuyển sang ảnh xám
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0) # Tăng độ tương phản
    return img

def get_names_from_drop_image(image_url):
    """
    Sử dụng OCR để đọc tên 3 nhân vật từ ảnh drop của Karuta.
    """
    try:
        response = requests.get(image_url)
        if response.status_code != 200:
            return []

        main_image = Image.open(io.BytesIO(response.content))
        img_width, img_height = main_image.size
        card_width = img_width // 3
        
        extracted_names = []

        for i in range(3):
            # Cắt riêng ảnh của từng thẻ
            left = i * card_width
            right = (i + 1) * card_width
            card_image = main_image.crop((left, 0, right, img_height))

            # Cắt vùng chứa tên nhân vật (phần trên cùng của thẻ)
            # Tọa độ này được ước tính và có thể cần điều chỉnh
            name_region = card_image.crop((20, 30, card_width - 40, 100))
            
            processed_region = preprocess_image_for_ocr(name_region)
            
            # Đọc văn bản từ ảnh
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(processed_region, config=custom_config)
            
            # Dọn dẹp tên: xóa các ký tự thừa và chỉ lấy dòng đầu tiên
            cleaned_name = text.split('\n')[0].strip()
            extracted_names.append(cleaned_name)
            
        return extracted_names
    except Exception as e:
        print(f"Lỗi trong quá trình xử lý ảnh: {e}")
        return []

# --- THIẾT LẬP BOT DISCORD ---

# Cần bật Message Content Intent trên Developer Portal
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Đăng nhập thành công với tên {bot.user}')
    print('Bot đã sẵn sàng quét drop của Karuta!')

@bot.event
async def on_message(message):
    # Bỏ qua tin nhắn từ chính bot
    if message.author == bot.user:
        return

    # Chỉ xử lý tin nhắn từ Karuta
    if message.author.id == KARUTA_ID:
        # Kiểm tra xem có phải là tin nhắn drop và có chứa ảnh không
        if message.embeds and "I'm dropping 3 cards since this server is currently active!" in message.content:
            embed = message.embeds[0]
            if embed.image and embed.image.url:
                print(f"Phát hiện drop từ Karuta trong kênh {message.channel.name}. Bắt đầu xử lý ảnh...")

                async with message.channel.typing():
                    # Lấy tên nhân vật từ ảnh
                    character_names = get_names_from_drop_image(embed.image.url)

                    if not character_names or len(character_names) != 3:
                        print("Không thể đọc đủ 3 tên nhân vật từ ảnh.")
                        return

                    print(f"Đã nhận dạng các tên: {character_names}")

                    # Chuẩn bị nội dung phản hồi
                    reply_lines = []
                    for i, name in enumerate(character_names):
                        # Tra cứu tên trong database
                        lookup_name = name.lower().strip()
                        heart_value = HEART_DATABASE.get(lookup_name, 0) # Mặc định là 0 nếu không tìm thấy
                        
                        # Định dạng số tim cho dễ đọc
                        heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                        
                        reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{name}`")

                    reply_content = "\n".join(reply_lines)
                    await message.reply(reply_content)
                    print("Đã gửi phản hồi thành công.")

# Chạy bot
if TOKEN:
    bot.run(TOKEN)
else:
    print("LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env")

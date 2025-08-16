# main.py (Phiên bản viết lại bằng discum)
import discum
import os
import re
import requests
import io
import pytesseract
from PIL import Image, ImageEnhance
from dotenv import load_dotenv
import threading

# --- PHẦN 1: CẤU HÌNH VÀ CÁC HÀM XỬ LÝ (Tương tự phiên bản trước) ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
KARUTA_ID = "646937666251915264"
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
            print(f"⭐ Đã phát hiện và lưu nhân vật mới: {character_name}")
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
        print(f"Lỗi trong quá trình xử lý ảnh: {e}")
        return []

def get_names_from_embed_fields(embed):
    extracted_names = []
    try:
        for field in embed.get('fields', []):
            match = re.search(r'\*\*(.*?)\*\*', field.get('value', ''))
            if match:
                extracted_names.append(match.group(1).strip())
        return extracted_names
    except Exception as e:
        print(f"Lỗi khi xử lý embed fields: {e}")
        return []

# --- PHẦN 2: LOGIC BOT VIẾT BẰNG DISUM ---
bot = discum.Client(token=TOKEN, log=False)

def process_karuta_drop(msg):
    """Hàm xử lý logic khi phát hiện drop, được gọi trong một luồng riêng."""
    embed = msg['embeds'][0]
    character_names = []

    print(f"🔎 Phát hiện drop từ Karuta. Bắt đầu xử lý...")

    if embed.get('image', {}).get('url'):
        print("  -> Đây là Drop dạng Ảnh. Sử dụng OCR...")
        character_names = get_names_from_image(embed['image']['url'])
    elif embed.get('fields'):
        print("  -> Đây là Drop dạng Chữ/Embed. Đọc dữ liệu fields...")
        character_names = get_names_from_embed_fields(embed)

    while len(character_names) < 3:
        character_names.append("")

    print(f"  Nhận dạng các tên: {character_names}")

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
    bot.reply(msg['channel_id'], msg['id'], reply_content)
    print("✅ Đã gửi phản hồi thành công.")

@bot.gateway.command
def on_message(resp):
    if resp.event.message:
        msg = resp.parsed.auto()

        # Lệnh kiểm tra !ping
        if msg['content'] == '!ping':
            print(f"✅ Nhận được lệnh !ping từ {msg['author']['username']}. Đang trả lời...")
            bot.sendMessage(msg['channel_id'], "Pong!")
            return

        # Logic xử lý drop
        author_id = msg.get('author', {}).get('id')
        content = msg.get('content', '')
        embeds = msg.get('embeds')

        if author_id == KARUTA_ID and "dropping" in content and embeds:
            # Chạy xử lý trong một luồng riêng để không làm nghẽn gateway
            threading.Thread(target=process_karuta_drop, args=(msg,)).start()

@bot.gateway.command
def on_ready(resp):
    if resp.event.ready:
        user = resp.parsed.auto()['user']
        print(f"✅ Đăng nhập thành công với tài khoản: {user['username']}#{user['discriminator']}")
        print('Bot đã sẵn sàng quét drop của Karuta!')

# --- PHẦN 3: KHỞI ĐỘNG BOT ---
if __name__ == "__main__":
    if TOKEN:
        bot.gateway.run(auto_reconnect=True)
    else:
        print("LỖI: Không tìm thấy DISCORD_TOKEN trong tệp .env.")

# main.py (Phiên bản Embed - Siêu nhanh, không cần OCR)

import discord
from discord.ext import commands
import os
import re # Thư viện cần thiết để trích xuất dữ liệu
from dotenv import load_dotenv
import threading
from flask import Flask

# --- PHẦN 1: CẤU HÌNH WEB SERVER (Giữ nguyên) ---
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
    """Tải dữ liệu số tim của nhân vật từ một file."""
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
    """Ghi lại tên nhân vật mới."""
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

# <<< BỎ HOÀN TOÀN HÀM get_names_from_image_ocr >>>

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True # Vẫn cần để đọc nội dung tin nhắn cơ bản
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Sự kiện khi bot đã đăng nhập thành công vào Discord."""
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy với phương pháp đọc Embed siêu tốc.')

@bot.event
async def on_message(message):
    """Sự kiện xử lý mỗi khi có tin nhắn mới."""
    # Chỉ xử lý tin nhắn từ Karuta và tin nhắn đó phải có Embed
    if not (message.author.id == KARUTA_ID and message.embeds):
        return

    try:
        # Lấy embed đầu tiên từ tin nhắn
        embed = message.embeds[0]

        # Karuta drop embed thường có thông tin trong 'description'
        if not embed.description:
            return
        
        print("\n" + "="*40)
        print(f"🔎 [LOG] Phát hiện drop embed từ KARUTA. Bắt đầu xử lý...")

        # Sử dụng regex để tìm tất cả các dòng chứa thông tin thẻ
        # Mẫu: `Print` · icon · `Tên nhân vật` · Tên series
        pattern = r"`#(\d+)`.*· `(.*?)`"
        matches = re.findall(pattern, embed.description)

        if not matches:
            print("  -> Không tìm thấy dữ liệu thẻ hợp lệ trong embed. Bỏ qua.")
            print("="*40 + "\n")
            return
        
        # Dữ liệu character_data bây giờ là một danh sách các cặp (tên, print)
        character_data = [(name, print_num) for print_num, name in matches]
        print(f"  -> Dữ liệu trích xuất: {character_data}")

        async with message.channel.typing():
            reply_lines = []
            for i, (name, print_number) in enumerate(character_data):
                display_name = name
                lookup_name = name.lower().strip()
                
                if lookup_name and lookup_name not in HEART_DATABASE:
                    log_new_character(name)

                heart_value = HEART_DATABASE.get(lookup_name, 0)
                heart_display = f"{heart_value:,}" if heart_value > 0 else "N/A"
                
                reply_lines.append(f"{i+1} | ♡**{heart_display}** · `{display_name}` `#{print_number}`")
            
            reply_content = "\n".join(reply_lines)
            await message.reply(reply_content, mention_author=False) # mention_author=False để không ping người dùng
            print("✅ ĐÃ GỬI PHẢN HỒI THÀNH CÔNG")

    except Exception as e:
        print(f"  [LỖI] Đã xảy ra lỗi không xác định khi xử lý embed: {e}")
    
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

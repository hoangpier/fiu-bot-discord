# main.py (Phiên bản Embed v2 - Xử lý nhiều định dạng)

import discord
from discord.ext import commands
import os
import re
from dotenv import load_dotenv
import threading
from flask import Flask

# --- PHẦN 1: CẤU HÌNH WEB SERVER (Giữ nguyên) ---
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
HEART_DATABASE_FILE = "tennhanvatvasotim.txt"

def load_heart_data(file_path):
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

# --- PHẦN CHÍNH CỦA BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot Discord đã đăng nhập với tên {bot.user}')
    print('Bot đang chạy với bộ xử lý Embed v2 thông minh.')

@bot.event
async def on_message(message):
    if not (message.author.id == KARUTA_ID and message.embeds):
        return

    try:
        embed = message.embeds[0]
        character_data = []

        print("\n" + "="*40)
        print(f"🔎 [LOG] Phát hiện embed từ KARUTA. Bắt đầu phân tích...")

        # --- LOGIC MỚI: KIỂM TRA NHIỀU NƠI ---

        # Cách 1: Kiểm tra trong 'description' (cho các drop dạng danh sách)
        if embed.description:
            print("  -> Tìm thấy 'description'. Đang phân tích theo dạng danh sách...")
            pattern = r"`#(\d+)`.*· `(.*?)`"
            matches = re.findall(pattern, embed.description)
            if matches:
                character_data = [(name, print_num) for print_num, name in matches]

        # Cách 2: Nếu không có trong description, kiểm tra trong 'fields' (cho các drop dạng cột)
        if not character_data and embed.fields:
            print("  -> 'description' trống. Chuyển sang phân tích 'fields'...")
            for field in embed.fields:
                char_name = field.name
                print_match = re.search(r'#(\d+)', field.value)
                if char_name and print_match:
                    print_number = print_match.group(1)
                    character_data.append((char_name, print_number))

        # --- KẾT THÚC LOGIC MỚI ---

        if not character_data:
            print("  -> Không tìm thấy dữ liệu nhân vật dạng text trong embed. Bỏ qua.")
            print("="*40 + "\n")
            return
        
        print(f"  -> Dữ liệu trích xuất thành công: {character_data}")

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
            await message.reply(reply_content, mention_author=False)
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

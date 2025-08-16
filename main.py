# main.py (Phiên bản v3 - Thám tử Embed)

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
    print('Bot đang chạy với bộ xử lý Thám tử Embed v3.')

@bot.event
async def on_message(message):
    if not (message.author.id == KARUTA_ID and message.embeds):
        return

    try:
        embed = message.embeds[0]
        
        print("\n" + "="*40)
        print(f"🔎 [LOG] Phát hiện embed từ KARUTA. Khởi động chế độ thám tử...")

        # --- BƯỚC 1: GOM TẤT CẢ TEXT TỪ MỌI NGÓC NGÁCH ---
        text_sources = []
        if embed.title: text_sources.append(embed.title)
        if embed.description: text_sources.append(embed.description)
        if embed.footer.text: text_sources.append(embed.footer.text)
        if embed.author.name: text_sources.append(embed.author.name)
        for field in embed.fields:
            if field.name: text_sources.append(field.name)
            if field.value: text_sources.append(field.value)
        
        # --- BƯỚC 2: KẾT HỢP VÀ "RỬA" SẠCH TEXT ---
        full_text_content = "\n".join(text_sources)
        # Loại bỏ ký tự không chiều rộng (zero-width space), một cách phổ biến để ẩn text
        cleaned_text = full_text_content.replace('\u200b', '')

        # Dùng print để debug, xem bot thực sự "đọc" được gì
        print(f"  [DEBUG] Nội dung text thô bot đọc được:\n---\n{cleaned_text}\n---")

        # --- BƯỚC 3: TRÍCH XUẤT DỮ LIỆU BẰNG REGEX ---
        # Mẫu regex này tìm cặp `Print` và `Tên nhân vật`
        pattern = r"`#(\d+)`.*· `(.*?)`"
        matches = re.findall(pattern, cleaned_text)
        
        character_data = []
        if matches:
            character_data = [(name, print_num) for print_num, name in matches]

        if not character_data:
            print("  -> Đã quét toàn bộ embed nhưng không tìm thấy dữ liệu hợp lệ. Bỏ qua.")
            print("="*40 + "\n")
            return
        
        print(f"  -> Trích xuất thành công: {character_data}")

        # Gửi phản hồi (giữ nguyên như cũ)
        async with message.channel.typing():
            reply_lines = []
            for i, (name, print_number) in enumerate(character_data):
                display_name = name
                lookup_name = name.lower().strip()
                if lookup_name and lookup_name not in HEART_DATABASE: log_new_character(name)
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


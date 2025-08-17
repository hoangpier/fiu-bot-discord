# fiu.py (Phiên bản gộp tất cả trong một file để deploy trên Render)
import os
import json
import discord
import requests
import aiohttp
import threading
from discord.ext import commands
from flask import Flask, request, redirect
from dotenv import load_dotenv

# --- CÀI ĐẶT BAN ĐẦU ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
OWNER_ID = int(os.getenv('OWNER_ID', 0))

if not all([TOKEN, CLIENT_ID, CLIENT_SECRET, OWNER_ID]):
    exit("LỖI: Hãy chắc chắn DISCORD_TOKEN, CLIENT_ID, CLIENT_SECRET, và OWNER_ID đã được thiết lập trong file .env")

# ==============================================================================
# PHẦN 1: CODE CỦA BOT DISCORD (Giữ nguyên)
# ==============================================================================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, owner_id=OWNER_ID)

def get_user_access_token(user_id: int):
    try:
        with open('tokens.json', 'r') as f:
            tokens = json.load(f)
            return tokens.get(str(user_id))
    except (FileNotFoundError, json.JSONDecodeError):
        return None

async def add_member_to_guild(guild_id: int, user_id: int, access_token: str):
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"access_token": access_token}
    
    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=headers, json=data) as response:
            if response.status in [201, 204]:
                return True, "Thành công hoặc đã có trong server"
            else:
                error_text = await response.text()
                return False, f"HTTP {response.status}: {error_text}"

@bot.event
async def on_ready():
    print(f'>>> Bot {bot.user.name} đã sẵn sàng!')

@bot.command(name='force_add', help='Thêm một người dùng vào tất cả các server.')
@commands.is_owner()
async def force_add(ctx, user_id_str: str):
    try:
        user_id = int(user_id_str)
    except ValueError:
        await ctx.send("⚠️ ID người dùng không hợp lệ. Vui lòng chỉ nhập số.")
        return
    await ctx.send(f"✅ Đã nhận lệnh! Bắt đầu quá trình thêm người dùng có ID `{user_id}`...")
    access_token = get_user_access_token(user_id)
    if not access_token:
        await ctx.send(f"❌ **Lỗi:** Không tìm thấy mã ủy quyền cho người dùng này.")
        return
    try:
        user_to_add = await bot.fetch_user(user_id)
    except discord.NotFound:
        await ctx.send(f"❌ Lỗi: Không tìm thấy người dùng có ID `{user_id}`.")
        return
    success_count = 0
    fail_count = 0
    for guild in bot.guilds:
        success, message = await add_member_to_guild(guild.id, user_id, access_token)
        if success:
            print(f"👍 Thêm thành công {user_to_add.name} vào server {guild.name}: {message}")
            success_count += 1
        else:
            print(f"👎 Lỗi khi thêm vào {guild.name}: {message}")
            fail_count += 1
    await ctx.send(f"\n--- **HOÀN TẤT** --- \n✅ Thêm thành công vào **{success_count}** server.\n❌ Thất bại ở **{fail_count}** server.")

# ==============================================================================
# PHẦN 2: HTML/CSS VÀ WEB SERVER
# ==============================================================================

# --- Nội dung CSS được nhúng vào đây ---
CSS_CONTENT = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
    body {
        font-family: 'Roboto', sans-serif;
        background-color: #36393f;
        color: #dcddde;
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        margin: 0;
        text-align: center;
    }
    .container {
        background-color: #2f3136;
        padding: 40px;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        max-width: 500px;
        width: 90%;
    }
    h1 { color: #ffffff; margin-bottom: 20px; }
    p { font-size: 1.1em; line-height: 1.6; }
    .button {
        display: inline-block;
        background-color: #5865F2;
        color: #ffffff;
        padding: 15px 30px;
        text-decoration: none;
        font-weight: bold;
        border-radius: 5px;
        margin-top: 25px;
        transition: background-color 0.3s ease;
        font-size: 1.2em;
    }
    .button:hover { background-color: #4752C4; }
    .success-icon { font-size: 50px; color: #43b581; }
    .error-icon { font-size: 50px; color: #f04747; }
    .username { font-weight: bold; color: #5865F2; }
</style>
"""

# --- Các template HTML dưới dạng chuỗi f-string ---
def get_index_page(auth_url):
    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ủy quyền Bot</title>
        {CSS_CONTENT}
    </head>
    <body>
        <div class="container">
            <h1>Chào mừng đến với Trang Ủy Quyền</h1>
            <p>Để sử dụng các tính năng của bot, vui lòng đăng nhập và cấp quyền bằng tài khoản Discord của bạn.</p>
            <a href="{auth_url}" class="button">Đăng nhập với Discord</a>
        </div>
    </body>
    </html>
    """

def get_success_page(username):
    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Thành công!</title>
        {CSS_CONTENT}
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✓</div>
            <h1>Ủy quyền thành công!</h1>
            <p>Cảm ơn <span class="username">{username}</span>, bạn đã cấp quyền cho bot. Bây giờ bạn có thể đóng trang này.</p>
        </div>
    </body>
    </html>
    """

def get_error_page(error_message):
    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Có lỗi xảy ra</title>
        {CSS_CONTENT}
    </head>
    <body>
        <div class="container">
            <div class="error-icon">✗</div>
            <h1>Đã có lỗi xảy ra</h1>
            <p>Không thể hoàn tất quá trình ủy quyền. Vui lòng thử lại sau.</p>
            <p><em>Chi tiết lỗi: {error_message}</em></p>
        </div>
    </body>
    </html>
    """

# --- Code Web Server ---
app = Flask(__name__)

@app.route('/')
def index():
    base_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://127.0.0.1:5000')
    redirect_uri = f"{base_url}/callback"
    auth_url = (
        f'https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}'
        f'&redirect_uri={redirect_uri}&response_type=code&scope=identify%20guilds.join'
    )
    return get_index_page(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    base_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://127.0.0.1:5000')
    redirect_uri = f"{base_url}/callback"

    token_url = 'https://discord.com/api/v10/oauth2/token'
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        token_response = requests.post(token_url, data=payload, headers=headers)
        token_response.raise_for_status()
        token_data = token_response.json()
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi gọi API token: {e}")
        return get_error_page("Không thể kết nối đến máy chủ Discord.")

    access_token = token_data.get('access_token')
    if not access_token:
        error_details = token_data.get('error_description', 'Không có chi tiết.')
        return get_error_page(f"Không thể lấy access token. Phản hồi: {error_details}")

    user_info_url = 'https://discord.com/api/v10/users/@me'
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        user_response = requests.get(user_info_url, headers=headers)
        user_response.raise_for_status()
        user_data = user_response.json()
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi gọi API người dùng: {e}")
        return get_error_page("Không thể lấy thông tin người dùng từ Discord.")
        
    user_id = user_data['id']
    username = user_data['username']
    
    try:
        with open('tokens.json', 'r') as f:
            tokens = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        tokens = {}
        
    tokens[user_id] = access_token
    
    with open('tokens.json', 'w') as f:
        json.dump(tokens, f, indent=4)
        
    return get_success_page(username)

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==============================================================================
# PHẦN 3: CHẠY CẢ HAI
# ==============================================================================
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print(">>> Web server đã khởi động trong luồng nền.")

    print(">>> Đang khởi động bot Discord...")
    bot.run(TOKEN)

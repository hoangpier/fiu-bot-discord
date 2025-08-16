import discum
import threading
import time
import os
from keep_alive import keep_alive

accounts = [
    {"token": os.getenv("TOKEN1"), "channel_id": os.getenv("CHANNEL_ID")},
    {"token": os.getenv("TOKEN2"), "channel_id": os.getenv("CHANNEL_ID")},
    {"token": os.getenv("TOKEN3"), "channel_id": os.getenv("CHANNEL_ID")},
    {"token": os.getenv("TOKEN4"), "channel_id": os.getenv("CHANNEL_ID")},
    {"token": os.getenv("TOKEN5"), "channel_id": os.getenv("CHANNEL_ID")},
    {"token": os.getenv("TOKEN6"), "channel_id": os.getenv("CHANNEL_ID")},
]

karuta_id = "646937666251915264"
ktb_channel_id = os.getenv("KTB_CHANNEL_ID")
fixed_emojis = ["1️⃣", "2️⃣", "3️⃣", "1️⃣", "2️⃣", "3️⃣"]

bots = []

def create_bot(account, emoji, grab_time):
    bot = discum.Client(token=account["token"], log=False)

    @bot.gateway.command
    def on_ready(resp):
        if resp.event.ready:
            try:
                user_id = resp.raw["user"]["id"]
                print(f"[{account['channel_id']}] → Đăng nhập với user_id: {user_id}")
            except Exception as e:
                print(f"Lỗi lấy user_id từ ready: {e}")

    @bot.gateway.command
    def on_message(resp):
        if resp.event.message:
            msg = resp.parsed.auto()
            author = msg.get("author", {}).get("id")
            content = msg.get("content", "")
            if author == karuta_id and "is dropping 3 cards!" in content:
                if msg.get("channel_id") == str(account["channel_id"]):
                    threading.Thread(target=react_and_message, args=(bot, msg, emoji, grab_time, account)).start()

    bots.append(bot)
    threading.Thread(target=run_bot, args=(bot, account), daemon=True).start()

def react_and_message(bot, msg, emoji, grab_time, account):
    time.sleep(grab_time)
    try:
        bot.addReaction(msg["channel_id"], msg["id"], emoji)
        print(f"[{account['channel_id']}] → Thả reaction {emoji}")
    except Exception as e:
        print(f"[{account['channel_id']}] → Lỗi thả reaction: {e}")
        time.sleep(2)
    try:
        bot.sendMessage(ktb_channel_id, "kt b")
        print(f"[{account['channel_id']}] → Nhắn 'kt b' ở kênh riêng")
    except Exception as e:
        print(f"[{account['channel_id']}] → Lỗi nhắn kt b: {e}")

def run_bot(bot, account):
    while True:
        try:
            bot.gateway.run(auto_reconnect=True)
        except Exception as e:
            print(f"[{account['channel_id']}] → Bot lỗi, thử kết nối lại: {e}")
        time.sleep(5)

def drop_loop():
    acc_count = len(accounts)
    i = 0
    while True:
        acc = accounts[i % acc_count]
        try:
            bots[i % acc_count].sendMessage(str(acc["channel_id"]), "kd")
            print(f"[{acc['channel_id']}] → Gửi lệnh k!d từ acc thứ {i % acc_count + 1}")
        except Exception as e:
            print(f"[{acc['channel_id']}] → Drop lỗi: {e}")
        i += 1
        time.sleep(305)

keep_alive()

# Gán thời gian grab cho từng acc
grab_times = [1.3, 2.3, 3.2, 1.3, 2.3, 3.2]

for i, acc in enumerate(accounts):
    emoji = fixed_emojis[i % len(fixed_emojis)]
    grab_time = grab_times[i]
    create_bot(acc, emoji, grab_time)

threading.Thread(target=drop_loop, daemon=True).start()

while True:
    time.sleep(60)

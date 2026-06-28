import urllib.request
import urllib.parse
import json
import time
import string
import random
import os
import sys
from datetime import datetime, timedelta

# Default variables
BOT_TOKEN = ""
ADMIN_CHAT_ID = ""
db = None
firebase_initialized = False

# Load Telegram Config
config_path = "telegram_config.json"
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            BOT_TOKEN = config.get("bot_token", "").strip()
            ADMIN_CHAT_ID = str(config.get("admin_chat_id", "")).strip()
    except Exception as e:
        print("Gagal membaca telegram_config.json:", e)

# Try initializing Firebase Admin SDK
try:
    if os.path.exists("serviceAccountKey.json"):
        import firebase_admin
        from firebase_admin import credentials, firestore
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        firebase_initialized = True
        print("Firebase Admin SDK terhubung dengan sukses.")
    else:
        print("Peringatan: serviceAccountKey.json tidak ditemukan. Koneksi Firebase gagal.")
except Exception as e:
    print("Error initializing Firebase Admin SDK:", e)

def get_updates(offset=None):
    if not BOT_TOKEN or "TOKEN" in BOT_TOKEN or not BOT_TOKEN.strip():
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    if offset:
        url += f"?offset={offset}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print("Error getting updates:", e)
        return None

def send_message(chat_id, text):
    if not BOT_TOKEN or "TOKEN" in BOT_TOKEN or not BOT_TOKEN.strip():
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return True
    except Exception as e:
        print("Error sending message:", e)
        return False

def generate_key():
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(random.choices(chars, k=4)) for _ in range(3)]
    return "BAMZ-" + '-'.join(parts)

def calculate_expiry(duration_code):
    now = datetime.now()
    if duration_code == "1m":
        exp = now + timedelta(days=30)
        return exp.strftime("%Y-%m-%d"), "1 Bulan"
    elif duration_code == "6m":
        exp = now + timedelta(days=180)
        return exp.strftime("%Y-%m-%d"), "6 Bulan"
    elif duration_code == "1y":
        exp = now + timedelta(days=365)
        return exp.strftime("%Y-%m-%d"), "1 Tahun"
    elif duration_code == "lifetime":
        # 100 Tahun
        exp = now + timedelta(days=36500)
        return exp.strftime("%Y-%m-%d"), "Lifetime (Lifetime)"
    return None, None

def process_message(msg):
    chat = msg.get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = msg.get("text", "").strip()
    
    if not text:
        return
        
    print(f"Pesan masuk dari Chat ID {chat_id}: {text}")
    
    # Handle /start command (allows user to see their chat id easily)
    if text.startswith("/start"):
        welcome_text = (
            "🤖 *Bamz Downloader - License Generator Bot*\n\n"
            "Selamat datang! Bot ini terhubung ke database Firestore Anda.\n"
            "Gunakan perintah berikut untuk membuat lisensi baru:\n\n"
            "🔑 *Perintah Generator:*\n"
            "• `/gen 1m` - Lisensi 1 Bulan\n"
            "• `/gen 6m` - Lisensi 6 Bulan\n"
            "• `/gen 1y` - Lisensi 1 Tahun\n"
            "• `/gen lifetime` - Lisensi Lifetime\n\n"
            f"ℹ️ *Info:* Hanya ID Telegram Admin terdaftar yang dapat menggunakan bot ini.\n"
            f"ID Anda saat ini: `{chat_id}`"
        )
        send_message(chat_id, welcome_text)
        return
        
    # Check authorization
    if chat_id != ADMIN_CHAT_ID:
        send_message(chat_id, f"❌ *Akses Ditolak!*\n\nID Telegram Anda (`{chat_id}`) tidak terdaftar sebagai Admin di `telegram_config.json`.")
        return
        
    # Process /gen command
    if text.startswith("/gen"):
        parts = text.split()
        if len(parts) < 2:
            send_message(chat_id, "⚠️ *Format Salah!*\n\nGunakan perintah: `/gen [1m/6m/1y/lifetime]`")
            return
            
        duration_code = parts[1].lower()
        expiry_date, duration_display = calculate_expiry(duration_code)
        
        if not expiry_date:
            send_message(chat_id, "⚠️ *Pilihan Durasi Salah!*\n\nPilihan yang tersedia:\n• `1m` (1 Bulan)\n• `6m` (6 Bulan)\n• `1y` (1 Tahun)\n• `lifetime` (Lifetime)")
            return
            
        if not firebase_initialized or not db:
            send_message(chat_id, "❌ *Koneksi Firebase Gagal!*\n\nDatabase Firebase tidak terhubung di server bot. Pastikan `serviceAccountKey.json` terpasang dengan benar di folder aplikasi.")
            return
            
        # Generate Key
        new_key = generate_key()
        
        try:
            # Tulis ke Firestore
            doc_ref = db.collection("licenses").document(new_key)
            doc_ref.set({
                "duration": duration_display,
                "expiry_date": expiry_date,
                "hwid": "",
                "is_active": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Balas dengan Serial Key yang terbuat
            success_text = (
                "✅ *Lisensi Berhasil Dibuat!*\n\n"
                "🔑 *Serial Key:*\n"
                f"`{new_key}`\n\n"
                "📅 *Detail Lisensi:*\n"
                f"• Durasi: *{duration_display}*\n"
                f"• Kedaluwarsa: *{expiry_date}*\n"
                f"• Status: *Siap Aktivasi (Bebas HWID)*\n\n"
                f"_Silakan salin serial key di atas untuk dikirim ke pembeli._"
            )
            send_message(chat_id, success_text)
            print(f"Sukses generate key {new_key} durasi {duration_display}")
        except Exception as err:
            send_message(chat_id, f"❌ *Gagal menyimpan ke Firestore:*\n\n{err}")
            print(f"Error saving to Firestore: {err}")

def main():
    print("====================================================")
    print("🤖 BAMZ TELEGRAM LICENSE GENERATOR BOT RUNNING...")
    print("====================================================")
    print(f"Bot Token     : {'TERPASANG' if BOT_TOKEN and 'TOKEN' not in BOT_TOKEN and BOT_TOKEN.strip() else 'KOSONG / BELUM DIKONFIGURASI'}")
    print(f"Admin Chat ID : {ADMIN_CHAT_ID if ADMIN_CHAT_ID and 'CHAT_ID' not in ADMIN_CHAT_ID and ADMIN_CHAT_ID.strip() else 'KOSONG / BELUM DIKONFIGURASI'}")
    print("====================================================")
    
    if not BOT_TOKEN or "TOKEN" in BOT_TOKEN or not BOT_TOKEN.strip():
        print("Peringatan: Harap isi bot_token di telegram_config.json terlebih dahulu!")
        
    offset = None
    while True:
        try:
            updates = get_updates(offset)
            if updates and updates.get("ok"):
                result = updates.get("result", [])
                for update in result:
                    update_id = update.get("update_id")
                    offset = update_id + 1
                    
                    if "message" in update:
                        process_message(update["message"])
            
        except KeyboardInterrupt:
            print("\nBot dimatikan oleh Admin.")
            break
        except Exception as e:
            print("Loop Error:", e)
            
        time.sleep(1)

if __name__ == '__main__':
    main()

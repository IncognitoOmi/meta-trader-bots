import requests
from datetime import datetime
import pytz

# ================= CONFIG =================
BOT_TOKEN = "7699036883:AAEh1PxEVSoqaYyto0E1yByjgxC4q5mLeJw"
CHAT_ID = "1155443179"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": CHAT_ID, "text": message})
        if response.status_code == 200:
            print("✅ Telegram alert sent successfully!")
        else:
            print(f"❌ Telegram Error: {response.text}")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def force_test_alert():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    target_currencies = ["USD", "AUD", "EUR", "GBP"]
    
    print("⏳ Fetching real news to force an alert...\n")
    try:
        resp = requests.get(url)
        # Filter High Impact and target currencies
        news_data = [n for n in resp.json() if n.get("country") in target_currencies and n.get("impact") == "High"]
        
        if not news_data:
            print("Koi Red Folder news nahi mili is hafte ki list mein.")
            return
        
        # Pura list me se sabse pehli news utha li testing ke liye
        recent_news = news_data[0] 
        
        # Force Message
        msg = (f"🧪 FORCE TEST ALERT 🧪\n\n"
               f"Currency: {recent_news['country']}\n"
               f"Event: {recent_news['title']}\n"
               f"Original Time: {recent_news['date']}\n\n"
               f"Yeh sirf check karne ke liye hai ki real data fetch hokar Telegram par aa raha hai.")
        
        send_telegram(msg)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    force_test_alert()
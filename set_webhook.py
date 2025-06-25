import requests

BOT_TOKEN = "7795558482:AAE8WEmzTJqQkfSLKUPXjVK40QIUC2mitYg"
WEBHOOK_URL = "https://my-ai-bot-la8u.onrender.com/webhook"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
r = requests.post(url, data={"url": WEBHOOK_URL})
print(r.json())
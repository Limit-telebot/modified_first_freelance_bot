import os
from dotenv import load_dotenv

load_dotenv("env_file.env")

ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DASHBOARD_LINK = os.environ.get("DASHBOARD_LINK", "")
VIP_CHANNEL_ID = os.environ.get("VIP_CHANNEL_ID", "")

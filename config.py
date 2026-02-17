import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

# PirateSwap API Configuration
PIRATESWAP_API = 'https://web.pirateswap.com/inventory/Exchangerinventory'
SCAN_INTERVAL = 300  # 5 minutes in seconds
PAGES_TO_SCAN = 2
RESULTS_PER_PAGE = 50

# Database Configuration
DB_NAME = 'pirateswap_tracker.db'

import telebot
import logging
import threading
import time
from flask import Flask, request
from config import BOT_TOKEN, ADMIN_CHAT_ID
from database import Database
from parser import PirateSwapParser
from filters import ItemFilter
from config import SCAN_INTERVAL, DB_NAME
import os
import sys

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Check tokens
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not set!")
    exit(1)

logger.info("✅ Configuration loaded")

# Initialize Flask
app = Flask(__name__)

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
logger.info("✅ Bot initialized")

# Initialize database
try:
    db = Database(DB_NAME)
    logger.info("✅ Database initialized")
except Exception as e:
    logger.error(f"❌ Database init failed: {e}")
    exit(1)

# Initialize parser
try:
    parser = PirateSwapParser()
    logger.info("✅ Parser initialized")
except Exception as e:
    logger.error(f"❌ Parser init failed: {e}")
    exit(1)

# User states
user_states = {}
PORT = int(os.getenv('PORT', 5000))

logger.info(f"✅ PORT: {PORT}")

# ==================== KEYBOARD ====================

def get_main_keyboard():
    """Main menu keyboard"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row('🚀 Старт', '➕ Добавить скин')
    markup.row('📋 Мои поиски')
    return markup

# ==================== FLASK ROUTES ====================

@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok'}, 200

@app.route('/', methods=['GET', 'POST'])
def index():
    return {'status': 'ok'}, 200

# ==================== BOT HANDLERS ====================

@bot.message_handler(commands=['start'])
def cmd_start(message):
    """Handle /start"""
    user_id = message.chat.id
    logger.info(f"👤 /start from user {user_id}")
    
    text = (
        "🎮 <b>PirateSwap Tracker Bot</b>\n\n"
        "<b>Возможности:</b>\n"
        "🔍 Отслеживает скины на pirateswap.com\n"
        "📢 Отправляет уведомления о находках\n"
        "💰 Показывает цену и float\n"
        "🔗 Ссылка для осмотра\n\n"
        "<b>Начало работы:</b>\n"
        "1️⃣ Нажми '➕ Добавить скин'\n"
        "2️⃣ Укажи название скина\n"
        "3️⃣ Выбери нужны ли брелоки\n"
        "4️⃣ Жди уведомления!"
    )
    
    try:
        bot.send_message(user_id, text, reply_markup=get_main_keyboard())
        logger.info(f"✅ Start message sent to {user_id}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def btn_start(message):
    """Start button"""
    cmd_start(message)

@bot.message_handler(func=lambda m: m.text == '➕ Добавить скин')
def btn_add_skin(message):
    """Add skin button"""
    user_id = message.chat.id
    logger.info(f"➕ Add skin from {user_id}")
    
    user_states[user_id] = {'step': 'skin_name'}
    bot.send_message(user_id, "🎯 Введи название скина:\n(например: AK-47, Dragon Lore)")
    logger.info(f"✅ Waiting for skin name from {user_id}")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'skin_name')
def process_skin_name(message):
    """Process skin name"""
    user_id = message.chat.id
    text = message.text
    
    if not text or len(text) < 2:
        bot.send_message(user_id, "❌ Название слишком короткое (минимум 2 символа)")
        return
    
    logger.info(f"📝 Skin name: {text}")
    user_states[user_id] = {'step': 'charm_choice', 'skin_name': text}
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton('✨ Да', callback_data='charm_yes'),
        telebot.types.InlineKeyboardButton('❌ Нет', callback_data='charm_no')
    )
    
    bot.send_message(user_id, f"🎨 Нужен брелок?\n\nСкин: <b>{text}</b>", reply_markup=markup)
    logger.info(f"✅ Asking for charm choice from {user_id}")

@bot.callback_query_handler(func=lambda call: call.data in ['charm_yes', 'charm_no'])
def process_charm(call):
    """Process charm choice"""
    user_id = call.message.chat.id
    logger.info(f"🎨 Charm choice: {call.data}")
    
    if user_id not in user_states or user_states[user_id].get('step') != 'charm_choice':
        bot.answer_callback_query(call.id, "❌ Сессия истекла", show_alert=True)
        return
    
    charm = 1 if call.data == 'charm_yes' else 0
    skin_name = user_states[user_id].get('skin_name', '')
    
    try:
        if db.add_search(user_id, skin_name, charm):
            charm_text = "Да ✨" if charm else "Нет"
            msg = f"✅ Поиск добавлен!\n\nСкин: <b>{skin_name}</b>\nБрелок: {charm_text}"
            bot.send_message(user_id, msg, reply_markup=get_main_keyboard())
            logger.info(f"✅ Search added for {user_id}: {skin_name}")
            del user_states[user_id]
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, "❌ Такой поиск уже есть", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Error adding search: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)

@bot.message_handler(func=lambda m: m.text == '📋 Мои поиски')
def btn_my_searches(message):
    """Show searches"""
    user_id = message.chat.id
    logger.info(f"📋 Show searches for {user_id}")
    
    try:
        searches = db.get_user_searches(user_id)
        
        if not searches:
            bot.send_message(user_id, "📭 Нет поисков\n\nНажми '➕ Добавить скин'", reply_markup=get_main_keyboard())
            return
        
        text = "📋 <b>Ваши поиски:</b>\n\n"
        markup = telebot.types.InlineKeyboardMarkup()
        
        for sid, sname, scharm in searches:
            charm_emoji = "✨" if scharm else "❌"
            text += f"• <b>{sname}</b> {charm_emoji}\n"
            markup.add(telebot.types.InlineKeyboardButton(f"🗑 {sname}", callback_data=f"del_{sid}"))
        
        bot.send_message(user_id, text, reply_markup=markup)
        logger.info(f"✅ Searches sent to {user_id}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        bot.send_message(user_id, "❌ Ошибка")

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_search(call):
    """Delete search"""
    user_id = call.message.chat.id
    try:
        sid = int(call.data.split('_')[1])
        logger.info(f"🗑 Delete search {sid}")
        
        if db.delete_search(sid):
            bot.edit_message_text("🗑 Удалено", user_id, call.message.message_id)
            bot.answer_callback_query(call.id)
            logger.info(f"✅ Search deleted")
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)

@bot.message_handler(func=lambda m: True)
def default_handler(message):
    """Default handler"""
    user_id = message.chat.id
    text = message.text if message.text else "[no text]"
    logger.info(f"💬 Message from {user_id}: {text}")
    bot.send_message(user_id, "👋 Используй кнопки внизу", reply_markup=get_main_keyboard())

# ==================== NOTIFICATIONS ====================

def send_notifications(matches):
    """Send notifications"""
    logger.info(f"📤 Sending {len(matches)} notifications...")
    
    for match in matches:
        try:
            user_id = match['user_id']
            charm_text = "Да ✨" if match['has_keychains'] else "Нет"
            
            msg = (
                f"🎉 <b>Найден скин!</b>\n\n"
                f"<b>Название:</b> {match['market_hash_name']}\n"
                f"<b>Цена:</b> ${match['price']}\n"
                f"<b>Float:</b> {match['float']:.6f}\n"
                f"<b>Брелоки:</b> {charm_text}\n\n"
            )
            
            if match.get('inspect_link'):
                msg += f"<a href='{match['inspect_link']}'>Осмотреть</a>"
            
            bot.send_message(user_id, msg)
            logger.info(f"✅ Notification to {user_id}")
        except Exception as e:
            logger.error(f"❌ Error: {e}")

# ==================== SCANNER ====================

def background_scanner():
    """Background scanner thread"""
    logger.info("🔄 Scanner started")
    
    while True:
        try:
            logger.info("🔍 Scanning...")
            
            items = parser.get_all_items()
            logger.info(f"📥 {len(items)} items fetched")
            
            if items:
                user_searches = db.get_all_searches()
                logger.info(f"🔎 {len(user_searches)} active searches")
                
                if user_searches:
                    matches = ItemFilter.filter_items(items, user_searches, db)
                    logger.info(f"✨ {len(matches)} matches found")
                    
                    if matches:
                        send_notifications(matches)
            
            time.sleep(SCAN_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Scanner error: {e}")
            time.sleep(SCAN_INTERVAL)

# ==================== MAIN ====================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 PirateSwap Tracker Bot starting...")
    logger.info("=" * 60)
    
    # Start scanner thread
    scanner_thread = threading.Thread(target=background_scanner, daemon=True)
    scanner_thread.start()
    logger.info("✅ Scanner thread started")
    
    # Start Flask in thread
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    logger.info(f"✅ Flask started on port {PORT}")
    
    # Start polling
    logger.info("=" * 60)
    logger.info("📡 Bot polling started - waiting for messages...")
    logger.info("=" * 60)
    
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
    except Exception as e:
        logger.error(f"❌ Polling error: {e}")

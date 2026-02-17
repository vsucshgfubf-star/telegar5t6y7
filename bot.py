import telebot
import logging
import threading
import time
from flask import Flask, request
from config import BOT_TOKEN, ADMIN_CHAT_ID, DB_NAME
from database import Database
from parser import PirateSwapParser
from filters import ItemFilter
from config import SCAN_INTERVAL
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

# Verify tokens
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is not set in environment variables!")
    exit(1)

if not ADMIN_CHAT_ID:
    logger.error("❌ ADMIN_CHAT_ID is not set in environment variables!")
    exit(1)

logger.info("✅ BOT_TOKEN loaded successfully")
logger.info(f"✅ ADMIN_CHAT_ID loaded: {ADMIN_CHAT_ID}")

# Initialize Flask app
app = Flask(__name__)
logger.info("✅ Flask app initialized")

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
logger.info("✅ Telegram bot initialized")

# Initialize database and parser
try:
    db = Database(DB_NAME)
    logger.info("✅ Database initialized")
except Exception as e:
    logger.error(f"❌ Database init failed: {e}")
    exit(1)

try:
    parser = PirateSwapParser()
    logger.info("✅ PirateSwap parser initialized")
except Exception as e:
    logger.error(f"❌ Parser init failed: {e}")
    exit(1)

# State management for user conversations
user_states = {}

# Get port from environment
PORT = int(os.getenv('PORT', 5000))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Должен быть типа https://yourdomain.com/webhook

if not WEBHOOK_URL:
    logger.warning("⚠️ WEBHOOK_URL не задан. Использовать polling локально.")

logger.info(f"✅ PORT: {PORT}")

# Main keyboard
def get_main_keyboard():
    """Create main menu keyboard"""
    logger.debug("Creating main keyboard")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row('🚀 Старт', '➕ Добавить скин')
    markup.row('📋 Мои поиски')
    return markup

# ==================== FLASK HEALTH ENDPOINTS ====================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    logger.debug("Health check requested")
    return {'status': 'ok'}, 200

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    logger.info("GET request to root")
    return {'status': 'Bot is running'}, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook handler"""
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    logger.info("✅ Webhook update processed")
    return '', 200

# ==================== BOT MESSAGE HANDLERS ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command"""
    user_id = message.chat.id
    logger.info(f"🔥 /START COMMAND FROM USER {user_id}")
    
    welcome_text = (
        "🎮 <b>PirateSwap Tracker Bot</b>\n\n"
        "<b>Что делает бот:</b>\n"
        "🔍 Отслеживает новые скины на pirateswap.com\n"
        "📢 Отправляет уведомления о найденных скинах\n"
        "💰 Показывает цену и float значения\n"
        "🔗 Предоставляет ссылку для осмотра в игре\n\n"
        "<b>Как начать:</b>\n"
        "1️⃣ Нажми '<b>➕ Добавить скин</b>'\n"
        "2️⃣ Введи название скина\n"
        "3️⃣ Выбери, нужны ли брелоки\n"
        "4️⃣ Жди уведомления!\n\n"
        "<b>Как приходят уведомления:</b>\n"
        "📬 Бот сканирует PirateSwap каждые 5 минут\n"
        "🎯 При совпадении с твоим поиском ты получишь сообщение\n"
        "✅ В сообщении будут все данные о скине"
    )
    
    try:
        msg = bot.send_message(
            user_id, 
            welcome_text, 
            reply_markup=get_main_keyboard()
        )
        logger.info(f"✅ Start message sent to user {user_id}, message_id: {msg.message_id}")
    except Exception as e:
        logger.error(f"❌ Error sending start message to {user_id}: {e}", exc_info=True)

@bot.message_handler(func=lambda message: message.text == '🚀 Старт')
def start_button(message):
    """Handle Start button"""
    start_command(message)

@bot.message_handler(func=lambda message: message.text == '➕ Добавить скин')
def add_skin_start(message):
    """Start skin addition process"""
    user_id = message.chat.id
    logger.info(f"📌 Add skin button pressed by user {user_id}")
    
    user_states[user_id] = {'step': 'waiting_skin_name'}
    
    try:
        msg = bot.send_message(
            user_id,
            "🎯 <b>Какой скин хотите отслеживать?</b>\n\n"
            "<i>Введите название или часть названия скина:</i>\n"
            "Например: <code>AK-47</code> или <code>Dragon Lore</code>",
            reply_markup=telebot.types.ForceReply()
        )
        logger.info(f"✅ Skin name request sent to user {user_id}")
    except Exception as e:
        logger.error(f"❌ Error requesting skin name from {user_id}: {e}")
        if user_id in user_states:
            del user_states[user_id]

@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('step') == 'waiting_skin_name')
def process_skin_name(message):
    """Process skin name input"""
    user_id = message.chat.id
    skin_name = message.text.strip()
    
    logger.info(f"📝 Skin name input from user {user_id}: '{skin_name}'")
    
    if not skin_name or len(skin_name) < 2:
        logger.warning(f"❌ Invalid skin name length from {user_id}")
        bot.send_message(user_id, "❌ Название скина слишком короткое. Пожалуйста, введите минимум 2 символа.")
        return
    
    user_states[user_id]['skin_name'] = skin_name
    user_states[user_id]['step'] = 'waiting_charm_choice'
    
    # Inline keyboard for charm selection
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton('✨ Добавить брелок', callback_data='charm_yes'),
        telebot.types.InlineKeyboardButton('❌ Без брелока', callback_data='charm_no')
    )
    
    try:
        msg = bot.send_message(
            user_id,
            f"🎨 <b>Нужен брелок для этого скина?</b>\n\n"
            f"<b>Скин:</b> {skin_name}",
            reply_markup=markup
        )
        logger.info(f"✅ Charm choice prompt sent to user {user_id}")
    except Exception as e:
        logger.error(f"❌ Error sending charm choice to {user_id}: {e}")
        if user_id in user_states:
            del user_states[user_id]

@bot.callback_query_handler(func=lambda call: call.data in ['charm_yes', 'charm_no'])
def process_charm_choice(call):
    """Process charm/keychain choice"""
    user_id = call.message.chat.id
    call_id = call.id
    
    logger.info(f"📌 Charm choice callback from user {user_id}: {call.data}")
    
    if user_id not in user_states or user_states[user_id].get('step') != 'waiting_charm_choice':
        logger.warning(f"❌ Invalid state for user {user_id}")
        bot.answer_callback_query(call_id, "❌ Сессия истекла. Начните заново.", show_alert=True)
        return
    
    charm_required = 1 if call.data == 'charm_yes' else 0
    skin_name = user_states[user_id]['skin_name']
    
    # Save to database
    try:
        if db.add_search(user_id, skin_name, charm_required):
            charm_text = "Да ✨" if charm_required else "Нет"
            confirmation = (
                f"✅ <b>Поиск добавлен!</b>\n\n"
                f"<b>Название:</b> {skin_name}\n"
                f"<b>Брелок:</b> {charm_text}"
            )
            
            msg = bot.send_message(user_id, confirmation, reply_markup=get_main_keyboard())
            logger.info(f"✅ Search added for user {user_id}: {skin_name} (charm: {charm_required})")
            
            # Clean up state
            del user_states[user_id]
            
            bot.answer_callback_query(call_id, "✅ Поиск успешно добавлен!", show_alert=False)
        else:
            logger.warning(f"❌ Failed to add search for user {user_id}")
            bot.answer_callback_query(
                call_id,
                "❌ Такой поиск уже существует или произошла ошибка",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"❌ Error adding search for {user_id}: {e}", exc_info=True)
        bot.answer_callback_query(call_id, f"❌ Ошибка: {str(e)}", show_alert=True)
        if user_id in user_states:
            del user_states[user_id]

@bot.message_handler(func=lambda message: message.text == '📋 Мои поиски')
def show_searches(message):
    """Show all user searches"""
    user_id = message.chat.id
    logger.info(f"📌 Show searches button pressed by user {user_id}")
    
    try:
        searches = db.get_user_searches(user_id)
        logger.info(f"📋 Found {len(searches)} searches for user {user_id}")
        
        if not searches:
            bot.send_message(
                user_id,
                "📭 <b>У вас нет активных поисков.</b>\n\n"
                "Нажмите '<b>➕ Добавить скин</b>' чтобы начать отслеживание.",
                reply_markup=get_main_keyboard()
            )
            return
        
        response = "📋 <b>Ваши поиски:</b>\n\n"
        markup = telebot.types.InlineKeyboardMarkup()
        
        for search_id, skin_name, charm_required in searches:
            charm_text = "✨ Брелок: Да" if charm_required else "❌ Брелок: Нет"
            response += f"• <b>{skin_name}</b> - {charm_text}\n"
            markup.add(
                telebot.types.InlineKeyboardButton(
                    f"🗑 {skin_name}",
                    callback_data=f"delete_{search_id}"
                )
            )
        
        msg = bot.send_message(user_id, response, reply_markup=markup)
        logger.info(f"✅ Searches list sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error showing searches for {user_id}: {e}", exc_info=True)
        bot.send_message(user_id, f"❌ Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_search(call):
    """Delete search"""
    user_id = call.message.chat.id
    call_id = call.id
    
    try:
        search_id = int(call.data.split('_')[1])
        logger.info(f"🗑 Delete search request from user {user_id}, search_id: {search_id}")
        
        if db.delete_search(search_id):
            bot.answer_callback_query(call_id, "✅ Поиск удалён!", show_alert=False)
            bot.edit_message_text(
                "🗑 <b>Поиск удалён</b>",
                user_id,
                call.message.message_id
            )
            logger.info(f"✅ Search {search_id} deleted for user {user_id}")
        else:
            logger.warning(f"❌ Failed to delete search {search_id} for user {user_id}")
            bot.answer_callback_query(call_id, "❌ Ошибка при удалении", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Error deleting search: {e}", exc_info=True)
        bot.answer_callback_query(call_id, f"❌ Ошибка: {str(e)}", show_alert=True)

@bot.message_handler(func=lambda message: True)
def default_handler(message):
    """Handle all other messages"""
    user_id = message.chat.id
    text = message.text
    logger.info(f"📝 Message from user {user_id}: '{text}'")
    
    try:
        bot.send_message(
            user_id,
            "👋 Привет! Используйте меню внизу для работы с ботом.",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"❌ Error in default handler: {e}")

# ==================== NOTIFICATION SYSTEM ====================

def format_notification(match):
    """Format notification message"""
    has_keychains_text = "Да ✨" if match['has_keychains'] else "Нет"
    
    message = (
        f"🎉 <b>Найден скин!</b>\n\n"
        f"<b>Название:</b> {match['market_hash_name']}\n"
        f"<b>Цена:</b> ${match['price']}\n"
        f"<b>Float:</b> {match['float']:.6f}\n"
        f"<b>Брелоки:</b> {has_keychains_text}\n\n"
    )
    
    if match.get('inspect_link'):
        message += f"<b>Inspect:</b> <a href='{match['inspect_link']}'>Осмотреть в игре</a>"
    
    return message

def send_notifications(matches):
    """Send notifications to users"""
    logger.info(f"📤 Sending {len(matches)} notifications...")
    
    for match in matches:
        try:
            user_id = match['user_id']
            notification = format_notification(match)
            bot.send_message(user_id, notification)
            logger.info(f"✅ Notification sent to user {user_id} for item {match['item_id']}")
        except Exception as e:
            logger.error(f"❌ Error sending notification to user {match['user_id']}: {e}")

# ==================== BACKGROUND SCANNER ====================

def background_scanner():
    """Background thread for scanning PirateSwap"""
    logger.info("🔄 Background scanner started")
    
    while True:
        try:
            logger.info("🔍 Starting scan cycle...")
            
            # Get all items
            items = parser.get_all_items()
            logger.info(f"📥 Fetched {len(items)} items from PirateSwap")
            
            if not items:
                logger.warning("⚠️ No items fetched from API")
                time.sleep(SCAN_INTERVAL)
                continue
            
            # Get all active searches
            user_searches = db.get_all_searches()
            logger.info(f"🔎 Got {len(user_searches)} active searches")
            
            if not user_searches:
                logger.info("ℹ️ No active searches")
                time.sleep(SCAN_INTERVAL)
                continue
            
            # Filter items
            matches = ItemFilter.filter_items(items, user_searches, db)
            logger.info(f"✨ Found {len(matches)} matching items")
            
            if matches:
                send_notifications(matches)
            
            logger.info(f"⏳ Next scan in {SCAN_INTERVAL} seconds...")
            time.sleep(SCAN_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Error in background scanner: {e}", exc_info=True)
            time.sleep(SCAN_INTERVAL)

# ==================== STARTUP ====================

def start_background_thread():
    """Start background scanner thread"""
    scanner_thread = threading.Thread(target=background_scanner, daemon=True)
    scanner_thread.start()
    logger.info("✅ Background scanner thread started")

def start_flask_thread():
    """Start Flask server thread"""
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    logger.info(f"✅ Flask server thread started on port {PORT}")

if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("🚀 Starting PirateSwap Tracker Bot (Webhook Mode)")
    logger.info("=" * 70)
    
    # Start background threads
    start_background_thread()
    start_flask_thread()
    
    # Setup webhook if URL задан
    if WEBHOOK_URL:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
            logger.info(f"✅ Webhook set: {WEBHOOK_URL}/webhook")
        except Exception as e:
            logger.error(f"❌ Failed to set webhook: {e}", exc_info=True)
            exit(1)
    else:
        logger.info("ℹ️ WEBHOOK_URL не задан, используем polling")
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
        except Exception as e:
            logger.error(f"❌ Polling error: {e}", exc_info=True)
            exit(1)

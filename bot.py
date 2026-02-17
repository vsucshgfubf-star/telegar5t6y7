import telebot
import logging
import threading
import time
from flask import Flask, request
from config import BOT_TOKEN, ADMIN_CHAT_ID
from database import Database
from parser import PirateSwapParser
from filters import ItemFilter
from config import SCAN_INTERVAL
import os
import sys
from threading import Lock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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

# Initialize bot - ВАЖНО: используй threading_handler
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)
logger.info("✅ Telegram bot initialized")

# Initialize database and parser
try:
    db = Database()
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

# State management for user conversations with thread-safety
user_states = {}
state_lock = Lock()
STATE_TIMEOUT = 3600  # 1 hour in seconds

# Get port from environment
PORT = int(os.getenv('PORT', 5000))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

logger.info(f"✅ PORT: {PORT}")
if WEBHOOK_URL:
    logger.info(f"✅ WEBHOOK_URL: {WEBHOOK_URL}")

# ==================== STATE MANAGEMENT ====================

def get_user_state(user_id):
    """Get user state with lock"""
    with state_lock:
        return user_states.get(user_id)

def set_user_state(user_id, state):
    """Set user state with lock and timestamp"""
    with state_lock:
        state['created_at'] = time.time()
        user_states[user_id] = state

def delete_user_state(user_id):
    """Delete user state with lock"""
    with state_lock:
        if user_id in user_states:
            del user_states[user_id]

def cleanup_expired_states():
    """Cleanup expired states periodically"""
    logger.info("🧹 State cleanup thread started")
    while True:
        try:
            time.sleep(300)  # Check every 5 minutes
            with state_lock:
                now = time.time()
                expired_users = [
                    uid for uid, state in user_states.items()
                    if now - state.get('created_at', now) > STATE_TIMEOUT
                ]
                for uid in expired_users:
                    del user_states[uid]
                if expired_users:
                    logger.info(f"🧹 Cleaned up {len(expired_users)} expired states")
        except Exception as e:
            logger.error(f"❌ Error in state cleanup: {e}")

# Main keyboard
def get_main_keyboard():
    """Create main menu keyboard"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row('🚀 Старт', '➕ Добавить скин')
    markup.row('📋 Мои поиски')
    return markup

# ==================== WEBHOOK ENDPOINTS ====================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return {'status': 'ok'}, 200

@app.route('/', methods=['POST', 'GET'])
def root():
    """Root endpoint"""
    if request.method == 'GET':
        logger.info("✅ GET request to root - Bot is running")
        return {'status': 'ok', 'message': 'Bot is running'}, 200
    
    logger.debug("POST request to root")
    return handle_webhook()

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook_handler():
    """Main webhook endpoint"""
    logger.debug(f"⚡ Webhook POST to /{BOT_TOKEN}")
    return handle_webhook()

def handle_webhook():
    """Process webhook data - ГЛАВНАЯ ФУНКЦИЯ"""
    try:
        if request.headers.get('content-type') == 'application/json':
            json_data = request.get_json()
            logger.info(f"📨 Webhook JSON received, update_id: {json_data.get('update_id')}")
            
            if json_data:
                update = telebot.types.Update.de_json(json_data)
                logger.info(f"✅ Update parsed, type: message={bool(update.message)}, callback={bool(update.callback_query)}")
                
                if update:
                    # ГЛАВНОЕ: передай обновление боту
                    bot.process_new_updates([update])
                    logger.info(f"✅ Update {update.update_id} processed")
                    return 'OK', 200
        
        logger.warning("⚠️ No JSON data received")
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return 'ERROR', 500

# ==================== BOT HANDLERS ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command"""
    user_id = message.chat.id
    logger.info(f"🔥 /START from user {user_id}")
    
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
        bot.send_message(user_id, welcome_text, reply_markup=get_main_keyboard())
        logger.info(f"✅ Start message sent to {user_id}")
    except Exception as e:
        logger.error(f"❌ Error sending start: {e}", exc_info=True)

@bot.message_handler(func=lambda message: message.text == '🚀 Старт')
def start_button(message):
    """Handle Start button"""
    logger.info(f"🚀 Start button from {message.chat.id}")
    start_command(message)

@bot.message_handler(func=lambda message: message.text == '➕ Добавить скин')
def add_skin_start(message):
    """Start skin addition process"""
    user_id = message.chat.id
    logger.info(f"➕ Add skin from {user_id}")
    
    set_user_state(user_id, {'step': 'waiting_skin_name'})
    
    try:
        bot.send_message(
            user_id,
            "🎯 <b>Какой скин хотите отслеживать?</b>\n\n"
            "<i>Введите название или часть названия:</i>\n"
            "Например: <code>AK-47</code> или <code>Dragon Lore</code>",
            reply_markup=telebot.types.ForceReply()
        )
        logger.info(f"✅ Skin request sent to {user_id}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        delete_user_state(user_id)

@bot.message_handler(func=lambda message: get_user_state(message.chat.id) and 
                     get_user_state(message.chat.id).get('step') == 'waiting_skin_name')
def process_skin_name(message):
    """Process skin name input"""
    user_id = message.chat.id
    text = message.text
    
    if not text:
        logger.warning(f"Empty message from {user_id}")
        bot.send_message(user_id, "❌ Пожалуйста, отправьте текст")
        return
    
    skin_name = text.strip()
    logger.info(f"📝 Skin name from {user_id}: {skin_name}")
    
    if len(skin_name) < 2:
        bot.send_message(user_id, "❌ Слишком короткое название (минимум 2 символа)")
        return
    
    user_state = get_user_state(user_id)
    if user_state:
        user_state['skin_name'] = skin_name
        user_state['step'] = 'waiting_charm_choice'
        set_user_state(user_id, user_state)
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton('✨ Да', callback_data='charm_yes'),
        telebot.types.InlineKeyboardButton('❌ Нет', callback_data='charm_no')
    )
    
    try:
        bot.send_message(
            user_id,
            f"🎨 <b>Нужен брелок?</b>\n\n<b>Скин:</b> {skin_name}",
            reply_markup=markup
        )
        logger.info(f"✅ Charm choice sent to {user_id}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        delete_user_state(user_id)

@bot.callback_query_handler(func=lambda call: call.data in ['charm_yes', 'charm_no'])
def process_charm_choice(call):
    """Process charm choice"""
    user_id = call.message.chat.id
    call_id = call.id
    
    logger.info(f"🎨 Charm choice from {user_id}: {call.data}")
    
    user_state = get_user_state(user_id)
    if not user_state or user_state.get('step') != 'waiting_charm_choice':
        logger.warning(f"Invalid state for {user_id}")
        bot.answer_callback_query(call_id, "❌ Сессия истекла", show_alert=True)
        return
    
    charm_required = 1 if call.data == 'charm_yes' else 0
    skin_name = user_state.get('skin_name', '')
    
    try:
        if db.add_search(user_id, skin_name, charm_required):
            charm_text = "Да ✨" if charm_required else "Нет ❌"
            confirmation = (
                f"✅ <b>Поиск добавлен!</b>\n\n"
                f"<b>Скин:</b> {skin_name}\n"
                f"<b>Брелок:</b> {charm_text}"
            )
            
            bot.send_message(user_id, confirmation, reply_markup=get_main_keyboard())
            logger.info(f"✅ Search added: {skin_name} for {user_id}")
            delete_user_state(user_id)
            bot.answer_callback_query(call_id, "✅ Успешно!", show_alert=False)
        else:
            logger.warning(f"Failed to add search for {user_id}")
            bot.answer_callback_query(call_id, "❌ Ошибка добавления", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        bot.answer_callback_query(call_id, "❌ Ошибка", show_alert=True)
        delete_user_state(user_id)

@bot.message_handler(func=lambda message: message.text == '📋 Мои поиски')
def show_searches(message):
    """Show user searches"""
    user_id = message.chat.id
    logger.info(f"📋 Show searches from {user_id}")
    
    try:
        searches = db.get_user_searches(user_id)
        logger.info(f"Found {len(searches)} searches for {user_id}")
        
        if not searches:
            bot.send_message(
                user_id,
                "📭 <b>Нет активных поисков</b>\n\n"
                "Нажмите '➕ Добавить скин'",
                reply_markup=get_main_keyboard()
            )
            return
        
        response = "📋 <b>Ваши поиски:</b>\n\n"
        markup = telebot.types.InlineKeyboardMarkup()
        
        for search_id, skin_name, charm_required in searches:
            charm_text = "✨" if charm_required else "❌"
            response += f"• <b>{skin_name}</b> {charm_text}\n"
            markup.add(telebot.types.InlineKeyboardButton(f"🗑 {skin_name}", callback_data=f"delete_{search_id}"))
        
        bot.send_message(user_id, response, reply_markup=markup)
        logger.info(f"✅ Searches list sent to {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        bot.send_message(user_id, "❌ Ошибка")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_search(call):
    """Delete search"""
    user_id = call.message.chat.id
    call_id = call.id
    
    try:
        search_id = int(call.data.split('_')[1])
        logger.info(f"🗑 Delete {search_id} from {user_id}")
        
        if db.delete_search(search_id):
            bot.answer_callback_query(call_id, "✅ Удалено!", show_alert=False)
            bot.edit_message_text("🗑 <b>Удалено</b>", user_id, call.message.message_id)
            logger.info(f"✅ Search {search_id} deleted")
        else:
            bot.answer_callback_query(call_id, "❌ Ошибка", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        bot.answer_callback_query(call_id, "❌ Ошибка", show_alert=True)

@bot.message_handler(func=lambda message: True)
def default_handler(message):
    """Handle other messages"""
    user_id = message.chat.id
    text = message.text if message.text else "[No text]"
    logger.info(f"💬 Message from {user_id}: {text}")
    
    try:
        bot.send_message(user_id, "👋 Используйте меню внизу", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"❌ Error: {e}")

# ==================== NOTIFICATIONS ====================

def format_notification(match):
    """Format notification"""
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
    """Send notifications"""
    logger.info(f"📤 Sending {len(matches)} notifications...")
    
    for match in matches:
        try:
            user_id = match['user_id']
            notification = format_notification(match)
            bot.send_message(user_id, notification)
            logger.info(f"✅ Notification to {user_id}")
        except Exception as e:
            logger.error(f"❌ Error: {e}")

# ==================== BACKGROUND SCANNER ====================

def background_scanner():
    """Background scanner thread"""
    logger.info("🔄 Scanner started")
    
    while True:
        try:
            logger.info("🔍 Scan cycle...")
            
            items = parser.get_all_items()
            logger.info(f"📥 Fetched {len(items)} items")
            
            if not items:
                time.sleep(SCAN_INTERVAL)
                continue
            
            user_searches = db.get_all_searches()
            logger.info(f"🔎 {len(user_searches)} active searches")
            
            if not user_searches:
                time.sleep(SCAN_INTERVAL)
                continue
            
            matches = ItemFilter.filter_items(items, user_searches, db)
            logger.info(f"✨ Found {len(matches)} matches")
            
            if matches:
                send_notifications(matches)
            
            logger.info(f"⏳ Next scan in {SCAN_INTERVAL}s")
            time.sleep(SCAN_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Scanner error: {e}", exc_info=True)
            time.sleep(SCAN_INTERVAL)

# ==================== STARTUP ====================

def start_background_threads():
    """Start background threads"""
    cleanup_thread = threading.Thread(target=cleanup_expired_states, daemon=True)
    cleanup_thread.start()
    logger.info("✅ Cleanup thread started")
    
    scanner_thread = threading.Thread(target=background_scanner, daemon=True)
    scanner_thread.start()
    logger.info("✅ Scanner thread started")

if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("🚀 Starting PirateSwap Tracker Bot")
    logger.info("=" * 70)
    
    start_background_threads()
    
    logger.info(f"🌐 Flask on 0.0.0.0:{PORT}")
    logger.info("=" * 70)
    
    try:
        app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ Flask error: {e}", exc_info=True)
        exit(1)

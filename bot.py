import telebot
import logging
import threading
import time
from config import BOT_TOKEN, ADMIN_CHAT_ID
from database import Database
from parser import PirateSwapParser
from filters import ItemFilter
from config import SCAN_INTERVAL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize database and parser
db = Database()
parser = PirateSwapParser()

# State management for user conversations
user_states = {}

# Main keyboard
def get_main_keyboard():
    """Create main menu keyboard"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('🚀 Старт', '➕ Добавить скин', '📋 Мои поиски')
    return markup

# ==================== BOT COMMANDS ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command"""
    user_id = message.chat.id
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
        "✅ В сообщении будут все данные о скине\n\n"
        "Начни с добавления скина, который хочешь отслеживать!"
    )
    bot.send_message(user_id, welcome_text, parse_mode='HTML', reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text == '🚀 Старт')
def start_button(message):
    """Handle Start button"""
    start_command(message)

@bot.message_handler(func=lambda message: message.text == '➕ Добавить скин')
def add_skin_start(message):
    """Start skin addition process"""
    user_id = message.chat.id
    user_states[user_id] = {'step': 'waiting_skin_name'}
    bot.send_message(
        user_id,
        "🎯 Какой скин хотите отслеживать?\n\n"
        "<i>Введите название или часть названия скина:</i>\n"
        "Например: <code>AK-47</code> или <code>Dragon Lore</code>",
        parse_mode='HTML',
        reply_markup=telebot.types.ForceReply()
    )

@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('step') == 'waiting_skin_name')
def process_skin_name(message):
    """Process skin name input"""
    user_id = message.chat.id
    skin_name = message.text.strip()
    
    if not skin_name or len(skin_name) < 2:
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
    
    bot.send_message(
        user_id,
        f"🎨 Нужен брелок для этого скина?\n\n"
        f"<b>Скин:</b> {skin_name}",
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in ['charm_yes', 'charm_no'])
def process_charm_choice(call):
    """Process charm/keychain choice"""
    user_id = call.message.chat.id
    
    if user_id not in user_states or user_states[user_id].get('step') != 'waiting_charm_choice':
        bot.answer_callback_query(call.id, "❌ Сессия истекла. Начните заново.", show_alert=True)
        return
    
    charm_required = 1 if call.data == 'charm_yes' else 0
    skin_name = user_states[user_id]['skin_name']
    
    # Save to database
    if db.add_search(user_id, skin_name, charm_required):
        charm_text = "Да ✨" if charm_required else "��ет"
        confirmation = (
            f"✅ <b>Поиск добавлен!</b>\n\n"
            f"<b>Название:</b> {skin_name}\n"
            f"<b>Брелок:</b> {charm_text}"
        )
        bot.send_message(user_id, confirmation, parse_mode='HTML', reply_markup=get_main_keyboard())
        
        # Clean up state
        del user_states[user_id]
        
        bot.answer_callback_query(call.id, "✅ Поиск успешно добавлен!", show_alert=False)
    else:
        bot.answer_callback_query(
            call.id,
            "❌ Такой поиск уже существует или произошла ошибка",
            show_alert=True
        )

@bot.message_handler(func=lambda message: message.text == '📋 Мои поиски')
def show_searches(message):
    """Show all user searches"""
    user_id = message.chat.id
    searches = db.get_user_searches(user_id)
    
    if not searches:
        bot.send_message(
            user_id,
            "📭 У вас нет активных поисков.\n\n"
            "Нажмите '<b>➕ Добавить скин</b>' чтобы начать отслеживание.",
            parse_mode='HTML',
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
                f"🗑 Удалить: {skin_name}",
                callback_data=f"delete_{search_id}"
            )
        )
    
    bot.send_message(user_id, response, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_search(call):
    """Delete search"""
    user_id = call.message.chat.id
    search_id = int(call.data.split('_')[1])
    
    if db.delete_search(search_id):
        bot.answer_callback_query(call.id, "✅ Поиск удалён!", show_alert=False)
        bot.edit_message_text(
            "🗑 <b>Поиск удалён</b>",
            user_id,
            call.message.message_id,
            parse_mode='HTML'
        )
    else:
        bot.answer_callback_query(call.id, "❌ Ошибка при удалении", show_alert=True)

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
    
    if match['inspect_link']:
        message += f"<b>Inspect:</b> <a href='{match['inspect_link']}'>Осмотреть в игре</a>"
    
    return message

def send_notifications(matches):
    """Send notifications to users"""
    for match in matches:
        try:
            user_id = match['user_id']
            notification = format_notification(match)
            bot.send_message(user_id, notification, parse_mode='HTML')
            logger.info(f"Notification sent to user {user_id} for item {match['item_id']}")
        except Exception as e:
            logger.error(f"Error sending notification to user {match['user_id']}: {e}")

# ==================== BACKGROUND SCANNER ====================

def background_scanner():
    """Background thread for scanning PirateSwap"""
    logger.info("Background scanner started")
    
    while True:
        try:
            logger.info("Starting scan...")
            
            # Get all items
            items = parser.get_all_items()
            
            if not items:
                logger.warning("No items fetched from API")
                time.sleep(SCAN_INTERVAL)
                continue
            
            # Get all active searches
            user_searches = db.get_all_searches()
            
            if not user_searches:
                logger.info("No active searches")
                time.sleep(SCAN_INTERVAL)
                continue
            
            # Filter items
            matches = ItemFilter.filter_items(items, user_searches, db)
            
            if matches:
                logger.info(f"Found {len(matches)} matching items")
                send_notifications(matches)
            else:
                logger.info("No matching items found")
            
            # Wait before next scan
            time.sleep(SCAN_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in background scanner: {e}")
            time.sleep(SCAN_INTERVAL)

# ==================== BOT STARTUP ====================

def start_background_thread():
    """Start background scanner thread"""
    scanner_thread = threading.Thread(target=background_scanner, daemon=True)
    scanner_thread.start()
    logger.info("Background scanner thread started")

if __name__ == '__main__':
    logger.info("Starting PirateSwap Tracker Bot...")
    
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        logger.error("BOT_TOKEN or ADMIN_CHAT_ID not set in environment variables")
        exit(1)
    
    # Start background scanner
    start_background_thread()
    
    # Start bot polling
    logger.info("Bot is now running...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=10)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
    finally:
        logger.info("Bot stopped")

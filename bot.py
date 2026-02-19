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
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
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

PORT = int(os.getenv('PORT', 5000))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
logger.info(f"✅ PORT: {PORT}")

def get_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row('🚀 Старт', '➕ Добавить скин')
    markup.row('📋 Мои поиски')
    return markup

@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok'}, 200

@app.route('/', methods=['GET'])
def root():
    return {'status': 'Bot is running'}, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    logger.info(f"📩 Incoming webhook update: {json_string}")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    logger.info("✅ Webhook update processed")
    return '', 200

# ==================== BOT MESSAGE HANDLERS ====================

@bot.message_handler(commands=['start'])
def start_command(message):
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
        msg = bot.send_message(user_id, welcome_text, reply_markup=get_main_keyboard())
        logger.info(f"✅ Start message sent to user {user_id}, message_id: {msg.message_id}")
    except Exception as e:
        logger.error(f"❌ Error sending start message to {user_id}: {e}", exc_info=True)

@bot.message_handler(func=lambda message: message.text == '🚀 Старт')
def start_button(message):
    start_command(message)

@bot.message_handler(func=lambda message: message.text == '➕ Добавить скин')
def add_skin_start(message):
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
    user_id = message.chat.id
    skin_name = message.text.strip()
    logger.info(f"📝 Skin name input from user {user_id}: '{skin_name}', state: {user_states[user_id]}")
    if not skin_name or len(skin_name) < 2:
        logger.warning(f"❌ Invalid skin name length from {user_id}")
        bot.send_message(user_id, "❌ Название скина слишком короткое. Пожалуйста, введите минимум 2 символа.")
        return
    user_states[user_id]['skin_name'] = skin_name
    user_states[user_id]['step'] = 'waiting_charm_choice'

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
    user_id = call.message.chat.id
    call_id = call.id
    logger.info(f"📌 Charm choice callback from user {user_id}: {call.data}, state: {user_states.get(user_id)}")
    if user_id not in user_states or user_states[user_id].get('step') != 'waiting_charm_choice':
        logger.warning(f"❌ Invalid state for user {user_id}")
        bot.answer_callback_query(call_id, "❌ Сессия истекла. Начните заново.", show_alert=True)
        return

    charm_required = 1 if call.data == 'charm_yes' else 0
    skin_name = user_states[user_id]['skin_name']

    try:
        added = db.add_search(user_id, skin_name, charm_required)
        if added:
            charm_text = "Да ✨" if charm_required else "Нет"
            confirmation = (
                f"✅ <b>Поиск добавлен!</b>\n\n"
                f"<b>Название:</b> {skin_name}\n"
                f"<b>Брелок:</b> {charm_text}"
            )
            bot.send_message(user_id, confirmation, reply_markup=get_main_keyboard())
            logger.info(f"✅ Search added for user {user_id}: {skin_name} (charm: {charm_required})")
            bot.answer_callback_query(call_id, "✅ Поиск успешно добавлен!", show_alert=False)
        else:
            logger.warning(f"❌ Failed to add search for user {user_id}")
            bot.answer_callback_query(
                call_id,
                "❌ Такой поиск уже существует или произошла ошибка",
                show_alert=True
            )
        del user_states[user_id]
    except Exception as e:
        logger.error(f"❌ Error adding search for {user_id}: {e}", exc_info=True)
        bot.answer_callback_query(call_id, f"❌ Ошибка: {str(e)}", show_alert=True)
        if user_id in user_states:
            del user_states[user_id]

@bot.message_handler(func=lambda message: message.text == '📋 Мои поиски')
def show_searches(message):
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
    user_id = message.chat.id
    if user_id in user_states:
        logger.info(f"default_handler SKIP: user {user_id} in dialogue: {user_states[user_id]}")
        return
    text = message.text
    logger.info(f"📝 Default message from user {user_id}: '{text}'")
    try:
        bot.send_message(
            user_id,
            "👋 Привет! Используйте меню внизу для работы с ботом.",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"❌ Error in default handler: {e}")

def format_notification(match):
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
    logger.info(f"📤 Sending {len(matches)} notifications...")
    for match in matches:
        try:
            user_id = match['user_id']
            notification = format_notification(match)
            bot.send_message(user_id, notification)
            logger.info(f"✅ Notification sent to user {user_id} for item {match['item_id']}")
        except Exception as e:
            logger.error(f"❌ Error sending notification to user {match['user_id']}: {e}")

def background_scanner():
    logger.info("🔄 Background scanner started")
    while True:
        logger.info("=== [SCANNER] NEW CYCLE STARTED ===")
        try:
            try:
                items = parser.get_all_items()
                logger.info(f"[SCANNER] parser.get_all_items() вернул {len(items)} предметов")
                for idx, it in enumerate(items):
                    logger.info(f"[SCANNER] ITEM {idx+1}: {it}")
            except Exception as fetch_exc:
                logger.error(f"[SCANNER][ERROR] Ошибка при получении предметов через parser.get_all_items: {fetch_exc}", exc_info=True)
                items = []

            try:
                user_searches = db.get_all_searches()
                logger.info(f"[SCANNER] db.get_all_searches() вернул {len(user_searches)} поисков")
                for idx, search in enumerate(user_searches):
                    logger.info(f"[SCANNER] SEARCH {idx+1}: {search}")
            except Exception as filter_exc:
                logger.error(f"[SCANNER][ERROR] Ошибка при получении поисков пользователей: {filter_exc}", exc_info=True)
                user_searches = []

            try:
                matches = ItemFilter.filter_items(items, user_searches, db)
                logger.info(f"[SCANNER] ItemFilter.filter_items нашёл {len(matches)} совпадений")
                for idx, match in enumerate(matches):
                    logger.info(f"[SCANNER] MATCH {idx+1}: {match}")
            except Exception as filter_exc:
                logger.error(f"[SCANNER][ERROR] Ошибка при фильтрации: {filter_exc}", exc_info=True)
                matches = []

            if matches:
                try:
                    send_notifications(matches)
                except Exception as notify_exc:
                    logger.error(f"[SCANNER][ERROR] Ошибка при отправке уведомлений: {notify_exc}", exc_info=True)
            else:
                logger.info("[SCANNER] Нет совпадений для уведомления пользователей.")

            logger.info("=== [SCANNER] END OF CYCLE, sleeping before next scan... ===")
            time.sleep(SCAN_INTERVAL)
        except Exception as cycle_exc:
            logger.error(f"[SCANNER][ERROR] НЕОЖИДАННАЯ ОШИБКА в основном цикле: {cycle_exc}", exc_info=True)
            time.sleep(SCAN_INTERVAL)

def run_flask():
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False, threaded=False)

if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("🚀 Starting PirateSwap Tracker Bot (Web Service + Scanner in ONE process)")
    logger.info("=" * 70)

    # === Запуск сканера в отдельном НЕ-демон-потоке ===
    scanner_thread = threading.Thread(target=background_scanner, name='scanner', daemon=False)
    scanner_thread.start()

    # === Настраиваем webhook перед запуском Flask
    if WEBHOOK_URL:
        full_webhook_url = WEBHOOK_URL.rstrip('/') + '/webhook'
        try:
            bot.remove_webhook()
            bot.set_webhook(url=full_webhook_url)
            logger.info(f"✅ Webhook set: {full_webhook_url}")
        except Exception as e:
            logger.error(f"❌ Failed to set webhook: {e}", exc_info=True)
            exit(1)
        run_flask()
    else:
        logger.info("ℹ️ WEBHOOK_URL не задан, используем polling")
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
        except Exception as e:
            logger.error(f"❌ Polling error: {e}", exc_info=True)
            exit(1)

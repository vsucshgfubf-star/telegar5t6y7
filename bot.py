import os
import json
from flask import Flask, request
import requests
from html import escape

# ======= Конфигурация =======
TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

app = Flask(__name__)

# ======= State для управления чатами =======
active_chats = {}  # user_id -> stage: 'pending' | 'active'

# ======= State для консультацій =======
consult_request = {}  # user_id -> {"stage": "choose_duration"/"await_contact", "duration": "30"|"45"|"60"}

# ======= Reply и Inline разметки =======
def main_menu_markup():
    return {
        "keyboard": [
            [{"text": "Меню"}],
            [{"text": "Связь с админом"}, {"text": "Реквізити оплати"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def user_finish_markup():
    return {
        "keyboard": [[{"text": "Завершить чат"}]],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def admin_reply_markup(user_id):
    return {
        "inline_keyboard": [
            [{"text": "Ответить", "callback_data": f"reply_{user_id}"}],
            [{"text": "Завершить чат", "callback_data": f"close_{user_id}"}],
        ]
    }

def welcome_services_inline():
    return {
        "inline_keyboard": [
            [{"text": "• консультації", "callback_data": "consult"}],
            [{"text": "• супровід ФОП", "callback_data": "support"}],
            [{"text": "• реєстрація / закриття", "callback_data": "regclose"}],
            [{"text": "• звітність і податки", "callback_data": "reports"}],
            [{"text": "• ПРРО", "callback_data": "prro"}],
            [{"text": "• декрет ФОП", "callback_data": "decret"}]
        ]
    }

def return_to_menu_markup():
    return {
        "keyboard": [[{"text": "Повернутися в меню"}]],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# ======= Inline markup для консультації =======
def consult_duration_inline():
    return {
        "inline_keyboard": [
            [{"text": "30 хв", "callback_data": "consult_30"}],
            [{"text": "45 хв", "callback_data": "consult_45"}],
            [{"text": "60 хв", "callback_data": "consult_60"}],
            [{"text": "Повернутися в меню", "callback_data": "consult_back"}]
        ]
    }

# ======= Inline markup для супровід ФОП =======
def support_groups_inline():
    return {
        "inline_keyboard": [
            [{"text": "Группа ФОП 1", "callback_data": "support_1"}],
            [{"text": "Группа ФОП 2", "callback_data": "support_2"}],
            [{"text": "Группа ФОП 3", "callback_data": "support_3"}],
            [{"text": "Повернутися в меню", "callback_data": "support_back"}]
        ]
    }

def support_next_inline():
    return {
        "inline_keyboard": [
            [{"text": "Реквізити оплати", "callback_data": "support_pay"}],
            [{"text": "Связь с админом", "callback_data": "support_admin"}],
            [{"text": "Повернутися в меню", "callback_data": "support_back"}]
        ]
    }

WELCOME_SERVICES_TEXT = (
    "Вітаю\n"
    "Мене звати,  ——— !\n"
    "Я бухгалтер для ФОП — допомагаю підприємцям спокійно вести справи, не хвилюючись за податки, звітність і всі дрібниці, про які зазвичай болить голова\n\n"
    "У цьому боті ви можете:\n"
    "• обрати потрібну послугу та одразу побачити вартість;\n"
    "• записатись на консультацію чи супровід;\n"
    "• отримати реквізити для оплати;\n"
    "• або просто поставити запитання — я завжди на зв’язку\n\n"
    "З чого хочете розпочати ? 👇"
)

CONSULT_INTRO_TEXT = (
    "Консультація — це зручно, швидко і по суті 💬\n"
    "Ви можете обрати формат:\n\n"
    "▫️ 30 хв — 600 грн\n"
    "▫️ 45 хв — 800 грн\n"
    "▫️ 60 хв — 1000 грн\n\n"
    "Консультація проходить онлайн (Telegram / Instagram).\n\n"
    "Оберіть, будь ласка, тривалість 👇"
)

CONSULT_CONTACTS_TEXT = (
    "Чудово! 💼\n"
    "Щоб зафіксувати час консультації, будь ласка, залиште ваші контакти:\n"
    "•Ім'я та Прізвище\n"
    "•Нік Інстаграм чи Телеграм"
)

SUPPORT_INFO_TEXT = (
    "💼 Супровід ФОП — це коли про ваш облік піклуються за вас 🌸\n\n"
    "Ви не думаєте про податки, звітність чи перевірки — усе під контролем.\n"
    "Я беру ваш ФОП на повне бухгалтерське обслуговування 💪\n\n"
    "🔍 У супровід входить:\n"
    "• перевірка правильності вашої діяльності\n"
    "• нагадування про терміни сплати податку\n"
    "• повідомлення вам нових змін та законів\n"
    "• ведення Книги обліку доходів\n"
    "• консультаційна підтримка\n\n"
    "Звітність оплачується Додатково ❗\n\n"
    "🕓 Термін — 1 місяць (з можливістю продовження)\n\n"
    "Щоб я краще розуміла ваш запит 👇\n"
    "Оберіть, будь ласка, вашу групу ФОП:"
)

SUPPORT_GROUP_SELECTED_TEXT = (
    "💼 Інформація на вибранну вами группа ФОП  🌸\n\n"
    "Ви сплачуєте єдиний податок,військовий збір та ЄСВ щомісяця, звітність — 1 раз на рік.\n\n"
    "💰 Вартість супроводу — 1000 грн / місяць\n"
    "Додаткові послуги + до вартості \n"
    "Узгоджуємо особисто !\n\n"
    "Бажаєте отримати реквізити для оплати, щоб розпочати співпрацю? 👇"
)

# ======= Хелперы для отправки сообщений и медиа =======
def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        data["parse_mode"] = parse_mode
    requests.post(url, data=data, timeout=8)

def send_media(chat_id, msg):
    for key, api in [
        ("photo", "sendPhoto"), ("document", "sendDocument"),
        ("video", "sendVideo"), ("audio", "sendAudio"), ("voice", "sendVoice")
    ]:
        if key in msg:
            file_id = msg[key][-1]["file_id"] if key == "photo" else msg[key]["file_id"]
            payload = {"chat_id": chat_id, key: file_id}
            if "caption" in msg:
                payload["caption"] = msg.get("caption")
            requests.post(f"https://api.telegram.org/bot{TOKEN}/{api}", data=payload)
            return True
    return False

# ======= Главный обработчик событий Telegram =======
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)

    # --- Обработка инлайн-кнопок (callback_query) ---
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        from_id = cb["from"]["id"]

        # ====== Инлайн-кнопки для супровід ФОП ======
        if data == "support":
            send_message(chat_id, SUPPORT_INFO_TEXT, reply_markup=support_groups_inline())
            return "ok", 200

        if data in ("support_1", "support_2", "support_3"):
            send_message(chat_id, SUPPORT_GROUP_SELECTED_TEXT, reply_markup=support_next_inline())
            return "ok", 200

        if data == "support_pay":
            send_message(chat_id, "<b>Реквізити для оплати:</b>\nПриватБанк: 1234 5678 0000 1111\nМоноБанк: 4444 5678 1234 5678\nIBAN: UA12 1234 5678 0000 1111 1234 5678", parse_mode="HTML", reply_markup=main_menu_markup())
            return "ok", 200

        if data == "support_admin":
            # Поведение полностью как у reply-кнопки "Связь с админом"
            if chat_id not in active_chats:
                active_chats[chat_id] = "pending"
                send_message(chat_id, "Ожидайте ответа администратора...", reply_markup=user_finish_markup())
                notif = f"<b>Новое сообщение по супроводу ФОП!</b>\nID: <pre>{chat_id}</pre>"
                send_message(ADMIN_ID, notif, parse_mode="HTML", reply_markup=admin_reply_markup(chat_id))
            else:
                send_message(chat_id, "Ожидайте ответа администратора...", reply_markup=user_finish_markup())
            return "ok", 200

        if data == "support_back":
            send_message(chat_id, "👋 Добро пожаловать! Выберите действие:", reply_markup=main_menu_markup())
            return "ok", 200

        # >>>>>>> БЛОК ДЛЯ КОНСУЛЬТАЦИИ <<<<<<<<
        if data == "consult":
            consult_request[from_id] = {"stage": "choose_duration"}
            send_message(chat_id, CONSULT_INTRO_TEXT, reply_markup=consult_duration_inline())
            return "ok", 200

        if data in ("consult_30", "consult_45", "consult_60"):
            duration = data.split("_")[1]
            consult_request[from_id] = {"stage": "await_contact", "duration": duration}
            send_message(chat_id, CONSULT_CONTACTS_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        if data == "consult_back":
            consult_request.pop(from_id, None)
            active_chats.pop(from_id, None)
            send_message(chat_id, "👋 Добро пожаловать! Выберите действие:", reply_markup=main_menu_markup())
            return "ok", 200

        if data in ("regclose", "reports", "prro", "decret"):
            send_message(chat_id, "Оберіть далі, або поверніться до меню.", reply_markup=return_to_menu_markup())
            return "ok", 200

        # Ответ и завершение админом
        if data.startswith("reply_") and int(from_id) == ADMIN_ID:
            user_id = int(data.split("_")[1])
            active_chats[user_id] = "active"
            send_message(ADMIN_ID, f"Отправьте сообщение или медиа для пользователя {user_id}.")
            return "ok", 200
        if data.startswith("close_") and int(from_id) == ADMIN_ID:
            user_id = int(data.split("_")[1])
            active_chats.pop(user_id, None)
            send_message(user_id, "⛔️ Чат завершён администратором. Вы вернулись в главное меню.", reply_markup=main_menu_markup())
            send_message(ADMIN_ID, "Чат завершён.", reply_markup=main_menu_markup())
            return "ok", 200

    msg = update.get("message")
    if not msg:
        return "ok", 200
    cid = msg.get("chat", {}).get("id")
    text = msg.get("text", "") or ""
    user_data = msg.get("from", {})
    user_id = user_data.get("id")
    user_name = (user_data.get("first_name", "") + " " + user_data.get("last_name", "")).strip() or "Пользователь"

    # --- Главное меню / старт ---
    if text.startswith("/start") or text == "Повернутися в меню":
        consult_request.pop(user_id, None)
        active_chats.pop(user_id, None)
        send_message(cid, "👋 Добро пожаловать! Выберите действие:", reply_markup=main_menu_markup())
        return "ok", 200

    if text == "Меню":
        send_message(cid, WELCOME_SERVICES_TEXT, reply_markup=welcome_services_inline(), parse_mode="HTML")
        return "ok", 200
    if text == "Реквізити оплати" and cid not in active_chats:
        send_message(cid, "<b>Реквізити для оплати:</b>\nПриватБанк: 1234 5678 0000 1111\nМоноБанк: 4444 5678 1234 5678\nIBAN: UA12 1234 5678 0000 1111 1234 5678", parse_mode="HTML", reply_markup=main_menu_markup())
        return "ok", 200

    # --- Запрос на связь с админом ---
    if text == "Связь с админом" and cid not in active_chats:
        active_chats[cid] = "pending"
        send_message(cid, "Ожидайте ответа администратора...", reply_markup=user_finish_markup())
        notif = f"<b>Новое сообщение от пользователя!</b>\nВід: {escape(user_name)}\nID: <pre>{cid}</pre>"
        send_message(ADMIN_ID, notif, parse_mode="HTML", reply_markup=admin_reply_markup(cid))
        if any(k in msg for k in ("photo", "document", "video", "audio", "voice")):
            send_media(ADMIN_ID, msg)
        elif text != "Связь с админом":
            send_message(ADMIN_ID, f"<pre>{escape(text)}</pre>", parse_mode="HTML", reply_markup=admin_reply_markup(cid))
        return "ok", 200

    # --- Завершение чата пользователем ---
    if text == "Завершить чат" and cid in active_chats:
        active_chats.pop(cid, None)
        send_message(cid, "⛔️ Чат завершён. Вы вернулись в главное меню.", reply_markup=main_menu_markup())
        send_message(ADMIN_ID, f"Пользователь {cid} завершил чат.", reply_markup=main_menu_markup())
        return "ok", 200

    # --- Переписка пользователя с админом ---
    if cid in active_chats and active_chats[cid] == "active":
        if any(k in msg for k in ("photo", "document", "video", "audio", "voice")):
            send_media(ADMIN_ID, msg)
            send_message(ADMIN_ID, f"[медиа від {cid}]", reply_markup=admin_reply_markup(cid))
        elif text != "Завершить чат":
            send_message(ADMIN_ID, f"Пользователь {cid}:\n<pre>{escape(text)}</pre>", parse_mode="HTML", reply_markup=admin_reply_markup(cid))
        return "ok", 200

    # --- Ответ админа пользователю (если есть активный чат) ---
    if cid == ADMIN_ID:
        targets = [u for u, s in active_chats.items() if s == "active"]
        if not targets:
            return "ok", 200
        target = targets[0]
        if any(k in msg for k in ("photo", "document", "video", "audio", "voice")):
            send_media(target, msg)
            send_message(target, "💬 Ответ администратора (медиа).", reply_markup=user_finish_markup())
        elif text.lower().startswith("завершить"):
            active_chats.pop(target, None)
            send_message(target, "⛔️ Чат завершён администратором. Вы вернулись в главное меню.", reply_markup=main_menu_markup())
            send_message(ADMIN_ID, "Чат завершён.", reply_markup=main_menu_markup())
        elif text:
            send_message(target, f"💬 Ответ администратора:\n<pre>{escape(text)}</pre>", parse_mode="HTML", reply_markup=user_finish_markup())
        return "ok", 200

    # --- Если пользователь в чате, доступны только переписка и "Завершить чат" ---
    if cid in active_chats:
        send_message(cid, "В активном чате доступны только переписка и кнопка 'Завершить чат'.", reply_markup=user_finish_markup())
        return "ok", 200

    # === ОБРАБОТКА КОНТАКТОВ КОНСУЛЬТАЦІЇ ===
    if user_id in consult_request and consult_request[user_id].get("stage") == "await_contact":
        duration = consult_request[user_id].get("duration")
        note = (
            f"<b>Заявка на консультацію</b>\n"
            f"Тривалість: {duration} хв\n"
            f"Від: {escape(user_name)}\n"
            f"ID: <pre>{user_id}</pre>\n"
        )
        if any(k in msg for k in ("photo", "document", "video", "audio", "voice")):
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
            send_media(ADMIN_ID, msg)
        elif text:
            note += f"Контакти: <pre>{escape(text.strip())}</pre>"
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
        send_message(user_id, "Дякую! Ваші дані отримано, з вами зв'яжеться адміністратор.", reply_markup=main_menu_markup())
        consult_request.pop(user_id, None)
        return "ok", 200

    # --- Fallback: меню по умолчанию ---
    send_message(cid, "Будь ласка, оберіть дію з меню 👇", reply_markup=main_menu_markup())
    return "ok", 200

# ======= Пинг для uptime мониторинга / проверки =======
@app.route("/", methods=["GET"])
def index():
    return "OK", 200

if __name__ == "__main__":
    app.run("0.0.0.0", port=int(os.getenv("PORT", "5000")))

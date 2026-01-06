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

# ======= State для консультаций и этапов отчетов =======
consult_request = {}  # user_id -> {"stage": "choose_duration"/"await_contact", "duration": "30"|"45"|"60"}
reports_request = {}  # user_id -> {"stage": "...", "type": "submit"/"taxcheck"}
prro_request = {}     # Можно расширить если потребуется цепочка ПРРО

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
            [{"text": "реєстрація/закриття ПРРО", "callback_data": "prro"}],
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

# ======= Inline markup для реєстрація / закриття ФОП =======
def regclose_inline():
    return {
        "inline_keyboard": [
            [{"text": "Регестрация ФОП", "callback_data": "fop_register"}],
            [{"text": "Закрытие ФОП", "callback_data": "fop_close"}],
            [{"text": "Повернутися в меню", "callback_data": "regclose_back"}]
        ]
    }

def fop_register_inline():
    return {
        "inline_keyboard": [
            [{"text": "Регистрируем", "callback_data": "fop_register_pay"}],
            [{"text": "Повернутися", "callback_data": "regclose"}]
        ]
    }

def fop_close_inline():
    return {
        "inline_keyboard": [
            [{"text": "Закрываем", "callback_data": "fop_close_pay"}],
            [{"text": "Повернутися", "callback_data": "regclose"}]
        ]
    }

# ======= Inline markup для звітність і податки =======
def reports_inline():
    return {
        "inline_keyboard": [
            [{"text": "Подача отчета", "callback_data": "report_submit"}],
            [{"text": "Оплата податка / перевірка ФОП", "callback_data": "report_tax_check"}],
            [{"text": "Повернутися в меню", "callback_data": "reports_back"}],
        ]
    }

def report_submit_service_inline():
    return {
        "inline_keyboard": [
            [{"text": "Хочу цю послугу", "callback_data": "report_submit_contacts"}],
            [{"text": "Повернутися", "callback_data": "reports"}],
        ]
    }

def report_tax_check_inline():
    return {
        "inline_keyboard": [
            [{"text": "Перевіряємо", "callback_data": "tax_check_contacts"}],
            [{"text": "Повернутися", "callback_data": "reports"}]
        ]
    }

def tax_check_pay_inline():
    return {
        "inline_keyboard": [
            [{"text": "Оплата / реквізит", "callback_data": "tax_check_pay"}],
            [{"text": "Повернутися", "callback_data": "reports"}]
        ]
    }

# ======= Inline markup для реєстрація/закриття ПРРО =======
def prro_inline():
    return {
        "inline_keyboard": [
            [{"text": "Реєстрація ПРРО", "callback_data": "prro_register"}],
            [{"text": "Закриття ПРРО", "callback_data": "prro_close"}],
            [{"text": "Повернутися в меню", "callback_data": "prro_back"}]
        ]
    }

def prro_register_step_inline():
    return {
        "inline_keyboard": [
            [{"text": "Регистрируем", "callback_data": "prro_register_pay"}],
            [{"text": "Повернутися", "callback_data": "prro"}],
        ]
    }

def prro_register_pay_inline():
    return {
        "inline_keyboard": [
            [{"text": "Оплата / реквізит", "callback_data": "prro_pay"}],
            [{"text": "Повернутися", "callback_data": "prro"}],
        ]
    }

# ======= ТЕКСТЫ для всех сервисов =======
WELCOME_SERVICES_TEXT = (
    "Вітаю\n"
    "Мене звати,  ——— !\n"
    "Я бухгалтер для ФОП — допомагаю підприємцям спокійно вести справи, не хвилюючись за податки, звітність і все інше.\n"
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

REGCLOSE_INTRO_TEXT = (
    "Оберіть що саме вам потрібно 👇"
)

FOP_REGISTER_TEXT = (
    "Я допоможу швидко та безпечно зареєструвати ФОП під ключ.\n\n"
    "Що входить у послугу:\n"
    "- Консультація щодо вибору КВЕДів та системи оподаткування;\n"
    "- Підготовка документів для реєстрації;\n"
    "- Подання заяви до державного реєстратора (онлайн або офлайн);\n"
    "- Отримання виписки з ЄДР;\n"
    "- Реєстрація в податковій та/або як платника єдиного податку (за потреби).\n"
    "- Консультація для подальшої роботи\n\n"
    "Термін виконання: 1–2 робочі дні.\n"
    "Результат: офіційно зареєстрований ФОП, готовий до роботи.\n\n"
    "Вартість — 2500 грн."
)

FOP_REGISTER_PAY_TEXT = (
    "Оплата здійснюється на офіційний рахунок ФОП👩🏻‍💻\n\n"
    "Отримувач :\n"
    "ФОП Зброжик Катерина Миколаївна\n\n"
    "ЄДРПОУ : 3608900026\n"
    "IBAN : UA303220010000026001340018080\n\n"
    "Призначення платежу : оплата за консультаційні послуги\n\n"
    "❤️ ОБОВ’ЯЗКОВО після здійснення оплати скиньте будь ласка чек або скрін екрану сюда @your_telegram_tag"
)

FOP_CLOSE_TEXT = (
    "Я допоможу ��фіційно припинити підприємницьку діяльність швидко, без черг і зайвих клопотів.\n"
    "Підготую всі документи, подам заяву до держреєстратора, закрию ФОП у податковій та здам необхідну звітність.\n\n"
    "Що входить у послугу:\n"
    "- Консультація щодо процедури закриття ФОП;\n"
    "- Підготовка та подання заяви до державного реєстратора;\n"
    "- Здача фінальної звітності до податкової;\n"
    "- Отримання підтвердження про припинення діяльності;\n\n"
    "Термін: від 3 до 7 робочих днів.\n"
    "Результат: ФОП офіційно закрито, без податкових боргів і з чистою історією.\n\n"
    "Вартість — 2000 грн."
)

FOP_CLOSE_PAY_TEXT = (
    "Оплата здійснюється на офіційний рахунок ФОП👩🏻‍💻\n\n"
    "Отримувач :\n"
    "ФОП Зброжик Катерина Миколаївна\n\n"
    "ЄДРПОУ : 3608900026\n"
    "IBAN : UA303220010000026001340018080\n\n"
    "Призначення платежу : оплата за консультаційні послуги\n\n"
    "❤️ ОБОВ’ЯЗКОВО після здійснення оплати скиньте будь ласка чек або скрін екрану сюда @your_telegram_tag"
)

REPORTS_INTRO_TEXT = (
    "Обери, що саме потрібно зараз 👇\n\n"
    "📊 Подання звітності\n"
    "Я підготую і здам усі декларації замість тебе — без помилок, штрафів і головного болю.\n\n"
    "💰 Сплата податків / Перевірка ФОП\n"
    "Допоможу перевірити актуальні суми податків, строки сплати та підкажу, як оплатити правильно.\n\n"
    "Ти просто обираєш, а я все організовую 🌿"
)

REPORT_SUBMIT_TEXT = (
    "Я беру на себе повний процес підготовки та подання звітності для фізичних осіб-підприємців.\n"
    "Підготую декларації, перевірю правильність даних, подам їх до податкової та проконтролюю результат.\n\n"
    "Що входить у послугу:\n"
    "- Підготовка та подання податкової декларації;\n"
    "- Звітність по ЄСВ та єдиному податку;\n"
    "- Контроль строків подачі;\n"
    "- Повідомлення про успішну здачу звіту.\n\n"
    "Результат: звітність здана вчасно, правильно й без штрафів."
)

REPORT_SUBMIT_CONTACTS_TEXT = (
    "Чудово! 🙌\n"
    "Рада, що ти обрав(-ла) послугу «Подання звітності» 💼\n\n"
    "Щоб я могла підготувати все правильно, мені потрібно кілька деталей:\n"
    "1️⃣ Твій ПІБ (як у ФОП) та Податковий номер (ІПН)\n"
    "2️⃣ Електронний ключ та пароль\n"
    "3️⃣ Період, за який потрібно здати звітність (наприклад: 3 квартал 2025)"
)

REPORT_TAX_CHECK_TEXT = (
    "Я допомагаю перевірити актуальні податкові зобов’язання, стан розрахунків та суми до сплати.\n"
    "Підкажу, які податки і внески потрібно сплатити, а також як це зробити швидко і безпечно.\n\n"
    "У послугу входить:\n"
    "- Перевірка стану ФОП у податковій системі;\n"
    "- Визначення наявних боргів і штрафів;\n"
    "- Консультація щодо сум і строків сплати;\n"
    "- Підтримка у проведенні оплати (реквізити, способи оплати).\n\n"
    "Зі мною ти будеш впевнений, що податкові питання під контролем."
)

REPORT_TAX_CHECK_CONTACTS_TEXT = (
    "Готово! 😊\n"
    "Щоб я могла швидко перевірити стан твого ФОП, надішли, будь ласка:\n"
    "1. Твій податковий номер (ІПН)\n"
    "2. ПІБ, як у реєстрації ФОП\n"
    "3. Електронний ключ та пароль\n\n"
    "Після цього я перевірю інформацію і повідомлю тобі про наявність податкових зобов’язань та боргів.\n\n"
    "Вартість - 800 грн."
)

TAX_CHECK_PAY_TEXT = (
    "Оплата здійснюється на офіційний рахунок ФОП👩🏻‍💻\n\n"
    "Отримувач :\n"
    "ФОП Зброжик Катерина Миколаївна\n\n"
    "ЄДРПОУ : 3608900026\n"
    "IBAN : UA303220010000026001340018080\n\n"
    "Призначення платежу : оплата за консультаційні послуги\n\n"
    "❤️ ОБОВ’ЯЗКОВО після здійснення оплати скиньте будь ласка чек або скрін екрану сюда @your_telegram_tag"
)

PRRO_INTRO_TEXT = (
    "Виберіть одну з послуг, яка вам потрібна:\n\n"
    "1️⃣ Реєстрація ПРРО\n"
    "Допоможу швидко та без помилок зареєструвати ваш програмний РРО відповідно до вимог законодавства.\n\n"
    "2️⃣ Закриття ПРРО\n"
    "Професійно допоможу закрити ПРРО, якщо він більше не потрібен."
)

PRRO_REGISTER_TEXT = (
    "Надаю комплексну допомогу у реєстрації програмного реєстратора розрахункових операцій (ПРРО) відповідно до чинного законодавства України.\n\n"
    "Що входить у послугу:\n"
    "- Консультація щодо вибору ПРРО\n"
    "Допоможу підібрати програмне рішення, яке найкраще підходить для вашого бізнесу.\n\n"
    "- Підготовка необхідних документів\n"
    "Зберу і оформлю всі потрібні документи для реєстрації ПРРО у податковій службі.\n\n"
    "- Реєстрація ПРРО в ДПС\n"
    "Проведу подання заяви та реєстраційних документів через електронний кабінет платника податків.\n\n"
    "- Навчання та консультації\n"
    "Поясню, як користуватися ПРРО, як формувати чеки, звіти, і відповім на всі питання.\n\n"
    "- Отримання підтвердження від податкової\n"
    "Підтверджую успішну реєстрацію та передачу інформації.\n\n"
    "Ваші переваги:\n"
    "⚪ Повна підтримка на кожному етапі\n"
    "⚪ Оперативність та мінімум паперової тяганини\n"
    "⚪ Упевненість у правильності та законності процесу\n"
    "⚪ Збереження часу і ресурсів вашого бізнесу"
)

PRRO_REGISTER_CONTACTS_TEXT = (
    "Дякую, що обрали реєстрацію ПРРО! 💪\n"
    "Щоб розпочати, будь ласка, надішліть мені:\n"
    "1. Назву вашого бізнесу або ПІБ підприємця\n"
    "2. Податковий номер (ІПН)\n"
    "3. Електронний ключ та пароль\n"
    "4. Який ПРРО бажаєте зареєструвати? (якщо незнаєте — я допоможу з вибором)\n\n"
    "Нижче скидаю реквізити для оплати\n"
    "Вартість — 2000 грн.\n\n"
    "Як тільки отримаю ці дані, розпочну підготовку документів і оформлення заявки."
)

PRRO_REGISTER_PAY_TEXT = (
    "Оплата здійснюється на офіційний рахунок ФОП👩🏻‍💻\n\n"
    "Отримувач :\n"
    "ФОП Зброжик Катерина Миколаївна\n\n"
    "ЄДРПОУ : 3608900026\n"
    "IBAN : UA303220010000026001340018080\n\n"
    "Призначення п��атежу : оплата за консультаційні послуги\n\n"
    "❤️ ОБОВ’ЯЗКОВО після здійснення оплати скиньте будь ласка чек або скрін екрану сюда @your_telegram_tag"
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
            send_message(chat_id, "<b>Реквізити для оплати:</b>\nПриватБанк: 1234 5678 0000 1111\nМоноБанк: 4444 5678 1234 5678\nIBAN: UA12 1234 5678 0000 1111 1234 5678", parse_mode="HTML")
            return "ok", 200

        if data == "support_admin":
            # Поведение полностью как у reply-кнопки "Связь с админом"
            if chat_id not in active_chats:
                active_chats[chat_id] = "pending"
                send_message(chat_id, "Ожидайте ответа адміністратора...", reply_markup=user_finish_markup())
                notif = f"<b>Новое сообщение по супроводу ФОП!</b>\nID: <pre>{chat_id}</pre>"
                send_message(ADMIN_ID, notif, parse_mode="HTML", reply_markup=admin_reply_markup(chat_id))
            else:
                send_message(chat_id, "Ожидайте ответа адміністратора...", reply_markup=user_finish_markup())
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

        # ====== Реєстрація / Закриття ФОП =====
        if data == "regclose":
            send_message(chat_id, REGCLOSE_INTRO_TEXT, reply_markup=regclose_inline())
            return "ok", 200

        if data == "fop_register":
            send_message(chat_id, FOP_REGISTER_TEXT, reply_markup=fop_register_inline())
            return "ok", 200

        if data == "fop_register_pay":
            send_message(chat_id, FOP_REGISTER_PAY_TEXT, reply_markup=regclose_inline())
            return "ok", 200

        if data == "fop_close":
            send_message(chat_id, FOP_CLOSE_TEXT, reply_markup=fop_close_inline())
            return "ok", 200

        if data == "fop_close_pay":
            send_message(chat_id, FOP_CLOSE_PAY_TEXT, reply_markup=regclose_inline())
            return "ok", 200

        if data == "regclose_back":
            send_message(chat_id, "👋 Добро пожаловать! Выберите действие:", reply_markup=main_menu_markup())
            return "ok", 200

        # ====== Блок звітність і податки ======
        if data == "reports":
            send_message(chat_id, REPORTS_INTRO_TEXT, reply_markup=reports_inline())
            return "ok", 200

        if data == "report_submit":
            send_message(chat_id, REPORT_SUBMIT_TEXT, reply_markup=report_submit_service_inline())
            return "ok", 200

        if data == "report_submit_contacts":
            reports_request[from_id] = {"stage": "await_contact", "type": "submit"}
            send_message(chat_id, REPORT_SUBMIT_CONTACTS_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        if data == "report_tax_check":
            send_message(chat_id, REPORT_TAX_CHECK_TEXT, reply_markup=report_tax_check_inline())
            return "ok", 200

        if data == "tax_check_contacts":
            reports_request[from_id] = {"stage": "await_contact", "type": "taxcheck"}
            send_message(chat_id, REPORT_TAX_CHECK_CONTACTS_TEXT, reply_markup=tax_check_pay_inline())
            return "ok", 200

        if data == "tax_check_pay":
            send_message(chat_id, TAX_CHECK_PAY_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        if data == "reports_back":
            send_message(chat_id, "👋 Добро пожаловать! Выберите действие:", reply_markup=main_menu_markup())
            return "ok", 200

        # ====== БЛОК ПРРО ======
        if data == "prro":
            send_message(chat_id, PRRO_INTRO_TEXT, reply_markup=prro_inline())
            return "ok", 200

        if data == "prro_register":
            send_message(chat_id, PRRO_REGISTER_TEXT, reply_markup=prro_register_step_inline())
            return "ok", 200

        if data == "prro_register_pay":
            send_message(chat_id, PRRO_REGISTER_CONTACTS_TEXT, reply_markup=prro_register_pay_inline())
            return "ok", 200

        if data == "prro_pay":
            send_message(chat_id, PRRO_REGISTER_PAY_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        if data == "prro_close":
            # Аналогично support_admin: создаем и уведомляем админа
            if chat_id not in active_chats:
                active_chats[chat_id] = "pending"
                send_message(chat_id, "Ожидайте ответа адміністратора...", reply_markup=user_finish_markup())
                notif = f"<b>Новое сообщение! Запит на закриття ПРРО</b>\nID: <pre>{chat_id}</pre>"
                send_message(ADMIN_ID, notif, parse_mode="HTML", reply_markup=admin_reply_markup(chat_id))
            else:
                send_message(chat_id, "Ожидайте ответа адміністратора...", reply_markup=user_finish_markup())
            return "ok", 200

        if data == "prro_back":
            send_message(chat_id, "👋 Добро пожаловать! Выберите действие:", reply_markup=main_menu_markup())
            return "ok", 200

        if data in ("decret",):
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
        reports_request.pop(user_id, None)
        send_message(cid, "👋 Добро пожаловать! Выберите действие:", reply_markup=main_menu_markup())
        return "ok", 200

    if text == "Меню":
        send_message(cid, WELCOME_SERVICES_TEXT, reply_markup=welcome_services_inline(), parse_mode="HTML")
        return "ok", 200
    if text == "Реквізити оплати" and cid not in active_chats:
        send_message(cid, "<b>Реквізити для оплати:</b>\nПриватБанк: 1234 5678 0000 1111\nМоноБанк: 4444 5678 1234 5678\nIBAN: UA12 1234 5678 0000 1111 1234 5678", parse_mode="HTML")
        return "ok", 200

    # --- Запрос на связь с админом ---
    if text == "Связь с админом" and cid not in active_chats:
        active_chats[cid] = "pending"
        send_message(cid, "Ожидайте ответа адміністратора...", reply_markup=user_finish_markup())
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
            send_message(target, "💬 Ответ адміністратора (медіа).", reply_markup=user_finish_markup())
        elif text.lower().startswith("завершить"):
            active_chats.pop(target, None)
            send_message(target, "⛔️ Чат завершён администратором. Вы вернулись в главное меню.", reply_markup=main_menu_markup())
            send_message(ADMIN_ID, "Чат завершён.", reply_markup=main_menu_markup())
        elif text:
            send_message(target, f"💬 Ответ адміністратора:\n<pre>{escape(text)}</pre>", parse_mode="HTML", reply_markup=user_finish_markup())
        return "ok", 200

    # --- Если пользователь в чате, доступны только переписка и "Завершить чат" ---
    if cid in active_chats:
        send_message(cid, "В активному чаті доступні тільки переписка і кнопка 'Завершить чат'.", reply_markup=user_finish_markup())
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

    # === ОБРАБОТКА КОНТАКТОВ ДЛЯ ОТЧЕТА/ПОДАТКОВ ===
    if user_id in reports_request and reports_request[user_id].get("stage") == "await_contact":
        req_type = reports_request[user_id].get("type")
        note = ""
        if req_type == "submit":
            note = (
                f"<b>Заявка на подання звітності</b>\n"
                f"Від: {escape(user_name)}\n"
                f"ID: <pre>{user_id}</pre>\n"
            )
            if text:
                note += f"Контакти для звітності: <pre>{escape(text.strip())}</pre>"
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
            send_message(user_id, "Дякую! Ваші дані отримано, звітність буде підготовлена найближчим часом. Якщо потрібно щось ще — пишіть!", reply_markup=main_menu_markup())
            reports_request.pop(user_id, None)
            return "ok", 200
        elif req_type == "taxcheck":
            note = (
                f"<b>Запит на перевірку ФОП/податків</b>\n"
                f"Від: {escape(user_name)}\n"
                f"ID: <pre>{user_id}</pre>\n"
            )
            if text:
                note += f"Контакти для перевірки: <pre>{escape(text.strip())}</pre>"
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
            send_message(user_id, "Дякую! Перевірка буде виконана і вся інформація надана у відповідь. Якщо потрібно щось ще — пишіть!", reply_markup=main_menu_markup())
            reports_request.pop(user_id, None)
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

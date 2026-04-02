import asyncio
import logging
import json
import os
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from datetime import datetime

# --- ДАННЫЕ ---
API_TOKEN = os.environ.get("API_TOKEN", "8381146744:AAGifGXeiWvMFTZ3jRzWrse6hz3-uslkSkI")
CRYPTO_TOKEN = os.environ.get("CRYPTO_TOKEN", "560696:AAGcjeTB1aNDJAajb5g3YGqzQkZ7ZjH1DJS")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "5035967198"))
FILE_URL = "https://files.fm/u/bz4eqrfvfv"
DB_FILE = "purchases.json"

CRYPTO_API = "https://pay.crypt.bot/api"
PRODUCT_PRICE = 2.5
PRODUCT_NAME = "Sheet RAT"
PRODUCT_UAH = 100

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_purchase(user_id, username, full_name, product, price_usdt, price_uah):
    db = load_db()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {"username": username, "full_name": full_name, "purchases": [], "total_spent_uah": 0}
    db[uid]["purchases"].append({
        "product": product,
        "price_usdt": price_usdt,
        "price_uah": price_uah,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M")
    })
    db[uid]["total_spent_uah"] += price_uah
    db[uid]["username"] = username
    db[uid]["full_name"] = full_name
    save_db(db)

def get_user(user_id):
    db = load_db()
    return db.get(str(user_id))

# --- CRYPTOBOT ---
async def create_invoice(amount: float, description: str):
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "asset": "USDT",
        "amount": str(amount),
        "description": description,
        "expires_in": 3600
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{CRYPTO_API}/createInvoice",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return data["result"]
                logging.error(f"CryptoBot error: {data}")
                return None
        except Exception as e:
            logging.error(f"Ошибка создания счёта: {e}")
            return None

async def check_invoice(invoice_id: int):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{CRYPTO_API}/getInvoices",
                params={"invoice_ids": str(invoice_id)},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                items = data.get("result", {}).get("items", [])
                return items[0] if items else None
        except Exception as e:
            logging.error(f"Ошибка проверки счёта: {e}")
            return None

# --- КЛАВИАТУРА ---
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Каталог"), KeyboardButton(text="ℹ️ Инфо")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🔑 Админка")]
    ], resize_keyboard=True)

# --- ХЭНДЛЕРЫ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(
        f"👋 Привет, *{m.from_user.first_name}*!\n\nДобро пожаловать в магазин. Выбери раздел:",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )
    try:
        await bot.send_message(
            ADMIN_ID,
            f"👤 *Новый пользователь!*\n\n"
            f"├ 🏷 Имя: {m.from_user.full_name}\n"
            f"├ 👤 Юзернейм: @{m.from_user.username or '—'}\n"
            f"├ 🆔 ID: `{m.from_user.id}`\n"
            f"└ 🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка уведомления админа: {e}")

@dp.message(F.text == "ℹ️ Инфо")
async def info(m: types.Message):
    await m.answer(
        "ℹ️ *О магазине*\n\n"
        "Здесь продаются только чистые софты по дешёвке 🧹\n\n"
        "📦 Скоро будут новые товары, но пока что есть то что есть!\n\n"
        "✅ Все файлы проверены и безопасны\n"
        "⚡️ Выдача моментальная — сразу после оплаты\n"
        "💬 Вопросы? Пиши администратору",
        parse_mode="Markdown"
    )

@dp.message(F.text == "👤 Профиль")
async def profile(m: types.Message):
    user = get_user(m.from_user.id)
    if not user or not user["purchases"]:
        await m.answer(
            f"👤 *Твой профиль*\n\n"
            f"├ 🏷 Имя: {m.from_user.full_name}\n"
            f"├ 👤 Юзернейм: @{m.from_user.username or '—'}\n"
            f"├ 🆔 ID: `{m.from_user.id}`\n\n"
            f"🛒 Покупок: *0*\n"
            f"💰 Потрачено: *0 UAH*\n\n"
            f"_Ты ещё ничего не покупал_",
            parse_mode="Markdown"
        )
        return

    purchases_text = ""
    for i, p in enumerate(user["purchases"], 1):
        purchases_text += f"  {i}. 📦 {p['product']} — {p['price_uah']} UAH ({p['date']})\n"

    await m.answer(
        f"👤 *Твой профиль*\n\n"
        f"├ 🏷 Имя: {m.from_user.full_name}\n"
        f"├ 👤 Юзернейм: @{m.from_user.username or '—'}\n"
        f"├ 🆔 ID: `{m.from_user.id}`\n\n"
        f"🛒 Покупок: *{len(user['purchases'])}*\n"
        f"💰 Потрачено: *{user['total_spent_uah']} UAH*\n\n"
        f"📋 *История покупок:*\n{purchases_text}",
        parse_mode="Markdown"
    )

@dp.message(F.text == "🔑 Админка")
async def admin(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("❌ У тебя нет доступа!")
        return

    db = load_db()
    if not db:
        await m.answer("📊 *Админ панель*\n\n_Покупок пока нет_", parse_mode="Markdown")
        return

    total_purchases = sum(len(u["purchases"]) for u in db.values())
    total_revenue_uah = sum(u["total_spent_uah"] for u in db.values())
    total_revenue_usdt = sum(p["price_usdt"] for u in db.values() for p in u["purchases"])

    all_purchases = []
    for uid, udata in db.items():
        for p in udata["purchases"]:
            all_purchases.append({
                "name": udata["full_name"],
                "username": udata.get("username", "—"),
                "product": p["product"],
                "price_uah": p["price_uah"],
                "price_usdt": p["price_usdt"],
                "date": p["date"]
            })

    all_purchases.sort(key=lambda x: x["date"], reverse=True)

    last_text = ""
    for p in all_purchases[:5]:
        last_text += (
            f"\n├ 👤 {p['name']} (@{p['username'] or '—'})\n"
            f"├ 📦 {p['product']}\n"
            f"├ 💰 {p['price_uah']} UAH ({p['price_usdt']} USDT)\n"
            f"└ 🕐 {p['date']}\n"
        )

    await m.answer(
        f"🔑 *Админ панель*\n\n"
        f"📊 *Статистика:*\n"
        f"├ 👥 Всего юзеров: *{len(db)}*\n"
        f"├ 🛒 Всего покупок: *{total_purchases}*\n"
        f"├ 💵 Выручка: *{total_revenue_usdt} USDT*\n"
        f"└ 💰 Выручка: *{total_revenue_uah} UAH*\n\n"
        f"🕐 *Последние покупки:*\n{last_text if last_text else '_пусто_'}",
        parse_mode="Markdown"
    )

@dp.message(F.text == "🛒 Каталог")
async def catalog(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 КУПИТЬ SHEET RAT — 100 UAH", callback_data="buy_sheetrat")]
    ])
    await m.answer(
        f"📂 *Каталог товаров*\n\n"
        f"📦 *{PRODUCT_NAME}*\n"
        f"💰 Цена: *{PRODUCT_UAH} UAH* (~{PRODUCT_PRICE} USDT)\n"
        f"✅ Чистый, проверенный софт\n\n"
        f"Нажми кнопку ниже чтобы купить 👇",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "buy_sheetrat")
async def handle_buy(c: types.CallbackQuery):
    await c.answer("⏳ Создаю счёт...")
    await c.message.edit_text("⏳ *Создаю счёт на оплату...*", parse_mode="Markdown")

    invoice = await create_invoice(
        amount=PRODUCT_PRICE,
        description=f"Покупка: {PRODUCT_NAME}"
    )

    if not invoice:
        await c.message.edit_text(
            "❌ Не удалось создать счёт. Попробуй позже или напиши администратору."
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через CryptoBot", url=invoice["pay_url"])],
        [InlineKeyboardButton(text="✅ Я оплатил — проверить", callback_data=f"check_{invoice['invoice_id']}")]
    ])

    await c.message.edit_text(
        f"💳 *Счёт создан!*\n\n"
        f"📦 Товар: *{PRODUCT_NAME}*\n"
        f"💰 Сумма: *{PRODUCT_PRICE} USDT* (~{PRODUCT_UAH} UAH)\n"
        f"🆔 Счёт: `{invoice['invoice_id']}`\n\n"
        f"1️⃣ Нажми *«Оплатить»* — откроется CryptoBot\n"
        f"2️⃣ После оплаты нажми *«Я оплатил»*\n\n"
        f"⏰ Счёт действует *1 час*",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(c: types.CallbackQuery):
    await c.answer("⏳ Проверяю оплату...")

    invoice_id = int(c.data.split("_")[1])
    invoice = await check_invoice(invoice_id)

    if not invoice:
        await c.message.answer("❌ Ошибка при проверке. Попробуй ещё раз.")
        return

    status = invoice.get("status")

    if status == "paid":
        add_purchase(
            user_id=c.from_user.id,
            username=c.from_user.username or "—",
            full_name=c.from_user.full_name,
            product=PRODUCT_NAME,
            price_usdt=PRODUCT_PRICE,
            price_uah=PRODUCT_UAH
        )
        await c.message.edit_text(
            f"✅ *Оплата подтверждена!*\n\n"
            f"📦 Твой файл готов:\n{FILE_URL}\n\n"
            f"_Спасибо за покупку!_",
            parse_mode="Markdown"
        )
        try:
            await bot.send_message(
                ADMIN_ID,
                f"💰 *НОВАЯ ОПЛАТА!*\n\n"
                f"├ 🏷 Имя: {c.from_user.full_name}\n"
                f"├ 👤 Юзернейм: @{c.from_user.username or '—'}\n"
                f"├ 🆔 ID: `{c.from_user.id}`\n"
                f"├ 📦 Товар: {PRODUCT_NAME}\n"
                f"├ 💵 Сумма: {PRODUCT_PRICE} USDT ({PRODUCT_UAH} UAH)\n"
                f"└ 🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Ошибка уведомления: {e}")

    elif status == "active":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=invoice.get("pay_url", ""))],
            [InlineKeyboardButton(text="✅ Я оплатил — проверить", callback_data=f"check_{invoice_id}")]
        ])
        await c.message.edit_text(
            f"❌ *Вы не оплатили товар*\n\n"
            f"Оплата по счёту `{invoice_id}` ещё не поступила.\n\n"
            f"Нажми *«Оплатить»* и после оплаты снова нажми проверить 👇",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    elif status == "expired":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Создать новый счёт", callback_data="buy_sheetrat")]
        ])
        await c.message.edit_text(
            "⌛ *Счёт истёк!*\n\nВремя оплаты вышло. Создай новый счёт 👇",
            reply_markup=kb,
            parse_mode="Markdown"
        )

# --- ЗАПУСК С ЗАЩИТОЙ ОТ ОШИБОК ---
async def main():
    logging.info("Бот запускается...")
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except TelegramRetryAfter as e:
            logging.warning(f"RetryAfter: ждём {e.retry_after} сек...")
            await asyncio.sleep(e.retry_after)
        except TelegramNetworkError as e:
            logging.error(f"NetworkError: {e} — перезапуск через 5 сек...")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Неизвестная ошибка: {e} — перезапуск через 10 сек...")
            await asyncio.sleep(10)

if __name__ == '__main__':
    asyncio.run(main())
```

---

**`requirements.txt`**
```
aiogram==3.7.0
aiohttp==3.9.5

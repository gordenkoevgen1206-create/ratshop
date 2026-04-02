import asyncio
import logging
import json
import os
import threading
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from datetime import datetime

API_TOKEN = os.environ.get("API_TOKEN")
CRYPTO_TOKEN = os.environ.get("CRYPTO_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
FILE_URL = "https://files.fm/u/bz4eqrfvfv"
DB_FILE = "purchases.json"
CRYPTO_API = "https://pay.crypt.bot/api"
PRODUCT_PRICE = 2.5
PRODUCT_NAME = "Sheet RAT"
PRODUCT_UAH = 100

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- ФЕЙКОВЫЙ ВЕБ-СЕРВЕР ДЛЯ RENDER ---
def run_web():
    async def health(request):
        return web.Response(text="OK")
    app = web.Application()
    app.router.add_get("/", health)
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), print=None)

threading.Thread(target=run_web, daemon=True).start()

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

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

async def create_invoice(amount, description):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN, "Content-Type": "application/json"}
    payload = {"asset": "USDT", "amount": str(amount), "description": description, "expires_in": 3600}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{CRYPTO_API}/createInvoice", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return data["result"]
                logging.error(f"CryptoBot error: {data}")
                return None
        except Exception as e:
            logging.error(f"Ошибка создания счёта: {e}")
            return None

async def check_invoice(invoice_id):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{CRYPTO_API}/getInvoices", params={"invoice_ids": str(invoice_id)}, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                items = data.get("result", {}).get("items", [])
                return items[0] if items else None
        except Exception as e:
            logging.error(f"Ошибка проверки: {e}")
            return None

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Каталог"), KeyboardButton(text="ℹ️ Инфо")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🔑 Админка")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"👋 Привет, *{m.from_user.first_name}*!\n\nДобро пожаловать в магазин. Выбери раздел:", reply_markup=main_kb(), parse_mode="Markdown")
    try:
        await bot.send_message(ADMIN_ID, f"👤 *Новый пользователь!*\n\n├ 🏷 Имя: {m.from_user.full_name}\n├ 👤 Юзернейм: @{m.from_user.username or '—'}\n├ 🆔 ID: `{m.from_user.id}`\n└ 🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка уведомления: {e}")

@dp.message(F.text == "ℹ️ Инфо")
async def info(m: types.Message):
    await m.answer("ℹ️ *О магазине*\n\nЗдесь продаются только чистые софты по дешёвке 🧹\n\n📦 Скоро будут новые товары!\n\n✅ Все файлы проверены и безопасны\n⚡️ Выдача моментальная — сразу после оплаты", parse_mode="Markdown")

@dp.message(F.text == "👤 Профиль")
async def profile(m: types.Message):
    user = get_user(m.from_user.id)
    if not user or not user["purchases"]:
        await m.answer(f"👤 *Твой профиль*\n\n├ 🏷 Имя: {m.from_user.full_name}\n├ 👤 Юзернейм: @{m.from_user.username or '—'}\n├ 🆔 ID: `{m.from_user.id}`\n\n🛒 Покупок: *0*\n💰 Потрачено: *0 UAH*\n\n_Ты ещё ничего не покупал_", parse_mode="Markdown")
        return
    purchases_text = ""
    for i, p in enumerate(user["purchases"], 1):
        purchases_text += f"  {i}. 📦 {p['product']} — {p['price_uah']} UAH ({p['date']})\n"
    await m.answer(f"👤 *Твой профиль*\n\n├ 🏷 Имя: {m.from_user.full_name}\n├ 👤 Юзернейм: @{m.from_user.username or '—'}\n├ 🆔 ID: `{m.from_user.id}`\n\n🛒 Покупок: *{len(user['purchases'])}*\n💰 Потрачено: *{user['total_spent_uah']} UAH*\n\n📋 *История покупок:*\n{purchases_text}", parse_mode="Markdown")

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
            all_purchases.append({"name": udata["full_name"], "username": udata.get("username", "—"), "product": p["product"], "price_uah": p["price_uah"], "price_usdt": p["price_usdt"], "date": p["date"]})
    all_purchases.sort(key=lambda x: x["date"], reverse=True)
    last_text = ""
    for p in all_purchases[:5]:
        last_text += f"\n├ 👤 {p['name']} (@{p['username'] or '—'})\n├ 📦 {p['product']}\n├ 💰 {p['price_uah']} UAH ({p['price_usdt']} USDT)\n└ 🕐 {p['date']}\n"
    await m.answer(f"🔑 *Админ панель*\n\n📊 *Статистика:*\n├ 👥 Юзеров: *{len(db)}*\n├ 🛒 Покупок: *{total_purchases}*\n├ 💵 Выручка: *{total_revenue_usdt} USDT*\n└ 💰 Выручка: *{total_revenue_uah} UAH*\n\n🕐 *Последние покупки:*\n{last_text if last_text else '_пусто_'}", parse_mode="Markdown")

@dp.message(F.text == "🛒 Каталог")
async def catalog(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 КУПИТЬ SHEET RAT — 100 UAH", callback_data="buy_sheetrat")]])
    await m.answer(f"📂 *Каталог товаров*\n\n📦 *{PRODUCT_NAME}*\n💰 Цена: *{PRODUCT_UAH} UAH* (~{PRODUCT_PRICE} USDT)\n✅ Чистый, проверенный софт\n\nНажми кнопку ниже 👇", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "buy_sheetrat")
async def handle_buy(c: types.CallbackQuery):
    await c.answer("⏳ Создаю счёт...")
    await c.message.edit_text("⏳ *Создаю счёт на оплату...*", parse_mode="Markdown")
    invoice = await create_invoice(PRODUCT_PRICE, f"Покупка: {PRODUCT_NAME}")
    if not invoice:
        await c.message.edit_text("❌ Не удалось создать счёт. Попробуй позже.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через CryptoBot", url=invoice["pay_url"])],
        [InlineKeyboardButton(text="✅ Я оплатил — проверить", callback_data=f"check_{invoice['invoice_id']}")]
    ])
    await c.message.edit_text(f"💳 *Счёт создан!*\n\n📦 Товар: *{PRODUCT_NAME}*\n💰 Сумма: *{PRODUCT_PRICE} USDT* (~{PRODUCT_UAH} UAH)\n🆔 Счёт: `{invoice['invoice_id']}`\n\n1️⃣ Нажми *«Оплатить»*\n2️⃣ После оплаты нажми *«Я оплатил»*\n\n⏰ Счёт действует *1 час*", reply_markup=kb, parse_mode="Markdown")

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
        add_purchase(c.from_user.id, c.from_user.username or "—", c.from_user.full_name, PRODUCT_NAME, PRODUCT_PRICE, PRODUCT_UAH)
        await c.message.edit_text(f"✅ *Оплата подтверждена!*\n\n📦 Твой файл:\n{FILE_URL}\n\n_Спасибо за покупку!_", parse_mode="Markdown")
        try:
            await bot.send_message(ADMIN_ID, f"💰 *НОВАЯ ОПЛАТА!*\n\n├ 🏷 Имя: {c.from_user.full_name}\n├ 👤 Юзернейм: @{c.from_user.username or '—'}\n├ 🆔 ID: `{c.from_user.id}`\n├ 📦 Товар: {PRODUCT_NAME}\n├ 💵 Сумма: {PRODUCT_PRICE} USDT ({PRODUCT_UAH} UAH)\n└ 🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}", parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Ошибка уведомления: {e}")
    elif status == "active":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=invoice.get("pay_url", ""))],
            [InlineKeyboardButton(text="✅ Я оплатил — проверить", callback_data=f"check_{invoice_id}")]
        ])
        await c.message.edit_text(f"❌ *Вы не оплатили товар*\n\nОплата по счёту `{invoice_id}` ещё не поступила.\n\nНажми *«Оплатить»* и после нажми проверить 👇", reply_markup=kb, parse_mode="Markdown")
    elif status == "expired":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Создать новый счёт", callback_data="buy_sheetrat")]])
        await c.message.edit_text("⌛ *Счёт истёк!*\n\nВремя вышло. Создай новый счёт 👇", reply_markup=kb, parse_mode="Markdown")

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
            logging.error(f"Ошибка: {e} — перезапуск через 10 сек...")
            await asyncio.sleep(10)

if __name__ == '__main__':
    asyncio.run(main())

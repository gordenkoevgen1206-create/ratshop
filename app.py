import os
import asyncio
import logging
import json
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8381146744:AAGifGXeiWvMFTZ3jRzWrse6hz3-uslkSkI'
CRYPTO_TOKEN = '560696:AAGcjeTB1aNDJAajb5g3YGqzQkZ7ZjH1DJS'
ADMIN_ID = 5035967198
FILE_URL = "https://files.fm/u/bz4eqrfvfv"
DB_FILE = "purchases.json"

CRYPTO_API = "https://pay.crypt.bot/api"
PRODUCT_PRICE = 2.5
PRODUCT_NAME = "Sheet RAT"
PRODUCT_UAH = 100

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: 
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_purchase(user_id, username, full_name, product, price_usdt, price_uah):
    db = load_db()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {"username": username, "full_name": full_name, "purchases": [], "total_spent_uah": 0}
    db[uid]["purchases"].append({
        "product": product, "price_usdt": price_usdt, "price_uah": price_uah,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M")
    })
    db[uid]["total_spent_uah"] += price_uah
    save_db(db)

# --- CRYPTOBOT API ---
async def create_invoice(amount, description):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN, "Content-Type": "application/json"}
    payload = {"asset": "USDT", "amount": str(amount), "description": description, "expires_in": 3600}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{CRYPTO_API}/createInvoice", json=payload, headers=headers) as resp:
                data = await resp.json()
                return data["result"] if data.get("ok") else None
        except: return None

async def check_invoice(invoice_id):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{CRYPTO_API}/getInvoices", params={"invoice_ids": str(invoice_id)}, headers=headers) as resp:
                data = await resp.json()
                items = data.get("result", {}).get("items", [])
                return items[0] if items else None
        except: return None

# --- КЛАВИАТУРЫ ---
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Каталог"), KeyboardButton(text="ℹ️ Инфо")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🔑 Админка")]
    ], resize_keyboard=True)

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"👋 Привет, *{m.from_user.first_name}*!\nДобро пожаловать в магазин.", reply_markup=main_kb(), parse_mode="Markdown")

@dp.message(F.text == "ℹ️ Инфо")
async def info(m: types.Message):
    await m.answer(
        "ℹ️ *О магазине*\n\n"
        "Здесь продаются только чистые софты 🧹\n"
        "⚡️ Выдача моментальная — сразу после оплаты\n"
        "💬 По всем вопросам к админу.",
        parse_mode="Markdown"
    )

@dp.message(F.text == "👤 Профиль")
async def profile(m: types.Message):
    db = load_db()
    user = db.get(str(m.from_user.id))
    if not user or not user.get("purchases"):
        await m.answer(f"👤 *Профиль*\n\nПокупок пока нет.", parse_mode="Markdown")
        return
    
    text = f"👤 *Профиль*\n💰 Потрачено: {user['total_spent_uah']} UAH\n\n*История:* \n"
    for i, p in enumerate(user["purchases"], 1):
        text += f"{i}. {p['product']} ({p['date']})\n"
    await m.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🔑 Админка")
async def admin_panel(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("❌ Нет доступа")
        return
    db = load_db()
    total_uah = sum(u["total_spent_uah"] for u in db.values())
    await m.answer(f"🔑 *Админка*\n\n👥 Юзеров: {len(db)}\n💰 Общая выручка: {total_uah} UAH", parse_mode="Markdown")

@dp.message(F.text == "🛒 Каталог")
async def catalog(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 КУПИТЬ SHEET RAT — 100 UAH", callback_data="buy_sheetrat")]])
    await m.answer(f"📦 *{PRODUCT_NAME}*\n💰 Цена: *{PRODUCT_UAH} UAH*", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "buy_sheetrat")
async def handle_buy(c: types.CallbackQuery):
    invoice = await create_invoice(PRODUCT_PRICE, f"Покупка: {PRODUCT_NAME}")
    if not invoice:
        await c.answer("❌ Ошибка платежки", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=invoice["pay_url"])],
        [InlineKeyboardButton(text="✅ Проверить", callback_data=f"check_{invoice['invoice_id']}")]
    ])
    await c.message.edit_text(f"💳 Счёт №`{invoice['invoice_id']}` создан!", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(c: types.CallbackQuery):
    inv_id = int(c.data.split("_")[1])
    invoice = await check_invoice(inv_id)
    if invoice and invoice.get("status") == "paid":
        add_purchase(c.from_user.id, c.from_user.username, c.from_user.full_name, PRODUCT_NAME, PRODUCT_PRICE, PRODUCT_UAH)
        await c.message.edit_text(f"✅ Оплачено!\n\nСсылка:\n{FILE_URL}")
    else:
        await c.answer("❌ Оплата не найдена", show_alert=True)

# --- СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is working!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv('PORT', 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    await asyncio.gather(start_web_server(), dp.start_polling(bot))

if __name__ == '__main__':
    asyncio.run(main())

import os
from aiohttp import web

# Этот кусок кода нужен только для того, чтобы Render не убивал процесс
async def handle(request):
    return web.Response(text="Bot is live!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', 10000)))
    await site.start()

# В своей основной функции main() добавь вызов сервера:
# async def main():
#     await start_web_server()  <-- Добавь это ПЕРЕД запуском polling
#     await dp.start_polling(bot)

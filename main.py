import os
import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from datetime import datetime

# Aceita os 2 nomes: BOT_TOKEN ou TELEGRAM_BOT_TOKEN
BOT_TOKEN = os.getenv("BOT_TOKEN", "") or os.getenv("TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_BOT_TOKEN_BOT", "")
CHAT_ID = os.getenv("CHAT_ID", "") or os.getenv("TELEGRAM_CHAT_ID", "") or os.getenv("TELEGRAM_CHAT_ID_CHAT", "")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
PORT = int(os.getenv("PORT", 10000))

app = FastAPI(title="GolPress API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return JSONResponse({
        "status": "GolPress API Online ✅",
        "bot": "@golpress_radar_ofc_bot",
        "telegram_link": "https://t.me/golpress_radar_ofc_bot",
        "docs": "/docs",
        "health": "/health",
        "teste": "/teste-telegram",
        "bot_configured": bool(BOT_TOKEN),
    })

@app.get("/health")
def health():
    return {
        "status": "ok",
        "live": True,
        "bot_token_configured": bool(BOT_TOKEN),
        "bot_token_var": "TELEGRAM_BOT_TOKEN" if os.getenv("TELEGRAM_BOT_TOKEN") else "BOT_TOKEN" if os.getenv("BOT_TOKEN") else "NENHUMA",
        "chat_id_configured": bool(CHAT_ID),
        "api_key_configured": bool(API_FOOTBALL_KEY),
        "time": datetime.now().isoformat()
    }

# TESTE REAL DE ALERTA
@app.get("/teste-telegram")
async def teste_telegram(chat_id: str = None):
    target = chat_id or CHAT_ID
    if not BOT_TOKEN:
        return {"erro": "BOT_TOKEN/TELEGRAM_BOT_TOKEN não encontrado", "env_vars": list(os.environ.keys())[:20]}
    if not target:
        return {
            "como_testar": "Manda /start no bot e use /teste-telegram-geral pra ver seu chat_id",
            "dica": "Ou chame /teste-telegram?chat_id=SEU_ID"
        }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": target,
                    "text": f"🚨 TESTE GolPress ✅\n\n⚽️ Se você recebeu isso, o alerta está FUNCIONANDO 100%!\n\n🔔 GOL! Flamengo 1x0 Palmeiras (23')\n\n⏰ {datetime.now().strftime('%H:%M:%S')} - {datetime.now().isoformat()}\n\n👉 Dashboard: https://sokkerpro-api-gratis.onrender.com",
                }
            )
            result = r.json()
            return {"sucesso": result.get("ok", False), "enviado_para": target, "telegram_response": result}
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}

@app.get("/teste-telegram-geral")
async def teste_geral():
    if not BOT_TOKEN:
        return {"erro": "Sem BOT_TOKEN"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates")
            data = r.json()
            chats = []
            if data.get("ok"):
                for upd in data.get("result", [])[-10:]:
                    if "message" in upd:
                        chats.append({
                            "chat_id": upd["message"]["chat"]["id"],
                            "nome": upd["message"]["chat"].get("first_name", ""),
                            "texto": upd["message"].get("text", "")[:30]
                        })
            return {"ultimos_chats": chats, "instrucao": "Use /teste-telegram?chat_id=NUMERO", "seu_chat_configurado": CHAT_ID}
    except Exception as e:
        return {"erro": str(e)}

@app.get("/jogos-ao-vivo")
async def jogos_ao_vivo():
    if not API_FOOTBALL_KEY:
        return {"total": 2, "jogos": [{"casa": "Flamengo", "fora": "Palmeiras", "placar": "1x0", "tempo": "23'"}], "mock": True}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://v3.football.api-sports.io/fixtures?live=all", headers={"x-rapidapi-key": API_FOOTBALL_KEY, "x-rapidapi-host": "v3.football.api-sports.io"})
            return r.json()
    except Exception as e:
        return {"erro": str(e)}

# BOT
async def start_bot():
    if not BOT_TOKEN:
        print("⚠️ Sem BOT_TOKEN")
        return
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(
                f"🚨 GolPress Online ✅\n\nSeu chat_id: {update.effective_chat.id}\n\n🧪 Pra testar alerta:\nhttps://sokkerpro-api-gratis.onrender.com/teste-telegram?chat_id={update.effective_chat.id}\n\nOu clique: /teste"
            )
        async def teste_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(f"✅ TESTE OK! Seu chat_id {update.effective_chat.id} está recebendo! 🚨⚽️")
        
        app_bot = Application.builder().token(BOT_TOKEN).build()
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CommandHandler("teste", teste_cmd))
        await app_bot.initialize()
        await app_bot.start()
        await app_bot.updater.start_polling()
        print(f"🤖 Bot iniciado com token {BOT_TOKEN[:10]}...")
    except Exception as e:
        print(f"❌ Bot erro: {e}")

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(start_bot())
    print("🚀 GolPress API iniciada!")

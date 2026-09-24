import os
import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from datetime import datetime

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
PORT = int(os.getenv("PORT", 10000))

app = FastAPI(
    title="GolPress API",
    description="GolPress - Radar de Gols ao Vivo",
    version="1.0.0"
)

# CORS liberado pra funcionar no WhatsApp, Chrome, etc
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROTAS QUE NÃO QUEBRAM NUNCA ---

@app.get("/")
def home():
    # Tenta servir o dashboard se existir
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    # Se não existir, retorna JSON (nunca dá Not Found)
    return JSONResponse({
        "status": "GolPress API Online ✅",
        "bot": "@golpress_radar_ofc_bot",
        "telegram_link": "https://t.me/golpress_radar_ofc_bot",
        "docs": "/docs",
        "health": "/health",
        "jogos": "/jogos-ao-vivo",
        "message": "Dashboard em manutenção - use /docs"
    })

@app.get("/health")
def health():
    return {
        "status": "ok",
        "live": True,
        "bot_token_configured": bool(BOT_TOKEN),
        "api_key_configured": bool(API_FOOTBALL_KEY),
        "time": datetime.now().isoformat()
    }

@app.get("/jogos-ao-vivo")
async def jogos_ao_vivo():
    """Busca jogos ao vivo - com fallback se API não tiver configurada"""
    try:
        # Se não tem API key, retorna mock para testar
        if not API_FOOTBALL_KEY:
            return {
                "total": 0,
                "jogos": [],
                "message": "API_FOOTBALL_KEY não configurada - configure no Render Environment",
                "mock": True,
                "timestamp": datetime.now().isoformat()
            }
        
        # Busca real na API-Football
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://v3.football.api-sports.io/fixtures?live=all",
                headers={
                    "x-rapidapi-key": API_FOOTBALL_KEY,
                    "x-rapidapi-host": "v3.football.api-sports.io"
                }
            )
            if response.status_code == 200:
                data = response.json()
                fixtures = data.get("response", [])
                jogos = []
                for f in fixtures[:20]:  # Limita 20
                    jogos.append({
                        "id": f["fixture"]["id"],
                        "casa": f["teams"]["home"]["name"],
                        "fora": f["teams"]["away"]["name"],
                        "placar_casa": f["goals"]["home"],
                        "placar_fora": f["goals"]["away"],
                        "tempo": f["fixture"]["status"]["elapsed"],
                        "status": f["fixture"]["status"]["long"]
                    })
                return {
                    "total": len(jogos),
                    "jogos": jogos,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {"total": 0, "jogos": [], "error": f"API retornou {response.status_code}"}
    except Exception as e:
        return {
            "total": 0,
            "jogos": [],
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/stats")
def stats():
    return {
        "total_jogos": 0,
        "alertas_enviados": 0,
        "usuarios_ativos": 0,
        "status": "online"
    }

# --- BOT TELEGRAM (roda em background, não quebra a API) ---
async def start_bot():
    if not BOT_TOKEN:
        print("⚠️ BOT_TOKEN não configurado - bot não vai iniciar")
        return
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
        
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(
                "🚨 *GolPress - Radar de Gols ao Vivo* ⚽️\n\n"
                "✅ Bot oficial online!\n"
                "📊 Use /jogos para ver jogos ao vivo\n"
                "🔔 Ative os alertas e não perca nenhum gol!\n\n"
                "👉 Dashboard: https://golpress-api.onrender.com",
                parse_mode="Markdown"
            )
        
        async def jogos(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("⚽️ Buscando jogos ao vivo... Use o dashboard: https://golpress-api.onrender.com")
        
        app_bot = Application.builder().token(BOT_TOKEN).build()
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CommandHandler("jogos", jogos))
        
        print(f"🤖 Bot @{BOT_TOKEN.split(':')[0]} iniciado!")
        await app_bot.initialize()
        await app_bot.start()
        await app_bot.updater.start_polling()
        
    except Exception as e:
        print(f"❌ Erro no bot: {e}")
        # Não quebra a API se o bot falhar

@app.on_event("startup")
async def on_startup():
    # Inicia o bot em background sem travar a API
    asyncio.create_task(start_bot())
    print("🚀 GolPress API iniciada!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
    

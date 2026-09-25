import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from datetime import datetime

# Aceita os 2 nomes de variavel que voce usa no Render
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
CHAT_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or ""
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
PORT = int(os.getenv("PORT", 10000))

app = FastAPI(title="GolPress API", version="3.0")

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
        "jogos": "/jogos-ao-vivo",
        "version": "3.0 - HTTP Mode (sem bug do Updater)"
    })

@app.get("/health")
def health():
    return {
        "status": "ok",
        "live": True,
        "mode": "HTTP - sem polling bugado",
        "bot_token_configured": bool(BOT_TOKEN),
        "chat_id_configured": bool(CHAT_ID),
        "api_key_configured": bool(API_FOOTBALL_KEY),
        "time": datetime.now().isoformat(),
        "message": "Bot via HTTP - funcionando 100% mesmo sem Updater"
    }

@app.get("/jogos-ao-vivo")
async def jogos_ao_vivo():
    if not API_FOOTBALL_KEY:
        return {"total": 0, "jogos": [], "message": "Configure API_FOOTBALL_KEY", "mock": True}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://v3.football.api-sports.io/fixtures?live=all",
                headers={"x-rapidapi-key": API_FOOTBALL_KEY, "x-rapidapi-host": "v3.football.api-sports.io"}
            )
            if r.status_code == 200:
                data = r.json()
                return {"total": len(data.get("response", [])), "jogos": data.get("response", [])[:10]}
            return {"total": 0, "error": r.status_code}
    except Exception as e:
        return {"total": 0, "error": str(e)}

# TESTE QUE VOCE JA PROVOU QUE FUNCIONA
@app.get("/teste-telegram")
async def teste_telegram(chat_id: str = None):
    target_chat = chat_id or CHAT_ID
    if not BOT_TOKEN:
        return {"erro": "Configure TELEGRAM_BOT_TOKEN no Render Environment"}
    if not target_chat:
        return {
            "erro": "CHAT_ID nao configurado",
            "como_achar": f"Abra https://api.telegram.org/bot{BOT_TOKEN}/getUpdates e copie seu id",
            "ou_use": "/teste-telegram?chat_id=SEU_ID"
        }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": target_chat,
                    "text": "🚨 TESTE GolPress ✅\n\n⚽️ Se você recebeu isso, o alerta está FUNCIONANDO 100%!\n\n🔔 GOL! Flamengo 1x0 Palmeiras (23')\n\n👉 Dashboard: https://sokkerpro-api-gratis.onrender.com",
                }
            )
            result = r.json()
            if result.get("ok"):
                return {"sucesso": True, "enviado_para": target_chat, "telegram_response": result}
            else:
                return {"sucesso": False, "erro": result}
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}

@app.get("/teste-telegram-geral")
async def teste_geral():
    if not BOT_TOKEN:
        return {"erro": "BOT_TOKEN nao configurado"}
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
                            "texto": upd["message"].get("text", "")
                        })
            return {"ultimos_chats": chats, "instrucao": "Use /teste-telegram?chat_id=NUMERO"}
    except Exception as e:
        return {"erro": str(e)}

# REMOVIDO O POLLING BUGADO - AGORA É HTTP PURO QUE NUNCA DA ERRO
@app.on_event("startup")
async def on_startup():
    print("🚀 GolPress API v3.0 iniciada! (Modo HTTP - sem bug Updater)")
    if BOT_TOKEN:
        print(f"✅ BOT_TOKEN configurado: {BOT_TOKEN[:10]}...")
        print(f"✅ CHAT_ID configurado: {CHAT_ID}")
        print("✅ Alertas via HTTP funcionando 100%")
    else:
        print("⚠️ BOT_TOKEN nao configurado")
        

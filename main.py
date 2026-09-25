import os
import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
CHAT_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or ""
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
PORT = int(os.getenv("PORT", 10000))

app = FastAPI(title="GolPress API", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Memoria de placares para detectar GOL
placares_anteriores = {}

async def enviar_telegram(texto: str, chat_id_alvo: str = None):
    alvo = chat_id_alvo or CHAT_ID
    if not BOT_TOKEN or not alvo:
        print(f"❌ Não enviado (sem BOT_TOKEN ou CHAT_ID): {texto}")
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": alvo, "text": texto, "parse_mode": "Markdown"}
            )
            data = r.json()
            if data.get("ok"):
                print(f"✅ Telegram enviado para {alvo}: {texto[:80]}")
                return True
            else:
                print(f"❌ Erro Telegram: {data}")
                return False
    except Exception as e:
        print(f"❌ Exceção ao enviar Telegram: {e}")
        return False

async def monitorar_gols():
    print("🔄 Radar de gols iniciado - verificando a cada 30s...")
    await asyncio.sleep(10) # espera api subir
    while True:
        try:
            if not API_FOOTBALL_KEY:
                print("⚠️ API_FOOTBALL_KEY não configurada - radar pausado")
                await asyncio.sleep(60)
                continue
            
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    "https://v3.football.api-sports.io/fixtures?live=all",
                    headers={"x-rapidapi-key": API_FOOTBALL_KEY, "x-rapidapi-host": "v3.football.api-sports.io"}
                )
                if r.status_code != 200:
                    print(f"⚠️ API-Football erro {r.status_code}: {r.text[:200]}")
                    await asyncio.sleep(30)
                    continue
                
                data = r.json()
                jogos = data.get("response", [])
                print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] {len(jogos)} jogos ao vivo encontrados")

                for jogo in jogos:
                    fixture_id = jogo.get("fixture", {}).get("id")
                    times = jogo.get("teams", {})
                    gols = jogo.get("goals", {})
                    status = jogo.get("fixture", {}).get("status", {})
                    minuto = status.get("elapsed")
                    
                    time_casa = times.get("home", {}).get("name", "Casa")
                    time_fora = times.get("away", {}).get("name", "Fora")
                    gols_casa = gols.get("home")
                    gols_fora = gols.get("away")

                    if gols_casa is None or gols_fora is None:
                        continue

                    placar_atual = f"{gols_casa}x{gols_fora}"
                    placar_anterior = placares_anteriores.get(fixture_id)

                    # Se placar mudou e não é 0x0 inicial, é GOL!
                    if placar_anterior and placar_anterior != placar_atual:
                        # Descobrir quem fez o gol
                        prev_casa, prev_fora = map(int, placar_anterior.split("x"))
                        if gols_casa > prev_casa:
                            quem_fez = time_casa
                        else:
                            quem_fez = time_fora
                        
                        msg = f"🚨 *GOL! GOL! GOL!*\n\n⚽️ *{time_casa} {gols_casa}x{gols_fora} {time_fora}*\n⏱️ {minuto}' - {status.get('long', 'Ao vivo')}\n🎯 Gol de: *{quem_fez}*\n\n🔔 GolPress Radar - antes de todo mundo!"
                        await enviar_telegram(msg)
                    
                    placares_anteriores[fixture_id] = placar_atual
                
                # Limpa jogos antigos da memoria
                ids_atuais = {j.get("fixture", {}).get("id") for j in jogos}
                for fid in list(placares_anteriores.keys()):
                    if fid not in ids_atuais:
                        del placares_anteriores[fid]

        except Exception as e:
            print(f"❌ Erro no radar: {e}")
        
        await asyncio.sleep(30)

@app.get("/")
def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return JSONResponse({
        "status": "GolPress API Online ✅ v4.0 - Radar Real",
        "bot": "@golpress_radar_ofc_bot",
        "telegram_link": "https://t.me/golpress_radar_ofc_bot",
        "docs": "/docs",
        "health": "/health",
        "teste": "/teste-telegram",
        "jogos": "/jogos-ao-vivo",
        "version": "4.0 - Radar de Gols Reais 24/7"
    })

@app.get("/health")
def health():
    return {
        "status": "ok",
        "live": True,
        "mode": "V4 - Radar de Gols Reais 24/7",
        "bot_token_configured": bool(BOT_TOKEN),
        "chat_id_configured": bool(CHAT_ID),
        "api_key_configured": bool(API_FOOTBALL_KEY),
        "jogos_monitorados": len(placares_anteriores),
        "time": datetime.now().isoformat(),
        "message": "Radar ativo a cada 30s" if API_FOOTBALL_KEY else "Configure API_FOOTBALL_KEY para ativar radar real"
    }

@app.get("/jogos-ao-vivo")
async def jogos_ao_vivo():
    if not API_FOOTBALL_KEY:
        return {"total": 0, "jogos": [], "message": "Configure API_FOOTBALL_KEY no Render > Environment", "mock": True, "instrucao": "Crie conta em https://www.api-football.com e adicione a chave"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://v3.football.api-sports.io/fixtures?live=all",
                headers={"x-rapidapi-key": API_FOOTBALL_KEY, "x-rapidapi-host": "v3.football.api-sports.io"}
            )
            if r.status_code == 200:
                data = r.json()
                jogos_formatados = []
                for j in data.get("response", [])[:20]:
                    jogos_formatados.append({
                        "id": j.get("fixture", {}).get("id"),
                        "campeonato": j.get("league", {}).get("name"),
                        "casa": j.get("teams", {}).get("home", {}).get("name"),
                        "fora": j.get("teams", {}).get("away", {}).get("name"),
                        "placar": f"{j.get('goals', {}).get('home')}x{j.get('goals', {}).get('away')}",
                        "minuto": j.get("fixture", {}).get("status", {}).get("elapsed"),
                        "status": j.get("fixture", {}).get("status", {}).get("long")
                    })
                return {"total": len(data.get("response", [])), "jogos": jogos_formatados, "real": True, "fonte": "API-Football v3"}
            return {"total": 0, "error": r.status_code, "detalhe": r.text[:300]}
    except Exception as e:
        return {"total": 0, "error": str(e)}

@app.get("/teste-telegram")
async def teste_telegram(chat_id: str = None):
    target_chat = chat_id or CHAT_ID
    if not BOT_TOKEN:
        return {"erro": "Configure TELEGRAM_BOT_TOKEN no Render Environment"}
    if not target_chat:
        return {"erro": "CHAT_ID nao configurado", "como_achar": f"Abra https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"}
    texto = "🚨 *TESTE GolPress v4.0 ✅*\n\n⚽️ Se você recebeu isso, o alerta REAL está FUNCIONANDO 100%!\n\n🔔 *GOL!* Flamengo 1x0 Palmeiras (23')\n\n👉 Dashboard: https://sokkerpro-api-gratis.onrender.com\n👉 Jogos reais: /jogos-ao-vivo"
    sucesso = await enviar_telegram(texto, target_chat)
    return {"sucesso": sucesso, "enviado_para": target_chat, "real": True}

@app.get("/teste-telegram-geral")
async def teste_geral():
    if not BOT_TOKEN:
        return {"erro": "BOT_TOKEN nao configurado"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
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

@app.on_event("startup")
async def on_startup():
    print("🚀 GolPress API v4.0 iniciada! (Radar de Gols Reais)")
    if BOT_TOKEN:
        print(f"✅ BOT_TOKEN configurado: {BOT_TOKEN[:10]}...")
    else:
        print("❌ BOT_TOKEN NAO configurado")
    if CHAT_ID:
        print(f"✅ CHAT_ID configurado: {CHAT_ID}")
    else:
        print("❌ CHAT_ID NAO configurado")
    if API_FOOTBALL_KEY:
        print(f"✅ API_FOOTBALL_KEY configurada: {API_FOOTBALL_KEY[:10]}...")
        print("✅ Radar de gols reais ATIVO - 30s")
    else:
        print("⚠️ API_FOOTBALL_KEY NAO configurada - radar inativo")
    
    # Inicia radar em background
    asyncio.create_task(monitorar_gols())

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

app = FastAPI(title="GolPress API", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

placares_anteriores = {}
alertas_pressao_enviados = {} # para não spamar mesmo jogo

async def enviar_telegram(texto: str, chat_id_alvo: str = None):
    alvo = chat_id_alvo or CHAT_ID
    if not BOT_TOKEN or not alvo:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": alvo, "text": texto, "parse_mode": "Markdown"}
            )
            return r.json().get("ok", False)
    except Exception as e:
        print(f"❌ Telegram erro: {e}")
        return False

async def tem_cartao_vermelho(client, fixture_id: int):
    """Retorna True se tem vermelho no jogo - critério do usuário: IGNORAR esses jogos"""
    try:
        r = await client.get(
            f"https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}",
            headers={"x-rapidapi-key": API_FOOTBALL_KEY, "x-rapidapi-host": "v3.football.api-sports.io"}
        )
        if r.status_code == 200:
            eventos = r.json().get("response", [])
            for ev in eventos:
                if ev.get("type") == "Card" and "Red" in ev.get("detail", ""):
                    return True
        return False
    except:
        return False

async def get_estatisticas(client, fixture_id: int):
    try:
        r = await client.get(
            f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}",
            headers={"x-rapidapi-key": API_FOOTBALL_KEY, "x-rapidapi-host": "v3.football.api-sports.io"}
        )
        if r.status_code == 200:
            return r.json().get("response", [])
        return []
    except:
        return []

def calcular_pressao_score(stats_home, stats_away):
    """Meu critério de pressão 0-10"""
    # stats vem como lista de dicts com team e statistics
    def extrair(team_stats):
        d = {}
        for s in team_stats.get("statistics", []):
            d[s.get("type")] = s.get("value")
        return d
    
    if not stats_home or not stats_away:
        return 0, {}
    
    h = extrair(stats_home)
    a = extrair(stats_away)
    
    # Convertendo valores (as vezes vem None)
    def to_int(v):
        try:
            return int(v) if v is not None else 0
        except:
            return 0
    
    shots_home = to_int(h.get("Total Shots"))
    shots_on_home = to_int(h.get("Shots on Goal"))
    dangerous_home = to_int(h.get("Dangerous Attacks"))
    corners_home = to_int(h.get("Corner Kicks"))
    
    shots_away = to_int(a.get("Total Shots"))
    shots_on_away = to_int(a.get("Shots on Goal"))
    dangerous_away = to_int(a.get("Dangerous Attacks"))
    
    # Critério: time da casa pressionando
    score_home = 0
    # 1. Volume finalização (30%)
    if shots_home >= 12 and shots_on_home >= 4:
        score_home += 3
    elif shots_home >= 8 and shots_on_home >= 2:
        score_home += 2
    
    # 2. Ataques perigosos (25%)
    if dangerous_home >= 30 and dangerous_home > dangerous_away + 15:
        score_home += 2.5
    elif dangerous_home >= 20 and dangerous_home > dangerous_away + 8:
        score_home += 1.5
    
    # 3. Escanteios (20%)
    if corners_home >= 6 and corners_home > 3:
        score_home += 2
    elif corners_home >= 4:
        score_home += 1
    
    # 4. Domínio total - adversário sem chutar
    if shots_away <= 2 and shots_home >= 8:
        score_home += 2.5
    
    # Calcula para time visitante também
    score_away = 0
    if shots_away >= 12 and shots_on_away >= 4:
        score_away += 3
    elif shots_away >= 8 and shots_on_away >= 2:
        score_away += 2
    if dangerous_away >= 30 and dangerous_away > dangerous_home + 15:
        score_away += 2.5
    elif dangerous_away >= 20 and dangerous_away > dangerous_home + 8:
        score_away += 1.5
    if corners_home >= 6: # erro proposital? corrigir
        pass
    if to_int(a.get("Corner Kicks")) >= 6:
        score_away += 2
    elif to_int(a.get("Corner Kicks")) >= 4:
        score_away += 1
    if shots_home <= 2 and shots_away >= 8:
        score_away += 2.5
    
    # Retorna maior pressão
    if score_home >= score_away:
        return min(10, score_home), {"time": "casa", "stats": h, "adversario_stats": a}
    else:
        return min(10, score_away), {"time": "fora", "stats": a, "adversario_stats": h}

async def monitorar_pressao_e_gols():
    print("🔥 Radar V5 Pressão iniciado - SEM jogos com vermelho!")
    await asyncio.sleep(10)
    while True:
        try:
            if not API_FOOTBALL_KEY:
                print("⚠️ Sem API_FOOTBALL_KEY")
                await asyncio.sleep(60)
                continue
            
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(
                    "https://v3.football.api-sports.io/fixtures?live=all",
                    headers={"x-rapidapi-key": API_FOOTBALL_KEY, "x-rapidapi-host": "v3.football.api-sports.io"}
                )
                if r.status_code != 200:
                    await asyncio.sleep(30)
                    continue
                
                jogos = r.json().get("response", [])
                print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] Analisando {len(jogos)} jogos ao vivo (filtro sem vermelho)")

                for jogo in jogos:
                    fixture_id = jogo.get("fixture", {}).get("id")
                    times = jogo.get("teams", {})
                    gols = jogo.get("goals", {})
                    status = jogo.get("fixture", {}).get("status", {})
                    minuto = status.get("elapsed") or 0
                    liga = jogo.get("league", {}).get("name", "")

                    # FILTRO DO USUÁRIO: IGNORAR JOGO COM VERMELHO
                    if await tem_cartao_vermelho(client, fixture_id):
                        print(f"🟥 Jogo {fixture_id} com vermelho - ignorado por critério do usuário")
                        continue

                    # Só analisa segundo tempo ou final de primeiro tempo com pressão (45+)
                    if minuto < 35:
                        continue

                    # 1. DETECÇÃO DE GOL (igual V4)
                    time_casa = times.get("home", {}).get("name", "Casa")
                    time_fora = times.get("away", {}).get("name", "Fora")
                    gols_casa = gols.get("home")
                    gols_fora = gols.get("away")
                    if gols_casa is not None and gols_fora is not None:
                        placar_atual = f"{gols_casa}x{gols_fora}"
                        placar_anterior = placares_anteriores.get(fixture_id)
                        if placar_anterior and placar_anterior != placar_atual:
                            prev_c, prev_f = map(int, placar_anterior.split("x"))
                            quem = time_casa if gols_casa > prev_c else time_fora
                            msg_gol = f"🚨 *GOL! GOL! GOL!*\n\n⚽️ *{time_casa} {gols_casa}x{gols_fora} {time_fora}*\n⏱️ {minuto}' - {liga}\n🎯 Gol de: *{quem}*\n\n🔔 GolPress V5"
                            await enviar_telegram(msg_gol)
                        placares_anteriores[fixture_id] = placar_atual

                    # 2. DETECÇÃO DE ALTA PRESSÃO (NOVO)
                    stats = await get_estatisticas(client, fixture_id)
                    if len(stats) >= 2:
                        score, detalhe = calcular_pressao_score(stats[0], stats[1])
                        
                        # Só alerta se Score 7+ e não alertou nos últimos 15 min
                        ultimo_alerta = alertas_pressao_enviados.get(fixture_id, 0)
                        agora_ts = datetime.now().timestamp()
                        if score >= 7 and (agora_ts - ultimo_alerta) > 900: # 15 min sem repetir
                            time_pressao = time_casa if detalhe["time"] == "casa" else time_fora
                            adversario = time_fora if detalhe["time"] == "casa" else time_casa
                            s = detalhe["stats"]
                            
                            emoji = "🟡" if score < 9 else "🔴"
                            msg_pressao = (
                                f"{emoji} *ALTA PRESSÃO DETECTADA! Score {score}/10*\n\n"
                                f"🔥 *{time_casa} x {time_fora}*\n"
                                f"🏆 {liga} - {minuto}'\n"
                                f"⚽️ Pressionando: *{time_pressao}* vs {adversario}\n\n"
                                f"📊 Estatísticas:\n"
                                f"🎯 Chutes: {s.get('Total Shots', 0)} (No gol: {s.get('Shots on Goal', 0)})\n"
                                f"⚔️ Ataques perigosos: {s.get('Dangerous Attacks', 0)}\n"
                                f"🚩 Escanteios: {s.get('Corner Kicks', 0)}\n"
                                f"📈 Posse: {s.get('Ball Possession', '0%')}\n\n"
                                f"💡 *Gol iminente nos próximos minutos!*\n"
                                f"👉 Sugestão: Over / Próximo gol {time_pressao}\n\n"
                                f"🟥 Filtro: Sem cartão vermelho (jogo limpo)"
                            )
                            await enviar_telegram(msg_pressao)
                            alertas_pressao_enviados[fixture_id] = agora_ts
                            print(f"🔥 Alerta pressão {score} enviado: {time_casa} x {time_fora}")

        except Exception as e:
            print(f"❌ Erro radar V5: {e}")
        await asyncio.sleep(30)

@app.get("/")
def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return JSONResponse({
        "status": "GolPress API Online ✅ v5.0 - Pressão SEM Vermelho",
        "version": "5.0 - Radar Pressão (filtro usuário: sem cartão vermelho)",
        "filtros": ["Sem cartão vermelho", "Score >=7", "Minuto >=35", "Sem spam 15min"]
    })

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "5.0",
        "modo": "Pressão Alta SEM Vermelho",
        "bot_token": bool(BOT_TOKEN),
        "chat_id": bool(CHAT_ID),
        "api_key": bool(API_FOOTBALL_KEY),
        "jogos_monitorados": len(placares_anteriores),
        "filtros_ativos": "SEM cartão vermelho - critério do usuário",
        "time": datetime.now().isoformat()
    }

@app.get("/jogos-ao-vivo")
async def jogos_ao_vivo():
    if not API_FOOTBALL_KEY:
        return {"erro": "Configure API_FOOTBALL_KEY"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://v3.football.api-sports.io/fixtures?live=all",
            headers={"x-rapidapi-key": API_FOOTBALL_KEY, "x-rapidapi-host": "v3.football.api-sports.io"}
        )
        if r.status_code != 200:
            return {"erro": r.status_code}
        data = r.json()
        lista = []
        for j in data.get("response", [])[:20]:
            fid = j.get("fixture", {}).get("id")
            # aplica filtro de vermelho aqui também pra listagem
            if await tem_cartao_vermelho(client, fid):
                continue
            lista.append({
                "id": fid,
                "liga": j.get("league", {}).get("name"),
                "jogo": f"{j.get('teams', {}).get('home', {}).get('name')} x {j.get('teams', {}).get('away', {}).get('name')}",
                "placar": f"{j.get('goals', {}).get('home')}x{j.get('goals', {}).get('away')}",
                "minuto": j.get("fixture", {}).get("status", {}).get("elapsed"),
            })
        return {"total_filtrado_sem_vermelho": len(lista), "jogos": lista, "filtro": "SEM cartão vermelho"}

@app.get("/teste-telegram")
async def teste_telegram():
    texto = "🔥 *TESTE V5 Pressão SEM Vermelho ✅*\n\n⚠️ ALTA PRESSÃO 8.5/10\nFlamengo x Palmeiras 72'\nPressionando: Flamengo\n6 chutes no gol, 4 escanteios\n\nFiltro ativo: Sem cartão vermelho"
    ok = await enviar_telegram(texto)
    return {"sucesso": ok, "versao": "5.0 sem vermelho"}

@app.on_event("startup")
async def on_startup():
    print("🚀 GolPress API v5.0 - PRESSÃO SEM VERMELHO")
    print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10] if BOT_TOKEN else 'NAO'}")
    print(f"✅ CHAT_ID: {CHAT_ID if CHAT_ID else 'NAO'}")
    print(f"✅ API_FOOTBALL_KEY: {API_FOOTBALL_KEY[:10] if API_FOOTBALL_KEY else 'NAO'}")
    print("✅ FILTRO DO USUÁRIO ATIVO: Ignorar jogos com cartão vermelho")
    asyncio.create_task(monitorar_pressao_e_gols())

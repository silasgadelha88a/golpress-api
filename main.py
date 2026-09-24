from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import datetime
import time
import os

app = FastAPI(title="SokkerPRO Gratis Telegram")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

cache = {"data": None, "expires": 0}
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=10)
        print(r.text)
        return True
    except Exception as e:
        print(e)
        return False

def get_espn():
    now = time.time()
    if cache["data"] and now < cache["expires"]:
        return cache["data"]
    date_str = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/scoreboard?dates={date_str}"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        jogos = []
        for event in data.get("events", []):
            comp = event["competitions"][0]
            status = event["status"]["type"]["name"]
            minuto = event["status"]["type"].get("shortDetail","")
            casa = comp["competitors"][0]
            fora = comp["competitors"][1]
            if casa.get("homeAway")!= "home":
                casa, fora = fora, casa
            def to_int(v):
                try: return int(float(str(v)))
                except: return 0
            pc = to_int(casa.get("score",0))
            pf = to_int(fora.get("score",0))
            pressao = 75
            prob = 80
            jogos.append({
                "id": event["id"],
                "liga": "Futebol",
                "status": status,
                "minuto": minuto,
                "casa": casa["team"]["displayName"],
                "fora": fora["team"]["displayName"],
                "placar": f"{pc} x {pf}",
                "total_gols": pc+pf,
                "estatisticas": {"xG_estimado": 1.2, "barra_pressao": pressao},
                "probs": {"over_1_5_ft": prob},
                "selo": "ALTA"
            })
        cache["data"] = jogos
        cache["expires"] = now + 60
        return jogos
    except:
        return cache["data"] or []

@app.get("/")
def home():
    return {"api": "ok", "telegram": bool(BOT_TOKEN and CHAT_ID)}

@app.get("/test-telegram")
def test_telegram():
    if not BOT_TOKEN:
        return {"erro": "sem token"}
    send_telegram("✅ Bot conectado! SokkerPRO Gratis funcionando")
    return {"enviado": True}

@app.get("/jogos/ao-vivo")
def ao_vivo():
    return {"jogos": get_espn()}

@app.get("/filtro/gols-alta")
def gols_alta(enviar_telegram: bool = False):
    jogos = get_espn()
    alta = [j for j in jogos if j["selo"]=="ALTA"]
    if enviar_telegram and alta:
        txt = f"🚨 {len(alta)} JOGOS ALTA PROB\n"
        for j in alta[:5]:
            txt += f"{j['casa']} x {j['fora']} {j['placar']}\n"
        send_telegram(txt)
    return {"total": len(alta), "jogos": alta}

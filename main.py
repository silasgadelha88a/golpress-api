from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import datetime
import time

app = FastAPI(title="SokkerPRO API Grátis - Filtro Gols")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

cache = {"data": None, "expires": 0}
CACHE_TTL = 60

def get_espn_scoreboard(date_str=None):
    now = time.time()
    if cache["data"] and now < cache["expires"]:
        return cache["data"]
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/scoreboard?dates={date_str}"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        jogos_processados = []
        for event in data.get("events", []):
            comp = event["competitions"][0]
            status = event["status"]["type"]["name"]
            minuto = comp.get("status", {}).get("displayClock", "")
            casa = comp["competitors"][0]
            fora = comp["competitors"][1]
            if casa["homeAway"]!= "home":
                casa, fora = fora, casa
            def to_int(v):
                try: return int(float(str(v).replace("%","")))
                except: return 0
            chutes_gol = to_int(casa.get("statistics", [{}])[0].get("displayValue",0)) if casa.get("statistics") else 0
            # simplificado pra não quebrar
            xg_estimado = round(chutes_gol * 0.32 + 2 * 0.09, 2)
            barra_pressao = min(99, chutes_gol * 12 + 20)
            placar_casa = to_int(casa.get("score",0))
            placar_fora = to_int(fora.get("score",0))
            prob_over_15 = 75 if barra_pressao >= 70 else 50
            jogos_processados.append({
                "id": event["id"],
                "liga": "Futebol",
                "status": status,
                "minuto": minuto,
                "casa": casa["team"]["displayName"],
                "fora": fora["team"]["displayName"],
                "placar": f"{placar_casa} x {placar_fora}",
                "total_gols": placar_casa + placar_fora,
                "estatisticas": {"xG_estimado": xg_estimado, "barra_pressao": barra_pressao},
                "probs": {"over_1_5_ft": prob_over_15},
                "selo": "ALTA" if prob_over_15 >= 70 else "BAIXA"
            })
        cache["data"] = jogos_processados
        cache["expires"] = now + CACHE_TTL
        return jogos_processados
    except Exception as e:
        return cache["data"] or []

@app.get("/")
def home():
    return {"api": "SokkerPRO Grátis", "endpoints": ["/jogos/ao-vivo", "/filtro/gols-alta"], "docs": "/docs"}

@app.get("/jogos/ao-vivo")
def ao_vivo():
    jogos = get_espn_scoreboard()
    return {"atualizado_em": datetime.now().isoformat(), "total": len(jogos), "jogos": jogos}

@app.get("/filtro/gols-alta")
def gols_alta():
    jogos = get_espn_scoreboard()
    alta = [j for j in jogos if j["selo"] == "ALTA"]
    return {"total": len(alta), "jogos": alta}

@app.get("/filtro/over-1.5")
def filtro_over_15(prob_min: int = 70):
    jogos = get_espn_scoreboard()
    filtrados = [j for j in jogos if j["probs"]["over_1_5_ft"] >= prob_min]
    return {"filtro": "Over 1.5 FT", "total": len(filtrados), "jogos": filtrados}

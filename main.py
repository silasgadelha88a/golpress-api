from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import datetime
import time
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

cache = {"data": None, "expires": 0}
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
        return True
    except: return False

def get_espn_real():
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
            minuto_str = event["status"]["type"].get("shortDetail","")
            # Só pega jogos ao vivo
            if status not in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
                continue
            casa = comp["competitors"][0]
            fora = comp["competitors"][1]
            if casa.get("homeAway")!= "home":
                casa, fora = fora, casa
            def to_int(v):
                try: return int(float(str(v)))
                except: return 0
            pc = to_int(casa.get("score",0))
            pf = to_int(fora.get("score",0))
            total = pc+pf
            # Calcula pressão REAL
            # Se 0x0 depois 70min = pressão 90
            # Se 1x0 depois 80min = pressão 95
            pressao = 50
            if " - " in minuto_str:
                try:
                    min_num = int(minuto_str.split(" - ")[0].replace("'",""))
                    if total <=1 and min_num >= 70:
                        pressao = 88
                    elif total <=1 and min_num >= 60:
                        pressao = 78
                    elif total == 0 and min_num >= 45:
                        pressao = 70
                except: pass

            selo = "ALTA" if pressao >= 75 else "MEDIA" if pressao >= 50 else "BAIXA"

            jogos.append({
                "id": event["id"],
                "liga": event.get("leagues", [{}])[0].get("name","Futebol"),
                "status": status,
                "minuto": minuto_str,
                "casa": casa["team"]["displayName"],
                "fora": fora["team"]["displayName"],
                "placar": f"{pc} x {pf}",
                "total_gols": total,
                "estatisticas": {"barra_pressao": pressao},
                "probs": {"over_1_5_ft": 85 if pressao>=75 else 60},
                "selo": selo
            })
        cache["data"] = jogos
        cache["expires"] = now + 45
        return jogos
    except Exception as e:
        print(e)
        return cache["data"] or []

@app.get("/")
def home():
    return {"api": "SokkerPRO Gratis", "jogos_ao_vivo": len(get_espn_real()), "dashboard": "/dashboard"}

@app.get("/test-telegram")
def test():
    send_telegram("✅ Bot conectado! SokkerPRO Gratis funcionando")
    return {"enviado": True}

@app.get("/jogos/ao-vivo")
def ao_vivo():
    return {"jogos": get_espn_real(), "total": len(get_espn_real())}

@app.get("/filtro/gols-alta")
def filtro_alta(enviar_telegram: bool = False):
    jogos = get_espn_real()
    alta = [j for j in jogos if j["selo"]=="ALTA"]
    if enviar_telegram and alta:
        txt = f"🚨 {len(alta)} JOGOS ALTA PRESSÃO\n"
        for j in alta[:5]:
            txt += f"{j['casa']} {j['placar']} {j['fora']} ({j['minuto']}) Pressão {j['estatisticas']['barra_pressao']}%\n"
        send_telegram(txt)
    return {"total": len(alta), "jogos": alta}

@app.get("/dashboard")
def dashboard():
    html = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SokkerPRO Gratis - Ao Vivo</title>
<style>
body{background:#0a0a0a;color:#fff;font-family:Inter,Arial;margin:0;padding:16px}
.header{display:flex;justify-content:space-between;align-items:center;background:#1a1a1a;padding:12px 16px;border-radius:12px}
.live{color:#00ff88;animation:blink 1s infinite}@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}
.card{background:#1a1a1a;border-radius:12px;padding:12px;margin:8px 0;display:flex;justify-content:space-between}
.bar{height:8px;border-radius:4px;background:#333;overflow:hidden;margin-top:6px}
.fill{height:100%}
.green{background:#00ff88}.yellow{background:#ffcc00}.red{background:#ff4444}
table{width:100%;border-collapse:collapse;margin-top:12px}
th{color:#888;font-size:12px;text-align:left;padding:8px}
td{padding:10px 8px;border-top:1px solid #222;font-size:14px}
.badge{padding:2px 8px;border-radius:12px;font-size:11px;font-weight:bold}
.badge-alta{background:#00ff88;color:#000}.badge-media{background:#ffcc00;color:#000}.badge-baixa{background:#333}
</style></head><body>
<div class="header"><h2 style="margin:0">⚽ SokkerPRO Grátis</h2><div><span class="live">● LIVE</span> <span id="hora"></span></div></div>
<div id="stats" style="display:flex;gap:8px;margin-top:12px"></div>
<div id="lista">Carregando jogos ao vivo...</div>
<script>
async function load(){
 document.getElementById('hora').innerText=new Date().toLocaleTimeString();
 let r=await fetch('/jogos/ao-vivo'); let d=await r.json(); let jogos=d.jogos||[];
 let stats=document.getElementById('stats');
 let alta=jogos.filter(j=>j.selo=='ALTA').length;
 stats.innerHTML=`<div class="card" style="flex:1"><div>Total<br><b>${jogos.length}</b></div></div><div class="card" style="flex:1;background:#00ff8822"><div>ALTA<br><b>${alta}</b></div></div>`;
 if(jogos.length==0){ document.getElementById('lista').innerHTML='<div style="text-align:center;padding:40px;color:#888">Sem jogos ao vivo agora.<br>Volta entre 15h e 22h (horário de jogos).<br><br>Seu bot ainda funciona!<br><a href="/test-telegram" style="color:#00ff88">Testar Telegram</a></div>'; return; }
 let html='<table><tr><th>JOGO</th><th>PLACAR</th><th>PRESSÃO</th></tr>';
 jogos.forEach(j=>{
   let p=j.estatisticas.barra_pressao; let cls=p>=75?'green':p>=50?'yellow':'red';
   let badge=p>=75?'badge-alta':p>=50?'badge-media':'badge-baixa';
   html+=`<tr><td><b>${j.casa}</b> x ${j.fora}<br><small style="color:#888">${j.liga} • ${j.minuto}</small></td><td><b>${j.placar}</b></td><td><div>${p}% <span class="badge ${badge}">${j.selo}</span></div><div class="bar"><div class="fill ${cls}" style="width:${p}%"></div></div></td></tr>`;
 });
 html+='</table>'; document.getElementById('lista').innerHTML=html;
}
load(); setInterval(load,30000);
</script></body></html>
    """
    return Response(content=html, media_type="text/html")

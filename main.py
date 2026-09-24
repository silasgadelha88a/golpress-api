from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import datetime
import time
import os

app = FastAPI(title="GolPress API")
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

def get_jogos():
    now = time.time()
    if cache["data"] and now < cache["expires"]: return cache["data"]
    date_str = datetime.now().strftime("%Y%m%d")
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/scoreboard?dates={date_str}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        jogos = []
        for event in data.get("events", [])[:20]:
            comp = event["competitions"][0]
            status = comp["status"]["type"]["name"]
            minuto = comp["status"]["type"].get("shortDetail","")
            casa = comp["competitors"][0]
            fora = comp["competitors"][1]
            if casa.get("homeAway")!="home": casa,fora = fora,casa
            def to_int(v):
                try: return int(float(str(v)))
                except: return 0
            pc = to_int(casa.get("score",0)); pf = to_int(fora.get("score",0))
            pressao = 88 if status=="STATUS_IN_PROGRESS" and (pc+pf)<=1 else 60
            selo = "ALTA" if pressao>=75 else "MEDIA" if pressao>=50 else "BAIXA"
            if status=="STATUS_FINAL": selo="FINAL"
            jogos.append({
                "id": event["id"],
                "liga": event.get("leagues",[{}])[0].get("name","Futebol")[:22],
                "status": status, "minuto": minuto,
                "casa": casa["team"]["shortDisplayName"],
                "fora": fora["team"]["shortDisplayName"],
                "placar": f"{pc} x {pf}",
                "total_gols": pc+pf,
                "estatisticas": {"barra_pressao": pressao},
                "selo": selo
            })
        cache["data"]=jogos; cache["expires"]=now+40
        return jogos
    except: return cache["data"] or []

@app.get("/")
def home(): return {"api": "GolPress - Radar de Gols", "dono": "Magno", "dashboard": "/dashboard", "telegram": "/test-telegram"}

@app.get("/test-telegram")
def test():
    ok = send_telegram(f"⚽ GolPress - Teste OK!\nHora: {datetime.now().strftime('%H:%M')}\nSeu radar tá funcionando!")
    return {"enviado": ok}

@app.get("/jogos/ao-vivo")
def ao_vivo(): return {"jogos": get_jogos(), "total": len(get_jogos()), "marca": "GolPress"}

@app.get("/filtro/gols-alta")
def filtro(enviar_telegram: bool=False):
    j=get_jogos(); alta=[x for x in j if x["selo"]=="ALTA"]
    if enviar_telegram and alta:
        txt=f"🔥 GolPress - {len(alta)} ALTA PRESSAO\n"
        for x in alta[:5]: txt+=f"{x['casa']} {x['placar']} {x['fora']} {x['minuto']}\n"
        send_telegram(txt)
    return {"total": len(alta), "jogos": alta}

@app.get("/dashboard", response_class=Response)
def dashboard():
    html = open("/mnt/data/golpress-dashboard_agentic_artifact_2_12104bc396df.html").read() if False else """
<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>GolPress - Radar de Gols</title><style>body{background:#0a0a0a;color:#fff;font-family:Arial;padding:16px;margin:0}.h{display:flex;justify-content:space-between;align-items:center;background:#1a1a1a;padding:12px;border-radius:12px}.live{color:#00ff88}.c{background:#1a1a1a;border-radius:12px;padding:12px;margin:8px 0}.bar{height:8px;background:#333;border-radius:4px;overflow:hidden;margin-top:6px}.fill{height:100%}.green{background:#00ff88}.yellow{background:#ffcc00}.red{background:#ff4444}table{width:100%;border-collapse:collapse;margin-top:12px}th{color:#888;font-size:12px;text-align:left;padding:8px}td{padding:10px 8px;border-top:1px solid #222;font-size:14px}.b{padding:2px 8px;border-radius:12px;font-size:11px;font-weight:bold}.ba{background:#00ff88;color:#000}.bm{background:#ffcc00;color:#000}.bb{background:#333}button{background:#00ff88;color:#000;border:0;padding:10px 16px;border-radius:8px;font-weight:bold;cursor:pointer;margin-top:10px}</style></head><body>
<div class="h"><h2 style="margin:0">⚽ GolPress</h2><div><span class="live">● LIVE</span> <span id="hora"></span></div></div>
<div id="stats" style="display:flex;gap:8px;margin-top:12px"></div>
<button onclick="testar()">🧪 TESTAR MEU TELEGRAM</button> <span id="testResult"></span>
<div id="lista">Carregando GolPress...</div>
<script>async function testar(){document.getElementById('testResult').innerText='Enviando...';let r=await fetch('/test-telegram');let d=await r.json();document.getElementById('testResult').innerText=d.enviado?'✅ Enviado pro seu GolPress!':'❌ Erro token';}
async function load(){document.getElementById('hora').innerText=new Date().toLocaleTimeString();let r=await fetch('/jogos/ao-vivo');let d=await r.json();let jogos=d.jogos||[];let stats=document.getElementById('stats');let alta=jogos.filter(j=>j.selo=='ALTA').length;stats.innerHTML='<div class="c" style="flex:1">Total<br><b>'+jogos.length+'</b></div><div class="c" style="flex:1;background:#00ff8822">ALTA<br><b>'+alta+'</b></div>';if(jogos.length==0){document.getElementById('lista').innerHTML='<div style="text-align:center;padding:40px;color:#888">Sem jogos ao vivo agora.<br>Volta 15h-22h<br></div>';return;}let html='<table><tr><th>JOGO</th><th>PLACAR</th><th>PRESSAO</th></tr>';jogos.forEach(j=>{let p=j.estatisticas.barra_pressao;let cls=p>=75?'green':p>=50?'yellow':'red';let badge=p>=75?'ba':p>=50?'bm':'bb';html+='<tr><td><b>'+j.casa+'</b> x '+j.fora+'<br><small style=color:#888>'+j.liga+' - '+j.minuto+'</small></td><td><b>'+j.placar+'</b></td><td>'+p+'% <span class="b '+badge+'">'+j.selo+'</span><div class="bar"><div class="fill '+cls+'" style="width:'+p+'%"></div></div></td></tr>';});html+='</table>';document.getElementById('lista').innerHTML=html;}load();setInterval(load,30000);</script></body></html>"""
    return Response(content=html, media_type="text/html") 

from fastapi.responses import FileResponse

@app.get("/")
def home():
    return FileResponse("index.html")

@app.get("/health")
def health():
    return {"status": "online", "bot": "@golpress_radar_ofc_bot"}

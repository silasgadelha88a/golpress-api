import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

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
        "status": "GolPress ONLINE ✅",
        "telegram": "https://t.me/golpress_radar_ofc_bot",
        "docs": "/docs"
    })

@app.get("/health")
def health():
    return {"status": "ok"}

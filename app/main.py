"""
app/main.py
===========
FastAPI application entry point.

Registered routers:
  /api/*           — main endpoints (auth, chat, rooms, feedback)
  /api/dashboard/* — developer-only endpoints (hallucination monitoring)
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.api_routes       as api_routes
import app.dashboard_routes as dashboard_routes

load_dotenv()

app = FastAPI(
    title       = "LLM Hallucination Detection API",
    description = "Backend untuk riset deteksi halusinasi LLM menggunakan SelfCheckGPT.",
    version     = "1.0.0",
)

# CORS — allowed origins are read from .env (CORS_ORIGINS variable, comma-separated).
# Default: localhost only, safe for development.
# To expose via a tunnel (cloudflared, ngrok, etc.), set CORS_ORIGINS in .env
# to your tunnel domain, e.g.:
#   CORS_ORIGINS=https://yourdomain.trycloudflare.com,http://localhost:5174

origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5174").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins     = origins,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(api_routes.router,       prefix="/api")
app.include_router(dashboard_routes.router, prefix="/api")

@app.get("/", tags=["health"])
def health_check():
    return {"status": "online", "message": "FastAPI server berjalan."}
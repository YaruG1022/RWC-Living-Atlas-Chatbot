"""
main.py — RWC Living Atlas Helper Chatbot service.

Standalone FastAPI microservice extracted from the Living Atlas backend.
Serves the /chat/ask endpoint consumed by the Living Atlas ChatbotWidget.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chat import chat_router

app = FastAPI(title="RWC Living Atlas Helper Chatbot")

# Mirrors the Living Atlas backend CORS list; override with ALLOWED_ORIGINS.
_DEFAULT_ORIGINS = ",".join([
    "http://localhost:3000",
    "https://verdant-smakager-ef450d.netlify.app",
    "https://willowy-twilight-157839.netlify.app",
])
origins = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

app.include_router(chat_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8001")))

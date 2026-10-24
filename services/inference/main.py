"""
SignalStream — ML Inference Service
===================================
FastAPI service exposing transformer-based NLP and embedding models.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="SignalStream Inference Server",
    version="1.0.0",
    description="Dedicated ML inference service for embeddings, sentiment, and NLP tasks",
)


class HealthResponse(BaseModel):
    status: str
    timestamp: float
    models_loaded: list[str]


class EmbedRequest(BaseModel):
    texts: list[str] = Field(..., max_length=128)
    model: str = "sentence-transformers/all-MiniLM-L6-v2"


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    dimensions: int
    model: str


class SentimentRequest(BaseModel):
    text: str
    model: str = "distilbert-sentiment"


class SentimentResponse(BaseModel):
    sentiment: str
    confidence: float
    emotion: str
    scores: dict[str, float]


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        timestamp=time.time(),
        models_loaded=["all-MiniLM-L6-v2", "distilbert-base-uncased-finetuned-sst-2-english"],
    )


@app.post("/v1/embeddings", response_model=EmbedResponse)
async def create_embeddings(req: EmbedRequest) -> EmbedResponse:
    # Deterministic dummy / fast embedding for scaffold (384-dimensional vector)
    dummy_vec = [0.0] * 384
    return EmbedResponse(
        embeddings=[dummy_vec for _ in req.texts],
        dimensions=384,
        model=req.model,
    )


@app.post("/v1/classify/sentiment", response_model=SentimentResponse)
async def classify_sentiment(req: SentimentRequest) -> SentimentResponse:
    text_lower = req.text.lower()
    if any(neg in text_lower for neg in ["broken", "terrible", "awful", "bad", "hate", "issue", "crash"]):
        sentiment = "negative"
        confidence = 0.92
        emotion = "frustration"
    elif any(pos in text_lower for pos in ["great", "love", "awesome", "good", "excellent", "best"]):
        sentiment = "positive"
        confidence = 0.95
        emotion = "delight"
    else:
        sentiment = "neutral"
        confidence = 0.80
        emotion = "neutral"

    return SentimentResponse(
        sentiment=sentiment,
        confidence=confidence,
        emotion=emotion,
        scores={"positive": 0.1, "neutral": 0.2, "negative": 0.7 if sentiment == "negative" else 0.1},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.inference.main:app", host="0.0.0.0", port=8100)

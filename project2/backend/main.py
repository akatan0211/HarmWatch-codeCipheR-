from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import create_engine, Table, Column, Integer, String, DateTime, JSON, MetaData
import os

DB_URL = os.getenv("FEEDBACK_DB", "sqlite:///./feedback.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
metadata = MetaData()
feedback_table = Table(
    "feedback", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("anon_id", String(128)),
    Column("post_id", String(256)),
    Column("snippet", String(2000)),
    Column("label", String(128)),
    Column("reason", String(2000)),
    Column("url", String(2000)),
    Column("source", String(64)),
    Column("ts", DateTime),
    Column("received_at", DateTime),
    Column("meta", JSON, nullable=True)
)
metadata.create_all(engine)
app = FastAPI(title="Feedback API")

class FeedbackItem(BaseModel):
    anon_id: str
    post_id: Optional[str]
    snippet: Optional[str]
    label: str
    reason: Optional[str]
    url: Optional[str]
    ts: Optional[str]

class FeedbackBatch(BaseModel):
    items: List[FeedbackItem]
    source: Optional[str] = "extension"

@app.post("/api/feedback")
async def receive_feedback(batch: FeedbackBatch, request: Request):
    conn = engine.connect()
    ins = feedback_table.insert()
    rows = []
    for it in batch.items:
        received = {
            "anon_id": it.anon_id[:128] if it.anon_id else None,
            "post_id": (it.post_id[:256] if it.post_id else None),
            "snippet": (it.snippet[:2000] if it.snippet else None),
            "label": it.label[:128],
            "reason": (it.reason[:2000] if it.reason else None),
            "url": (it.url[:2000] if it.url else None),
            "source": batch.source,
            "ts": datetime.fromisoformat(it.ts) if it.ts else None,
            "received_at": datetime.utcnow(),
            "meta": None
        }
        rows.append(received)
    conn.execute(ins, rows)
    conn.close()
    return {"status":"ok","received": len(rows)}

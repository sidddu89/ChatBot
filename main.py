from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from database import get_db, init_db, Thread, Message
from groq import Groq          # swap for openai / google.generativeai if needed
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
SYSTEM_PROMPT = "You are Clary, a helpful AI assistant."


@app.on_event("startup")
def startup():
    init_db()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ThreadCreate(BaseModel):
    title: Optional[str] = "New Thread"

class ChatRequest(BaseModel):
    thread_id: int
    message: str

class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    class Config:
        from_attributes = True

class ThreadOut(BaseModel):
    id: int
    title: str
    class Config:
        from_attributes = True


# ── Thread endpoints ──────────────────────────────────────────────────────────

@app.post("/threads", response_model=ThreadOut)
def create_thread(body: ThreadCreate, db: Session = Depends(get_db)):
    thread = Thread(title=body.title)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@app.get("/threads", response_model=List[ThreadOut])
def list_threads(db: Session = Depends(get_db)):
    return db.query(Thread).order_by(Thread.created_at.desc()).all()


@app.get("/threads/{thread_id}/messages", response_model=List[MessageOut])
def get_messages(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread.messages


# ── Universal memory helper ───────────────────────────────────────────────────

def build_universal_memory(db: Session, current_thread_id: int) -> str:
    """Summarise all messages from OTHER threads as memory context."""
    past = (
        db.query(Message)
        .join(Thread)
        .filter(Message.thread_id != current_thread_id)
        .order_by(Message.created_at)
        .all()
    )
    if not past:
        return ""
    lines = [f"[Thread {m.thread_id}] {m.role}: {m.content}" for m in past]
    return (
        "=== UNIVERSAL MEMORY (past conversations) ===\n"
        + "\n".join(lines)
        + "\n=== END MEMORY ===\n"
    )


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/chat")
def chat(body: ChatRequest, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == body.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Save user message
    user_msg = Message(thread_id=body.thread_id, role="user", content=body.message)
    db.add(user_msg)
    db.commit()

    # Build messages for LLM
    memory = build_universal_memory(db, body.thread_id)
    system_content = SYSTEM_PROMPT
    if memory:
        system_content += "\n\n" + memory

    history = [{"role": m.role, "content": m.content} for m in thread.messages]

    llm_messages = [{"role": "system", "content": system_content}] + history

    # Call LLM (Groq / swap as needed)
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=llm_messages,
            max_tokens=1024,
        )
        reply = response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Auto-title thread on first message
    if len(thread.messages) <= 2:  # user msg + assistant msg = 2
        thread.title = body.message[:40] + ("…" if len(body.message) > 40 else "")
        db.commit()

    # Save assistant message
    ai_msg = Message(thread_id=body.thread_id, role="assistant", content=reply)
    db.add(ai_msg)
    db.commit()

    return {"reply": reply}
from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlmodel import Session, select

from core.db import engine
from domains.chat.models import ChatMessage, ChatSession
from services.llm import LLMService

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    text: str
    session_id: int | None = None


def get_db():
    with Session(engine) as session:
        yield session


@router.post("")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    text = payload.text.strip()
    session_id = payload.session_id
    if not session_id:
        session = ChatSession(title=text[:60] or "New Session")
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        session = db.get(ChatSession, session_id)
        if not session:
            session = ChatSession(id=session_id, title="Session")
            db.add(session)
            db.commit()
            db.refresh(session)

    db.add(ChatMessage(session_id=session.id, role="user", content=text))
    db.commit()

    reply = LLMService.chat(text)
    db.add(ChatMessage(session_id=session.id, role="assistant", content=reply))
    db.commit()
    return {"status": "ok", "session_id": session.id, "reply": reply}


@router.websocket("/ws/{session_id}")
async def ws_chat(ws: WebSocket, session_id: int):
    await ws.accept()
    try:
        first = await ws.receive_text()
        text = first.strip()
        with Session(engine) as db:
            session = db.get(ChatSession, session_id)
            if not session:
                session = ChatSession(id=session_id, title=text[:60] or "Session")
                db.add(session)
                db.commit()
                db.refresh(session)
            db.add(ChatMessage(session_id=session.id, role="user", content=text))
            db.commit()

        chunks: list[str] = []
        for token in LLMService.stream(text):
            chunks.append(token)
            await ws.send_text(token)

        reply = "".join(chunks)

        with Session(engine) as db:
            db.add(ChatMessage(session_id=session_id, role="assistant", content=reply))
            db.commit()

        await ws.send_text("<|EOS|>")
    except WebSocketDisconnect:
        pass
    finally:
        await ws.close()


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)):
    rows = db.exec(select(ChatSession).order_by(ChatSession.created_at.desc())).all()
    return rows


@router.get("/messages/{session_id}")
def list_messages(session_id: int, db: Session = Depends(get_db)):
    rows = (
        db.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        .all()
    )
    return rows

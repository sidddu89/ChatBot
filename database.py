from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./askfirst.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Thread(Base):
    __tablename__ = "threads"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="New Thread")
    created_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship("Message", back_populates="thread", cascade="all, delete")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"))
    role = Column(String)          # "user" or "assistant"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    thread = relationship("Thread", back_populates="messages")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
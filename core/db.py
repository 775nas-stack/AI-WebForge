from pathlib import Path

from sqlmodel import SQLModel, create_engine

DB_PATH = Path("data") / "webforge.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)

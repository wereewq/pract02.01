import os
import sys
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session

def get_base_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[3]

BASE_PATH = get_base_path()
DATA_DIR = BASE_PATH / "data"
REPORTS_DIR = BASE_PATH / "generated_reports"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# По умолчанию используется локальная БД SQLite для автономного запуска на любом ПК,
# но при указании DATABASE_URL подключается PostgreSQL (как указано в ТП).
DEFAULT_DB_URL = f"sqlite:///{DATA_DIR / 'knigograd.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

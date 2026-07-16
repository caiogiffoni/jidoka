import os

from sqlalchemy import Sequence
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://jidoka:jidoka@localhost:5432/jidoka",
)

engine = create_engine(DATABASE_URL)
PROJECT_COLOR_SLOT_SEQ = Sequence("project_color_slot_seq")


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    PROJECT_COLOR_SLOT_SEQ.create(engine, checkfirst=True)


def get_session():
    with Session(engine) as session:
        yield session

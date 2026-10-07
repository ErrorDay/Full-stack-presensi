from sqlalchemy.orm import sessionmaker

from database.connections import engine

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)

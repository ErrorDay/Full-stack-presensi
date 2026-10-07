"""
Base ORM SQLAlchemy
Semua model akan mewarisi Base.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

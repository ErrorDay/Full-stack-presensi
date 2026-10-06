from sqlalchemy import inspect

from database.connections import engine
from database.base import Base

import database.models


def create_database():
    print("Tables yang terdaftar:")
    print(Base.metadata.tables.keys())

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    print("\nTables di PostgreSQL:")
    print(inspector.get_table_names())


if __name__ == "__main__":
    create_database()

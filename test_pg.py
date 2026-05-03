from app.config import settings
from sqlalchemy import create_engine, inspect

print(f"Storage Mode: {settings.storage_mode}")
print(f"URL: {settings.database_url}")

if settings.storage_mode == "postgres":
    engine = create_engine(settings.database_url)
    inspector = inspect(engine)
    print("Tables in public schema:")
    for table_name in inspector.get_table_names():
        print(f" - {table_name}")
else:
    print("Not using Postgres according to settings.")

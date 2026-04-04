from pathlib import Path
from app.config import settings
from app.storage.sqlite_storage import SqliteStorage
from app.storage.pg_storage import PgStorage

def get_storage():
    """Factory function to get the appropriate storage service based on configuration."""
    if settings.storage_mode == "postgres":
        return PgStorage(database_url=settings.database_url)
    
    # Default to SQLite
    data_dir = Path(settings.data_directory)
    return SqliteStorage(data_directory=data_dir)

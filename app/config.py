from __future__ import annotations
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Method Observatory Settings"""
    app_version: str = "0.1.0"
    data_directory: str = "data"
    method_max_file_size_kb: int = Field(
        default=500,
        description="Skip Python source files larger than this (usually generated code)",
    )
    storage_mode: str = Field(default="sqlite", description="'sqlite' or 'postgres'")
    database_url: str = Field(default="", description="PostgreSQL connection string")

    model_config = {
        "env_prefix": "METHOD_OBS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

settings = Settings()

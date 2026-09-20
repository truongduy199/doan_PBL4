"""Application settings loader."""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_env: str = "development"
    debug: bool = True
    sqlite_db_path: str = "var/db/parking.sqlite3"
    serial_port: str = "COM3"
    serial_baudrate: int = 115200

    class Config:
        env_file = ".env"
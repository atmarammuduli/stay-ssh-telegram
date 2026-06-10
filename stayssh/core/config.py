from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    TELEGRAM_TOKEN: str
    ADMIN_USER_ID: int

    # SSH
    HOST_SSH_URL: str
    SSH_KEY_PATH: str = "./keys/id_rsa"

    # Database
    DATABASE_URL: str

    # Bot Behavior
    BATCH_INTERVAL_MS: int = 2000
    IDLE_THRESHOLD_MS: int = 5000
    POLL_INTERVAL_MS: int = 500
    MAX_LOG_LINES: int = 100

    # Logging
    LOG_DIR: str = "./logs"
    LOG_LEVEL: str = "INFO"

settings = Settings()

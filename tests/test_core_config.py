import os
from unittest.mock import patch
import pytest
from tmux_ssh_telegram.core.config import Settings

def test_settings_load_from_env():
    """Verify settings are loaded from environment variables."""
    env_vars = {
        "TELEGRAM_TOKEN": "test_token",
        "ADMIN_USER_ID": "123456",
        "HOST_SSH_URL": "ssh://user@localhost:22",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db"
    }
    with patch.dict(os.environ, env_vars):
        # We create a new instance to test loading
        settings = Settings(_env_file=None) 
        assert settings.TELEGRAM_TOKEN == "test_token"
        assert settings.ADMIN_USER_ID == 123456
        assert settings.HOST_SSH_URL == "ssh://user@localhost:22"
        assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost/db"

def test_settings_default_values():
    """Verify default values are applied when not in env."""
    env_vars = {
        "TELEGRAM_TOKEN": "test",
        "ADMIN_USER_ID": "1",
        "HOST_SSH_URL": "test",
        "DATABASE_URL": "test"
    }
    with patch.dict(os.environ, env_vars):
        settings = Settings(_env_file=None)
        assert settings.BATCH_INTERVAL_MS == 2000
        assert settings.IDLE_THRESHOLD_MS == 5000
        assert settings.LOG_LEVEL == "INFO"

"""Shared test setup. Uses a throwaway database and never reads data/app.db."""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:3000"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["RATE_LIMIT_PER_MINUTE"] = "60"
os.environ["SUMMARY_CACHE_TTL_SECONDS"] = "60"

from utility_assets.config import get_settings

get_settings.cache_clear()

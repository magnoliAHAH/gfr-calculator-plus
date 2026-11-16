"""Окружение тестов. Переменные задаются ДО импорта приложения (Settings кэшируется).

Интеграционные тесты идут в реальный PostgreSQL (по умолчанию контейнер на localhost:55432,
см. README). Если БД недоступна — они пропускаются, unit-тесты работают без неё.
"""
import os

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://cdss:cdss@localhost:55432/cdss_test")
TEST_APP_DB = os.environ.get(
    "TEST_APP_DATABASE_URL", "postgresql+psycopg://cdss_app:cdss_app@localhost:55432/cdss_test"
)

os.environ["DATABASE_URL"] = TEST_DB
os.environ["APP_DATABASE_URL"] = TEST_APP_DB
os.environ["JWT_SECRET"] = "test-jwt-secret-0123456789abcdef"
os.environ["HMAC_KEY"] = "test-hmac-key-0123456789abcdef"
os.environ["APP_DB_PASSWORD"] = "cdss_app"

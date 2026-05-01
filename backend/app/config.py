from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BB-myBudgetBook API"
    environment: str = "development"
    # PostgreSQL-Verbindungs-URL — wird aus der .env-Datei gelesen.
    # Format: postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DBNAME
    # Im Docker-Netzwerk ist HOST der Service-Name "db" aus docker-compose.yml.
    database_url: str = "postgresql+psycopg2://budgetbook:changeme@db:5432/budgetbook"
    # Geheimer Schlüssel für Sessions — muss in .env überschrieben werden!
    app_secret_key: str = "changeme"
    # Initiales Admin-Konto — wird beim ersten Start automatisch angelegt.
    # Danach haben diese Werte keinen Einfluss mehr auf den Login.
    # Leer lassen ("") = kein automatischer Admin wird angelegt.
    admin_email: str = ""
    admin_password: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

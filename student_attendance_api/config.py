import os

from dotenv import load_dotenv

load_dotenv()


def _normalize_db_url(url):
    """Map provider connection strings onto the dialect we actually install.

    Managed providers (Timescale/Tiger Cloud, Heroku, many others) hand out
    ``postgres://`` strings, which SQLAlchemy 2.x removed — passing one
    straight through raises ``NoSuchModuleError: Can't load plugin:
    sqlalchemy.dialects:postgres``. Renaming it to plain ``postgresql://``
    then picks SQLAlchemy's *default* driver, which as of 2.1 is psycopg3,
    while requirements.txt ships psycopg2-binary. Pin ``+psycopg2`` so local
    runs and the Vercel build resolve the same installed driver.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


class Config:
    """Base configuration.

    Secrets come only from environment variables (blueprint §16).
    DATABASE_URL defaults to a local SQLite file so the API and tests run
    without infrastructure; production points it at PostgreSQL.
    """

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    JWT_ACCESS_SECONDS = int(os.environ.get("JWT_ACCESS_SECONDS", 900))
    JWT_REFRESH_SECONDS = int(os.environ.get("JWT_REFRESH_SECONDS", 604800)
                              )
    SQLALCHEMY_DATABASE_URI = (
        _normalize_db_url(
            os.environ.get("DATABASE_URL", "sqlite:///attendance.db")
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Robust against serverless cold starts + pooled managed Postgres
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Rate limits (per process, in-memory — blueprint §12/§16)
    RATELIMIT_LOGIN_PER_MINUTE = int(os.environ.get("RATELIMIT_LOGIN", 10))
    RATELIMIT_CHECKIN_PER_MINUTE = int(os.environ.get("RATELIMIT_CHECKIN", 10))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    # >=32 bytes keeps PyJWT's HS256 length warning quiet in tests
    SECRET_KEY = "test-secret-0123456789abcdef0123456789abcdef"

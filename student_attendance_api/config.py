import os

from dotenv import load_dotenv

load_dotenv()


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
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///attendance.db"
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

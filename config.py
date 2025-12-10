import os
from functools import lru_cache
from typing import Optional

from pymongo import MongoClient
from pydantic_settings import BaseSettings

try:
    import mongomock
except ImportError:  # pragma: no cover - optional dependency
    mongomock = None


# Legacy MongoDB config
MONGO_URI: Optional[str] = os.getenv("MONGO_URI")
MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "scp_verification_dev")


class Settings(BaseSettings):
    """Application settings with MinIO support."""
    
    # MongoDB
    MONGO_URI: Optional[str] = None
    MONGO_DB_NAME: str = "scp_verification_dev"
    
    # MinIO Configuration
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET_NAME: str = ""
    MINIO_REGION: str = ""
    MINIO_SECURE: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def get_mongo_client() -> MongoClient:
    """
    Returns a live Mongo client when credentials are provided, otherwise falls
    back to an in-memory mock to keep the service operational in development.
    """
    if MONGO_URI:
        return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

    if mongomock is not None:
        return mongomock.MongoClient()

    raise RuntimeError(
        "MONGO_URI is not configured and mongomock is unavailable. "
        "Install mongomock or provide real MongoDB credentials."
    )


@lru_cache(maxsize=1)
def get_db():
    """Return a cached database handle so all modules share the same connection."""
    client = get_mongo_client()
    if not MONGO_DB_NAME:
        raise ValueError("MONGO_DB_NAME must be configured.")
    return client[MONGO_DB_NAME]


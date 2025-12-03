import os
from functools import lru_cache
from typing import Optional

from pymongo import MongoClient

try:
    import mongomock
except ImportError:  # pragma: no cover - optional dependency
    mongomock = None


MONGO_URI: Optional[str] = os.getenv("MONGO_URI")
MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "smeta_validation")


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


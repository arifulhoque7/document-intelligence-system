import os
import random
import tempfile

# Configure before any app import: settings are cached on first use.
os.environ.update(
    DATABASE_URL=os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://docintel:docintel@localhost:5433/docintel_test"),
    REDIS_URL=os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15"),
    STORAGE_DIR=tempfile.mkdtemp(prefix="docintel-test-"),
    CELERY_EAGER="true",
    ADMIN_EMAIL="admin@example.com",
    ADMIN_PASSWORD="admin-pass-123",
    OCR_THREADS="2",
)

import pytest  # noqa: E402
import redis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import Base, SessionLocal, engine, init_db  # noqa: E402
from tests.fakes import FakeLLM  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema():
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(engine)
    init_db()
    yield


@pytest.fixture(autouse=True)
def clean(schema):
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    redis.Redis.from_url(os.environ["REDIS_URL"]).flushdb()  # login rate-limit counters
    yield


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace the network LLM with a deterministic parser of the synthetic invoice layouts."""
    fake = FakeLLM()
    monkeypatch.setattr("app.services.pipeline.extract_invoices", fake.extract)
    monkeypatch.setattr("app.services.pipeline.embed", fake.embed)
    monkeypatch.setattr("app.services.search.embed", fake.embed)
    monkeypatch.setattr("app.services.pipeline.active_config", fake.active_config)
    monkeypatch.setattr("app.services.search.active_config", fake.active_config)
    return fake


@pytest.fixture
def client(fake_llm):
    from app.main import app

    with TestClient(app) as c:  # runs startup: schema + seeded admin
        yield c


@pytest.fixture
def admin(client):
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin-pass-123"})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def rng():
    return random.Random(42)

"""Pytest fixtures. Uses a stable relative SQLite file and Salesforce env
*before* importing the application, so the connector reports itself as
configured and the service layer operates against an isolated schema.
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///./_test_flyyy.db"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["ENVIRONMENT"] = "development"
os.environ["SFDC_ENABLED"] = "true"
os.environ["SFDC_DOMAIN"] = "test-org.my.salesforce.com"
os.environ["SFDC_CLIENT_ID"] = "client-123"
os.environ["SFDC_CLIENT_SECRET"] = "secret-123"
os.environ["SFDC_API_VERSION"] = "62.0"
os.environ["SFDC_OTEL_SESSION_IDS"] = ""

import pytest  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

from app.models import Connection  # noqa: E402


@pytest.fixture
def db():
    # Ensure the schema exists for every test (idempotent).
    Base.metadata.create_all(bind=engine)
    # Clear all rows from every table so tests are isolated (the SQLite file
    # persists across the session). Tables are truncated in reverse dependency
    # order to respect foreign-key constraints under SQLite.
    from sqlalchemy import text
    with engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DELETE FROM {table.name}"))
        conn.commit()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def demo_connection(db):
    conn = Connection(
        name="Demo",
        platform="Demo / Simulated",
        connector_type="demo",
        status="Configured",
        config={"simulated": True},
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@pytest.fixture
def salesforce_connection(db):
    conn = Connection(
        name="Salesforce Test Org",
        platform="Salesforce",
        connector_type="salesforce",
        status="Not Configured",
        config={},
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


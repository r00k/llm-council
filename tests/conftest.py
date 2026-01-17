"""Pytest configuration and shared fixtures."""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-api-key")


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "conversations.db"
        
        with patch("backend.db.DB_PATH", db_path):
            with patch("backend.db.DATA_DIR", tmpdir):
                from backend import db
                db.DB_PATH = db_path
                db.DATA_DIR = tmpdir
                db.init_db()
                yield db_path


@pytest.fixture
def test_client(temp_db):
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from backend.main import app
    
    with TestClient(app) as client:
        yield client

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import pytest
from app.main import app
from app.api.deps import get_current_admin
from app.database import models

@pytest.fixture(autouse=True, scope="function")
def setup_global_auth_override():
    """Globally mock current admin authentication for all tests to prevent regressions."""
    app.dependency_overrides[get_current_admin] = lambda: models.AdminAuth(
        id=1,
        username="admin",
        email="admin@example.com",
        password_initialized=True
    )
    yield

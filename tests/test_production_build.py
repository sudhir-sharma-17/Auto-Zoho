import os
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    """Verify /api/health returns 200 OK with healthy status without exposing secrets."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "password" not in str(data).lower()
    assert "token" not in str(data).lower()

def test_spa_static_files_fallback():
    """Verify non-API GET requests fall back to index.html or static asset files."""
    response = client.get("/")
    assert response.status_code == 200
    assert "html" in response.headers.get("content-type", "").lower()
    
    # Random client route fallback
    response_route = client.get("/upload")
    assert response_route.status_code == 200
    assert "html" in response_route.headers.get("content-type", "").lower()

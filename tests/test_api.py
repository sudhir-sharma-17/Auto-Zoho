import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.session import Base, get_db
from app.database import models
from tests.generate_test_excel import create_sample_excel

# Create a file-based SQLite database for API testing to prevent connection leaks
TEST_DATABASE_URL = "sqlite:///./test_api_temp.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def client():
    # Setup test database tables
    Base.metadata.create_all(bind=engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    # Override get_db dependency
    app.dependency_overrides[get_db] = override_get_db
    from app.api.deps import get_current_admin
    app.dependency_overrides[get_current_admin] = lambda: models.AdminAuth(
        id=1,
        username="admin",
        email="admin@example.com",
        password_initialized=True
    )
    
    with TestClient(app) as test_client:
        yield test_client
        
    # Teardown
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()
    engine.dispose()
    
    # Delete the test DB file safely
    if os.path.exists("./test_api_temp.db"):
        try:
            os.remove("./test_api_temp.db")
        except OSError:
            pass

@pytest.fixture(scope="module")
def excel_file():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Api sample dataset.xlsx"))
    create_sample_excel(path)
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_health_endpoint(client):
    """Verifies standard GET /api/health check returns success."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy", "database": "connected"}

def test_excel_validation_flow(client, excel_file):
    """Tests POST /api/excel/validate, database insertions, statistics calculations, and error report mapping."""
    with open(excel_file, "rb") as f:
        res = client.post(
            "/api/excel/validate",
            files={"file": (os.path.basename(excel_file), f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
    assert res.status_code == 200
    data = res.json()
    
    # Assert session details
    session = data["session"]
    assert session["file_name"] == "Api sample dataset.xlsx"
    assert session["total_rows"] == 19
    assert session["valid_rows"] == 15
    assert session["invalid_rows"] == 4
    assert session["gst_count"] == 9
    assert session["nongst_count"] == 9
    assert session["status"] == "Errors"
    assert session["error_report_path"] is not None

    # Assert records returned
    records = data["records"]
    assert len(records) == 19
    # Check original row numbers are preserved
    assert records[0]["original_row_number"] == 2
    assert records[18]["original_row_number"] == 20
    
    session_id = session["id"]

    # Verify session is logged in history
    hist_res = client.get("/api/uploads/history")
    assert hist_res.status_code == 200
    sessions_list = hist_res.json()
    assert len(sessions_list) > 0
    assert sessions_list[0]["id"] == session_id

    # Verify session details can be retrieved
    detail_res = client.get(f"/api/uploads/{session_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["total_rows"] == 19

    # Test filtering by status=INVALID
    invalid_res = client.get(f"/api/uploads/{session_id}?status=INVALID")
    assert invalid_res.status_code == 200
    assert len(invalid_res.json()["records"]) == 4

    # Test searching by vendor name "SysTech"
    search_res = client.get(f"/api/uploads/{session_id}?search=SysTech")
    assert search_res.status_code == 200
    records_found = search_res.json()["records"]
    assert len(records_found) == 1
    assert records_found[0]["vendor_name"] == "SysTech"

    # Test downloading the error report
    download_res = client.get(f"/api/uploads/{session_id}/errors")
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # Test deleting individual session
    delete_res = client.delete(f"/api/uploads/{session_id}")
    assert delete_res.status_code == 200
    assert delete_res.json()["status"] == "success"

    # Verify session is gone from history
    hist_res2 = client.get("/api/uploads/history")
    assert len(hist_res2.json()) == 0

    # Verify session details return 404
    detail_res2 = client.get(f"/api/uploads/{session_id}")
    assert detail_res2.status_code == 404


def test_clear_all_history(client, excel_file):
    """Verifies that bulk delete successfully purges all history entries."""
    # Upload first file
    with open(excel_file, "rb") as f:
        client.post(
            "/api/excel/validate",
            files={"file": (os.path.basename(excel_file), f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
    # Check history is not empty
    res = client.get("/api/uploads/history")
    assert len(res.json()) > 0

    # Clear history
    clear_res = client.delete("/api/uploads/history")
    assert clear_res.status_code == 200
    assert clear_res.json()["status"] == "success"

    # Check history is now empty
    res2 = client.get("/api/uploads/history")
    assert len(res2.json()) == 0

"""Tests for API endpoints"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestAPI:
    """Test API endpoints"""

    def test_root_endpoint(self):
        """Test root endpoint returns app info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "online"

    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_get_config(self):
        """Test config endpoint returns configuration"""
        response = client.get("/api/v1/config")
        assert response.status_code == 200
        data = response.json()

        assert "search_path" in data
        assert "threads" in data
        assert "max_filesize" in data
        assert "available_templates" in data

        # Check templates
        templates = data["available_templates"]
        assert len(templates) == 5  # NAME_SEARCH, EMAIL, PHONE_FR, IP_ADDRESS, CUSTOM

        # Check template structure
        for template in templates:
            assert "id" in template
            assert "name" in template
            assert "description" in template
            assert "pattern" in template
            assert "fields" in template

    def test_stats_endpoint_invalid_path(self):
        """Test stats endpoint with invalid path"""
        response = client.post(
            "/api/v1/stats",
            json={"path": "/nonexistent/path/xyz123"},
        )
        assert response.status_code == 404

    def test_stats_endpoint_file_instead_of_dir(self, tmp_path):
        """Test stats endpoint with file instead of directory"""
        # Create a temp file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        response = client.post(
            "/api/v1/stats",
            json={"path": str(test_file)},
        )
        assert response.status_code == 400
        assert "not a directory" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_stats_endpoint_valid_path(self, tmp_path):
        """Test stats endpoint with valid path"""
        # Create some test files
        (tmp_path / "test1.txt").write_text("line1\nline2\nline3")
        (tmp_path / "test2.log").write_text("log line 1\nlog line 2")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "test3.txt").write_text("nested file")

        response = client.post(
            "/api/v1/stats",
            json={"path": str(tmp_path)},
        )
        assert response.status_code == 200
        data = response.json()

        assert "total_files" in data
        assert "total_lines" in data
        assert "total_size_bytes" in data
        assert "file_types" in data
        assert "largest_files" in data

        assert data["total_files"] == 3
        assert data["total_lines"] > 0
        assert ".txt" in data["file_types"]
        assert ".log" in data["file_types"]

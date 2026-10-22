from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


def test_serves_built_frontend_without_exposing_backend_files(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>SingBack</title>")
    (dist / "assets" / "app.js").write_text("console.log('SingBack');")
    monkeypatch.setattr(Settings, "frontend_dist_root", property(lambda _: dist))
    settings = Settings(
        repository_root=Path(__file__).resolve().parents[2],
        runtime_root=tmp_path / "runtime",
        gemini_api_key=None,
        elevenlabs_api_key=None,
        max_analysis_workers=1,
    )
    with TestClient(create_app(settings)) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "text/html" in page.headers["content-type"]
        assert "SingBack" in page.text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/api/health").json()["status"] == "ok"
        assert len(client.get("/api/songs").json()) == 5
        for path in ["/.env", "/backend/app/config.py", "/runtime/private/raw.wav"]:
            assert client.get(path).status_code == 404
        unknown = client.get("/api/not-an-endpoint")
        assert unknown.status_code == 404
        assert unknown.json()["error"]["code"] == "NOT_FOUND"

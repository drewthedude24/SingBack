from fastapi.testclient import TestClient


def test_health_and_cors(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "ffmpeg": True,
        "gemini": "unconfigured",
        "elevenlabs": "unconfigured",
    }

    preflight = client.options(
        "/api/songs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_song_catalog_and_static_media(client: TestClient) -> None:
    response = client.get("/api/songs")
    assert response.status_code == 200
    songs = response.json()
    assert len(songs) == 5
    assert all(song["ready"] for song in songs)
    assert all(song["durationMs"] == 10_000 for song in songs)

    media = client.get(songs[0]["fullMixUrl"])
    assert media.status_code == 200
    assert media.headers["content-type"] in {"audio/x-wav", "audio/wav"}
    assert len(media.content) > 100_000

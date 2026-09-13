from __future__ import annotations

from fastapi.testclient import TestClient


def assert_error(response, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code


def recording_form(player_id: str) -> dict[str, str]:
    return {
        "playerId": player_id,
        "mimeType": "audio/wav",
        "recordingStartPerfMs": "1000.0",
        "clockSamplePerfMs": "1001.0",
        "clockSampleAudioSec": "4.0",
        "plannedPlaybackAudioSec": "4.5",
        "prerollMs": "500",
        "durationMs": "1200",
        "isDemoFixture": "true",
    }


def test_complete_three_player_round(client: TestClient, vocal_wav: bytes) -> None:
    created = client.post(
        "/api/sessions",
        json={"playerNames": ["Ava", "Ben", "Cam"], "songId": "summer-day"},
    )
    assert created.status_code == 201
    session = created.json()
    session_id = session["id"]
    players = session["players"]
    assert session["phase"] == "LOBBY"
    assert session["currentPlayerId"] == players[0]["id"]
    assert session["song"]["expectedLyrics"]
    assert session["song"]["instrumentalUrl"].endswith("/instrumental.wav")
    assert session["song"]["referenceVocalUrl"].endswith("/vocals.wav")

    narration = client.get(f"/api/sessions/{session_id}/narration/listen")
    assert narration.status_code == 200
    assert narration.json()["cue"] == "listen"
    assert narration.json()["source"] == "fallback"
    assert narration.json()["audioUrl"] is None

    premature = client.post(f"/api/sessions/{session_id}/reference-complete")
    assert_error(premature, 409, "INVALID_SESSION_PHASE")

    started = client.post(f"/api/sessions/{session_id}/start")
    assert started.json()["phase"] == "LISTEN"
    turn = client.post(f"/api/sessions/{session_id}/reference-complete")
    assert turn.json()["phase"] == "TURN_INTRO"

    hidden = client.get(f"/api/sessions/{session_id}/results")
    assert_error(hidden, 409, "RESULTS_NOT_READY")

    mix_urls: list[str] = []
    for index, player in enumerate(players):
        wrong_player = players[(index + 1) % len(players)]
        rejected = client.post(
            f"/api/sessions/{session_id}/recordings",
            data=recording_form(wrong_player["id"]),
            files={"file": ("take.wav", vocal_wav, "audio/wav")},
        )
        assert_error(rejected, 409, "WRONG_PLAYER_TURN")

        uploaded = client.post(
            f"/api/sessions/{session_id}/recordings",
            data=recording_form(player["id"]),
            files={"file": ("take.wav", vocal_wav, "audio/wav")},
        )
        assert uploaded.status_code == 200, uploaded.text
        recording = uploaded.json()
        assert recording["status"] == "ready"
        assert recording["rawUrl"] is None
        assert recording["silent"] is False
        assert recording["appliedOffsetMs"] == 500
        mix_urls.append(recording["mixUrl"])

        playable = client.get(recording["mixUrl"])
        assert playable.status_code == 200
        assert playable.headers["content-type"] == "audio/mpeg"
        assert len(playable.content) > 10_000
        raw_guess = recording["mixUrl"].replace("mix.mp3", "raw.wav")
        assert client.get(raw_guess).status_code == 404

        if index < len(players) - 1:
            assert recording["nextPhase"] == "NEXT_PLAYER"
            next_turn = client.post(f"/api/sessions/{session_id}/next-player")
            assert next_turn.json()["phase"] == "TURN_INTRO"
            assert next_turn.json()["currentPlayerId"] == players[index + 1]["id"]
        else:
            assert recording["nextPhase"] == "PROCESSING"

    state = client.get(f"/api/sessions/{session_id}").json()
    assert state["allArtifactsReady"] is True
    assert not any(url in str(state) for url in mix_urls)

    finalized = client.post(f"/api/sessions/{session_id}/finalize")
    assert finalized.status_code == 200
    reveal = finalized.json()
    assert reveal["phase"] == "REVEAL"
    assert len(reveal["performances"]) == 3
    assert {item["mixUrl"] for item in reveal["performances"]} == set(mix_urls)
    assert all(
        item["score"]["scoringProfile"] != "completion_only"
        for item in reveal["performances"]
    )
    assert all(
        0 <= item["score"]["technicalTotal"] <= 100
        for item in reveal["performances"]
    )
    assert all(
        item["feedback"]["source"] == "fallback"
        for item in reveal["performances"]
    )
    assert all(item["evidence"] is not None for item in reveal["performances"])
    for item in reveal["performances"]:
        evidence = item["evidence"]
        assert evidence["durationMs"] > 0
        assert len(evidence["referenceWaveform"]) == 180
        assert len(evidence["playerWaveform"]) == 180
        assert len(evidence["referencePitchMidi"]) == 180
        assert len(evidence["playerPitchMidi"]) == 180
        assert max(evidence["referenceWaveform"]) == 1
        assert max(evidence["playerWaveform"]) == 1

    reveal_ids = [item["revealId"] for item in reveal["performances"]]
    completed = client.post(
        f"/api/sessions/{session_id}/reveal-complete",
        json={"revealIds": reveal_ids},
    )
    assert completed.json()["phase"] == "RESULTS"

    final = client.get(f"/api/sessions/{session_id}/results/final")
    assert final.status_code == 200
    results = final.json()
    assert results["phase"] == "RESULTS"
    assert len(results["performances"]) == 3
    assert results["technicalWinnerPlayerId"] in {player["id"] for player in players}

    final_narration = client.get(f"/api/sessions/{session_id}/narration/results")
    assert final_narration.status_code == 200
    assert "technical crown" in final_narration.json()["text"]


def test_validation_errors_use_shared_shape(client: TestClient) -> None:
    response = client.post(
        "/api/sessions",
        json={"playerNames": [], "songId": "summer-day"},
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert response.json()["error"]["retryable"] is False

    duplicate_names = client.post(
        "/api/sessions",
        json={"playerNames": ["Ava", "ava", "Cam"], "songId": "summer-day"},
    )
    assert_error(duplicate_names, 422, "VALIDATION_ERROR")

    too_many = client.post(
        "/api/sessions",
        json={
            "playerNames": ["A", "B", "C", "D", "E"],
            "songId": "summer-day",
        },
    )
    assert_error(too_many, 422, "VALIDATION_ERROR")

    missing_route = client.get("/api/definitely-not-a-route")
    assert_error(missing_route, 404, "NOT_FOUND")


def test_variable_player_counts_are_accepted(client: TestClient) -> None:
    for names in [["Solo"], ["A", "B"], ["A", "B", "C", "D"]]:
        response = client.post(
            "/api/sessions",
            json={"playerNames": names, "songId": "summer-day"},
        )
        assert response.status_code == 201
        payload = response.json()
        assert len(payload["players"]) == len(names)
        assert [player["turnOrder"] for player in payload["players"]] == list(
            range(len(names))
        )

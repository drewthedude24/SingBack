import time

from fastapi.testclient import TestClient


def headers(credentials):
    return {"Authorization": f"Bearer {credentials['token']}"}


def create(client, name="Andrew"):
    response = client.post("/api/rooms", json={"displayName": name})
    assert response.status_code == 201, response.text
    return response.json()


def join(client, host, name="Jonathan"):
    response = client.post(f"/api/rooms/{host['code']}/join", json={"displayName": name})
    assert response.status_code == 201, response.text
    return response.json()


def action(client, member, route, **kwargs):
    return client.post(f"/api/rooms/{member['code']}/{route}", headers=headers(member), **kwargs)


def ready_and_start(client, members):
    for member in members:
        assert action(client, member, "ready", json={"ready": True}).status_code == 200
    response = action(client, members[0], "start")
    assert response.status_code == 200, response.text
    for member in members:
        assert action(client, member, "listened").status_code == 200


def wait_for_results(client, host):
    for _ in range(200):
        response = client.get(f"/api/rooms/{host['code']}", headers=headers(host))
        assert response.status_code == 200, response.text
        room = response.json()
        assert not room["error"], room["error"]
        if room["phase"] == "RESULTS":
            return room
        time.sleep(0.05)
    raise AssertionError("Results never became available")


def test_room_permissions_capacity_and_membership(client: TestClient):
    host = create(client)
    code = host["code"]
    assert len(code) == 6
    assert "token" not in host["room"]
    assert client.get(f"/api/rooms/{code}").status_code == 401
    assert client.get(f"/api/rooms/{code}", headers={"Authorization": "Bearer fake"}).status_code == 403
    assert client.post(f"/api/rooms/{code}/join", json={"displayName": "andrew"}).status_code == 409
    guest = join(client, host)
    assert action(client, guest, "start").status_code == 403
    assert action(client, host, "start").status_code == 409
    join(client, host, "Player 3")
    join(client, host, "Player 4")
    assert client.post(f"/api/rooms/{code}/join", json={"displayName": "Player 5"}).status_code == 409
    assert client.delete(f"/api/rooms/{code}/players/{host['room']['meId']}", headers=headers(guest)).status_code == 403
    assert action(client, guest, "leave").status_code == 204
    assert client.get(f"/api/rooms/{code}", headers=headers(guest)).status_code == 403
    assert len(join(client, host, "Replacement")["room"]["players"]) == 4


def test_multidevice_round_auth_turns_results_and_rematch(client: TestClient, vocal_wav: bytes):
    host, guest = create(client), None
    guest = join(client, host)
    ready_and_start(client, [host, guest])
    internal_id = client.app.state.room_service._rooms[host["code"]].session_id
    assert client.get(f"/api/sessions/{internal_id}").status_code == 403
    assert client.post(f"/api/sessions/{internal_id}/reference-complete").status_code == 403
    assert client.post(f"/api/rooms/{host['code']}/join", json={"displayName": "Late"}).status_code == 409
    form = {"mimeType": "audio/wav", "prerollMs": "0", "durationMs": "1200"}
    def upload(member, content=vocal_wav):
        return action(client, member, "recordings", data=form, files={"file": ("take.wav", content, "audio/wav")})
    assert upload(guest).status_code == 409  # Cannot submit someone else's turn.
    invalid = upload(host, b"not audio")
    assert invalid.status_code == 422  # Reservation is released on failure.
    assert internal_id not in invalid.text
    first = upload(host)
    assert first.status_code == 200, first.text
    assert first.json()["currentPlayerId"] == guest["room"]["meId"]
    assert first.json()["results"] is None
    assert upload(host).status_code == 409
    assert upload(guest).status_code == 200
    room = wait_for_results(client, host)
    guest_view = client.get(f"/api/rooms/{host['code']}", headers=headers(guest)).json()
    assert room["results"] == guest_view["results"]
    assert room["progress"]["percent"] == 100
    assert len(room["results"]["performances"]) == 2
    assert {p["playerId"] for p in room["results"]["performances"]} == {p["id"] for p in room["players"]}
    for performance in room["results"]["performances"]:
        assert performance["mixUrl"].startswith(f"/api/rooms/{host['code']}/mixes/")
        assert client.get(performance["mixUrl"]).status_code == 200
        assert len(performance["evidence"]["playerWaveform"]) == 180
    assert action(client, guest, "rematch").status_code == 403
    assert action(client, host, "rematch").json()["phase"] == "LOBBY"
    assert not client.get(f"/api/rooms/{host['code']}", headers=headers(guest)).json()["players"][0]["ready"]
    ready_and_start(client, [host, guest])
    assert client.get(f"/api/rooms/{host['code']}", headers=headers(host)).json()["roundNumber"] == 2
    assert action(client, host, "leave").status_code == 204
    assert client.get(f"/api/rooms/{host['code']}", headers=headers(guest)).json()["phase"] == "CLOSED"


def test_host_can_recover_from_missing_listener_and_player(client: TestClient):
    host = create(client)
    guest = join(client, host)
    for member in [host, guest]:
        action(client, member, "ready", json={"ready": True})
    action(client, host, "start")
    assert action(client, guest, "skip").status_code == 403
    assert action(client, host, "skip").json()["phase"] == "TURN_INTRO"
    assert action(client, host, "skip").status_code == 200
    assert action(client, host, "skip").status_code == 200
    room = wait_for_results(client, host)
    assert all(p["score"]["technicalTotal"] == 0 for p in room["results"]["performances"])


def test_closed_room_and_invalid_input(client: TestClient):
    assert client.post("/api/rooms", json={"displayName": "   "}).status_code == 422
    assert client.post("/api/rooms/ABC234/join", json={"displayName": "Hi"}).status_code == 404
    host = create(client)
    action(client, host, "leave")
    assert client.post(f"/api/rooms/{host['code']}/join", json={"displayName": "Hi"}).status_code == 409

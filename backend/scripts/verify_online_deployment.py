"""Exercise independent device memberships against a live/local server.

Only public song fixtures are uploaded. Tokens stay in process memory and are
never written to the report. --turn-seconds simulates time spent singing so the
report distinguishes overlapping background work from the final wait.
"""
import argparse
import json
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx
from backend.app.services.audio_service import resolve_ffmpeg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--players", type=int, choices=range(2, 5), default=4)
    parser.add_argument("--turn-seconds", type=float, default=10)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mobile-formats", action="store_true", help="Alternate streaming WebM/Opus and fragmented MP4/AAC uploads")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=180) as client:
        def request(method, path, member=None, **kwargs):
            if member:
                kwargs["headers"] = {"Authorization": f"Bearer {member['token']}"}
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json() if response.content and "json" in response.headers.get("content-type", "") else None

        health = request("GET", "/api/health")
        host = request("POST", "/api/rooms", json={"displayName": "Deployment host"})
        base = f"/api/rooms/{host['code']}"
        members = [host] + [request("POST", base + "/join", json={"displayName": f"Deployment guest {i}"})
                            for i in range(1, args.players)]
        assert client.get(base).status_code == 401
        assert client.post(base + "/start", headers={"Authorization": f"Bearer {members[1]['token']}"}).status_code == 403
        for member in members:
            request("POST", base + "/ready", member, json={"ready": True})
        room = request("POST", base + "/start", host)
        song = room["song"]
        for member in members:
            request("POST", base + "/listened", member)
        fixture = (repository / "assets/songs" / song["id"] / "vocals.wav").read_bytes()
        uploads = []
        formats = []
        started = time.perf_counter()
        for index, member in enumerate(members):
            time.sleep(max(0, args.turn_seconds))
            mime, name, payload = "audio/wav", "public-song-fixture.wav", fixture
            if args.mobile_formats:
                if index % 2 == 0:
                    mime, name = "audio/webm;codecs=opus", "mobile.webm"
                    encoding = ["-c:a", "libopus", "-f", "webm"]
                else:
                    mime, name = "audio/mp4", "mobile.m4a"
                    encoding = ["-c:a", "aac", "-movflags", "frag_keyframe+empty_moov+default_base_moof", "-f", "mp4"]
                payload = subprocess.run([resolve_ffmpeg(None), "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
                    *encoding, "pipe:1"], input=fixture, capture_output=True, check=True, timeout=20).stdout
            formats.append(mime)
            before = time.perf_counter()
            room = request("POST", base + "/recordings", member,
                data={"mimeType": mime, "prerollMs": "0", "durationMs": "10000"},
                files={"file": (name, payload, mime)})
            uploads.append(round(time.perf_counter() - before, 3))
            print(f"Uploaded player {index + 1}/{args.players}: {uploads[-1]}s; {room['phase']}; {room['progress']['percent']}%", flush=True)
        wait_started = time.perf_counter()
        samples = []
        while room["phase"] != "RESULTS":
            assert not room["error"], room["error"]
            assert time.perf_counter() - wait_started < 180, "Results timed out"
            request_started = time.perf_counter()
            room = request("GET", base, host)
            samples.append({"sinceLastUploadSeconds": round(time.perf_counter() - wait_started, 3),
                "responseSeconds": round(time.perf_counter() - request_started, 3),
                "percent": room["progress"]["percent"], "phase": room["phase"]})
            if len(samples) == 1 or samples[-1]["percent"] != samples[-2]["percent"]:
                print(f"Live progress {samples[-1]['percent']}% · {samples[-1]['phase']}", flush=True)
            if room["phase"] != "RESULTS":
                time.sleep(.5)
        final_wait = time.perf_counter() - wait_started
        assert room["progress"]["percent"] == 100
        final = room["results"]
        assert len(final["performances"]) == args.players
        assert request("GET", base, members[-1])["results"] == final
        for performance in final["performances"]:
            assert len(performance["evidence"]["playerWaveform"]) == 180
            assert performance["score"]["scoringProfile"] != "completion_only"
            assert client.get(performance["mixUrl"]).status_code == 200
        result = {"createdUtc": datetime.now(timezone.utc).isoformat(), "url": args.url,
            "players": args.players, "song": song["id"], "status": "passed", "health": health,
            "simulatedTurnSeconds": args.turn_seconds, "uploadSeconds": uploads,
            "uploadFormats": formats,
            "waitAfterLastUploadSeconds": round(final_wait, 3),
            "totalRoundSeconds": round(time.perf_counter() - started, 3),
            "performances": [{"score": p["score"]["technicalTotal"], "feedbackSource": p["feedback"]["source"],
                              "diagnostics": p["score"]["diagnostics"]} for p in final["performances"]],
            "pollSamples": samples}
        assert request("POST", base + "/rematch", host)["phase"] == "LOBBY"
        assert request("GET", base, members[-1])["phase"] == "LOBBY"
        request("POST", base + "/leave", host)
        assert request("GET", base, members[-1])["phase"] == "CLOSED"
        if args.output:
            args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({key: value for key, value in result.items() if key != "pollSamples"}, indent=2), flush=True)


if __name__ == "__main__":
    main()

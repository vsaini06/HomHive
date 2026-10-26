"""Validate the configured autonomous pipeline through the public API with real providers.

Start the API and exactly one worker, then run this script with an authorized
household account. Credentials are read interactively, never printed or stored.
"""
from __future__ import annotations

import argparse
import getpass
import json
import mimetypes
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def request(base: str, path: str, *, token: str = "", method: str = "GET",
            body: bytes | None = None, content_type: str = "application/json") -> dict:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(base + path, method=method, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read(4096)).get("detail", "Request failed")
        except (ValueError, AttributeError):
            detail = "Request failed"
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from None


def multipart(photo: Path) -> tuple[bytes, str]:
    kind, _ = mimetypes.guess_type(photo.name)
    if kind not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Provide a JPEG, PNG or WebP photograph")
    delimiter = "HH" + secrets.token_hex(15)
    data = photo.read_bytes()
    if not data or len(data) > 10 * 1024 * 1024:
        raise ValueError("Check photograph size and backend media limits")
    body = (f"--{delimiter}\r\nContent-Disposition: form-data; name=\"defer_analysis\"\r\n\r\ntrue\r\n"
            f"--{delimiter}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"scan\"\r\n"
            f"Content-Type: {kind}\r\n\r\n").encode() + data + (f"\r\n--{delimiter}--\r\n").encode()
    return body, f"multipart/form-data; boundary={delimiter}"


def main():
    p = argparse.ArgumentParser(description="One live HomHive household scan, using configured AI providers")
    p.add_argument("--image", required=True, type=Path)
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--timeout", type=int, default=360)
    p.add_argument("--expect-room", default="")
    p.add_argument("--expect-term", default="")
    a = p.parse_args()
    parsed = urllib.parse.urlsplit(a.api)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        p.error("The smoke test sends credentials only to a local HTTP server")
    if a.timeout < 30 or a.timeout > 1200:
        p.error("Timeout must be between 30 and 1200 seconds")
    if not a.image.is_file():
        p.error("Image file not found")
    base = a.api.rstrip("/")
    print("Connecting to local HomHive API; actual provider charges may apply.")
    if request(base, "/health").get("status") != "ok":
        raise RuntimeError("Backend health check failed")
    email = input("HomHive account email: ").strip()
    password = getpass.getpass("HomHive account password (not echoed): ")
    login = request(base, "/auth/login", method="POST", body=json.dumps({"email": email, "password": password}).encode())
    password = None
    token = login["access_token"]
    household = login["households"][0]
    prefix = "/households/" + urllib.parse.quote(household, safe="")
    before = request(base, prefix + "/autonomous-tasks", token=token)["tasks"]
    existing_ids = {t["id"] for t in before}
    body, mime = multipart(a.image)
    uploaded = request(base, prefix + "/media", token=token, method="POST", body=body, content_type=mime)
    media_id = uploaded["id"]
    print("Photo persisted. Waiting for autonomous worker status; no legacy analysis requested.")
    terminal = {"completed", "held_unverified_room", "failed"}
    deadline = time.monotonic() + a.timeout
    last_state = None
    state = None
    while time.monotonic() < deadline:
        jobs = request(base, prefix + "/autonomous-scan-jobs", token=token)["jobs"]
        job = next((x for x in jobs if x["media_id"] == media_id), None)
        state = job["state"] if job else "missing"
        if state != last_state:
            print("Scan state:", state)
            last_state = state
        if state in terminal:
            if job.get("message"):
                print("Status note:", job["message"])
            break
        time.sleep(8)
    if state != "completed":
        raise RuntimeError("Scan not completed. Inspect the worker and recent scan status.")
    after = request(base, prefix + "/autonomous-tasks", token=token)["tasks"]
    new = [t for t in after if t["id"] not in existing_ids]
    print(f"Independent processing completed; {len(new)} newly persisted tasks, {len(after)} total.")
    for task in new:
        print(json.dumps({"title": task["title"], "room": task.get("room_category"),
            "created_at": task.get("created_at"), "status": task["status"],
            "effort_min": task.get("effort_min"), "evidence": task.get("evidence_summary")}, ensure_ascii=False))
    if a.expect_room and not any(a.expect_room.casefold() in (t.get("room_category") or "").casefold() for t in new):
        raise RuntimeError("Expected room category was not established in a new task")
    if a.expect_term and not any(a.expect_term.casefold() in (t.get("title") or "").casefold() for t in new):
        raise RuntimeError("Expected task phrase not found in newly created tasks")
    print("Live API-to-worker-to-task smoke test completed. Visually review task necessity before acceptance.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print("FAILED:", error, file=sys.stderr)
        raise SystemExit(1)

"""Smoke-test the queue patient-calling flow over HTTP.

Signs in, picks a patient, issues a ticket, calls it, reads back the spoken
line and the rendered audio, confirms the board shows it CALLED, and cancels
the ticket so nothing is left behind.

With --start-api it will start the API gateway itself first (only if the port
is not already answering), so a single command is enough.

Why it calls the ticket it just created instead of "call next": call-next
claims whichever patient is genuinely first in line, which on a live facility
may be a real person. Pass --call-next when you specifically want to exercise
that path (do it on an empty or test queue).

Run from anywhere:

    services/api-gateway/.venv/Scripts/python.exe services/api-gateway/scripts/test_queue_call.py --start-api --test-patient "Caroline Wanjiru Muriuki" --room "Consultation Room 2"

Options fall back to these environment variables, then to the local test
account: AIFYA_EMAIL, AIFYA_PASSWORD, AIFYA_FACILITY, AIFYA_DUTY, AIFYA_API.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API = "http://localhost:8000/api/v1"
DEFAULT_EMAIL = "hr.probe5473@example.com"
DEFAULT_PASSWORD = "Aifya@Temp2026"
DEFAULT_FACILITY = "Probe Chain Clinic 5473"
DEFAULT_DUTY = "facility_admin"

API_LOG = pathlib.Path(tempfile.gettempdir()) / "aifya-api.log"


class Step:
    """Counts the checks so the exit code can gate a deployment."""

    def __init__(self) -> None:
        self.failures = 0

    def ok(self, passed: bool, label: str, detail: str = "") -> None:
        mark = "PASS" if passed else "FAIL"
        if not passed:
            self.failures += 1
        suffix = f"  ({detail})" if detail else ""
        print(f"  [{mark}] {label}{suffix}")


def request(method, url, token=None, body=None, binary=False):
    """One HTTP call. Returns (status, headers, parsed-json-or-bytes)."""

    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            lowered = {k.lower(): v for k, v in resp.headers.items()}
            if binary:
                return resp.status, lowered, raw
            return resp.status, lowered, json.loads(raw.decode() or "null")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        lowered = {k.lower(): v for k, v in exc.headers.items()}
        if binary:
            return exc.code, lowered, raw
        try:
            return exc.code, lowered, json.loads(raw.decode() or "null")
        except Exception:
            return exc.code, lowered, raw.decode(errors="replace")


def api_reachable(api: str, timeout: float = 3.0) -> bool:
    """True when something is answering on the API port."""

    try:
        with urllib.request.urlopen(f"{api}/auth/duties", timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def start_api(api: str) -> tuple[bool, str]:
    """Start uvicorn in the background with a clean DEBUG, then wait for it."""

    if api_reachable(api):
        return True, "already running"

    service_root = pathlib.Path(__file__).resolve().parents[1]
    parts = urllib.parse.urlparse(api)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or 8000

    env = {**os.environ}
    # Clean debug flag to ensure Settings() import succeeds without errors
    env["DEBUG"] = "false"

    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    with open(API_LOG, "ab") as sink:
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)],
            cwd=str(service_root), env=env, stdout=sink, stderr=sink,
            stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True,
        )

    for _ in range(40):
        time.sleep(1.5)
        if api_reachable(api):
            return True, f"started on {host}:{port} (log {API_LOG})"
    return False, f"did not come up; see {API_LOG}"


def tail_api_log(lines: int = 25) -> None:
    """Print the end of the API log so a startup crash is visible."""

    try:
        content = API_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        print(f"  (no log at {API_LOG})")
        return
    for line in content[-lines:]:
        print(f"    {line}")


def resolve_patient(api, token, name):
    """Find a patient by name. Returns (patient, note)."""

    tokens = [t for t in name.split() if t]
    query = urllib.parse.quote(tokens[-1] if tokens else name)
    status, _, payload = request("GET", f"{api}/patients?q={query}&page=1&page_size=25", token)
    items = payload.get("items") if isinstance(payload, dict) else None
    if status != 200 or not items:
        return None, f"HTTP {status}"
    wanted = " ".join(name.lower().split())
    for item in items:
        full = " ".join(
            str(part) for part in (item.get("first_name"), item.get("middle_name"), item.get("last_name")) if part
        ).lower()
        if " ".join(full.split()) == wanted:
            return item, "exact name match"
    return items[0], f"closest match ({len(items)} returned)"


def resolve_room(api, token, label):
    """Find a service point by label, or create it. Returns (id, note)."""

    status, _, payload = request("GET", f"{api}/queue/service-points", token)
    points = payload if isinstance(payload, list) else []
    wanted = label.strip().lower()
    for point in points:
        for field in ("display_label", "name"):
            value = (point.get(field) or "").strip().lower()
            if value and value == wanted:
                return str(point["id"]), f"reusing {point.get('display_label') or point.get('name')}"
    status, _, created = request("POST", f"{api}/queue/service-points", token, {"name": label, "kind": "room"})
    if status == 201 and isinstance(created, dict):
        return str(created["id"]), "created new room"
    return None, f"could not resolve room (HTTP {status})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test queue patient calling.")
    parser.add_argument("--api", default=os.environ.get("AIFYA_API", DEFAULT_API))
    parser.add_argument("--email", default=os.environ.get("AIFYA_EMAIL", DEFAULT_EMAIL))
    parser.add_argument("--password", default=os.environ.get("AIFYA_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument("--facility", default=os.environ.get("AIFYA_FACILITY", DEFAULT_FACILITY))
    parser.add_argument("--duty", default=os.environ.get("AIFYA_DUTY", DEFAULT_DUTY))
    
    # Updated: Supports both --patient and --test-patient as flags
    parser.add_argument("--patient", "--test-patient", dest="patient", help="Patient name to search for, e.g. 'Caroline Wanjiru Muriuki'")
    
    parser.add_argument("--patient-id", help="Skip the name lookup and use this id")
    parser.add_argument("--room", help="Room to call the patient into, e.g. 'Consultation Room 2'")
    parser.add_argument("--start-api", action="store_true", help="Start the API gateway first if the port is not answering")
    parser.add_argument("--call-next", action="store_true", help="Use /queue/call-next instead of calling the new ticket")
    parser.add_argument("--keep", action="store_true", help="Leave the ticket open instead of cancelling it")
    parser.add_argument("--play", action="store_true", help="Open the rendered audio in the default player")
    parser.add_argument("--audio-out", help="Where to write the rendered audio (default: a temp file)")
    args = parser.parse_args()

    api = args.api.rstrip("/")
    step = Step()
    print(f"Aifya queue call smoke test -> {api}")

    # 0. Bring the API up if asked.
    if args.start_api:
        ok, note = start_api(api)
        step.ok(ok, "API reachable", note)
        if not ok:
            print("  --- API startup log (last lines) ---")
            tail_api_log()
            return 1

    # 1. Sign in.
    status, _, payload = request("POST", f"{api}/auth/login", body={
        "email": args.email, "password": args.password,
        "facility": args.facility, "duty": args.duty,
    })
    if status != 200 or not isinstance(payload, dict) or "access_token" not in payload:
        print(f"  [FAIL] sign in -> HTTP {status}: {payload}")
        print("  is the API running? add --start-api, or run:")
        print("    set DEBUG=false && .venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000")
        return 1
    token = payload["access_token"]
    user = payload.get("user", {})
    step.ok(True, "signed in", f"{user.get('email')} @ {user.get('facilityName')} [{','.join(user.get('roles') or [])}]")
    if not user.get("facilityId"):
        print("  [FAIL] token carries no facility")
        return 1
    facility_id = str(user["facilityId"])

    # 2. Pick a patient.
    if args.patient_id:
        patient_id = args.patient_id
        step.ok(True, "patient given", args.patient_id[:8])
    elif args.patient:
        patient, note = resolve_patient(api, token, args.patient)
        if patient is None:
            print(f"  [FAIL] no patient matched {args.patient!r} at this facility -> {note}")
            return 1
        patient_id = str(patient["id"])
        display = " ".join(str(p) for p in (patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")) if p)
        step.ok(True, "patient resolved", f"{display} / {patient.get('mrn')} / {note}")
    else:
        status, _, payload = request("GET", f"{api}/patients?page=1&page_size=1", token)
        items = payload.get("items") if isinstance(payload, dict) else None
        if status != 200 or not items:
            print(f"  [FAIL] patient lookup -> HTTP {status}: {payload}")
            return 1
        patient_id = str(items[0]["id"])
        step.ok(True, "patient resolved", patient_id[:8])

    # 3. Optional destination room.
    service_point_id = None
    if args.room:
        service_point_id, note = resolve_room(api, token, args.room)
        step.ok(service_point_id is not None, "room ready", f"{args.room} ({note})")

    # 4. Issue a ticket.
    body = {"patient_id": patient_id, "priority": 100, "triage_category": "standard"}
    if service_point_id:
        body["service_point_id"] = service_point_id
    status, _, ticket = request("POST", f"{api}/queue/tickets", token, body)
    if status != 201 or not isinstance(ticket, dict):
        print(f"  [FAIL] issue ticket -> HTTP {status}: {ticket}")
        return 1
    ticket_id, number = ticket["id"], ticket["ticket_number"]
    step.ok(str(ticket.get("facility_id")) == facility_id, "ticket issued in the sign-in facility",
            f"{number} facility {str(ticket.get('facility_id'))[:8]}")

    # 5. Call it.
    if args.call_next:
        payload_body = {"service_point_id": service_point_id} if service_point_id else {}
        status, _, called = request("POST", f"{api}/queue/call-next", token, payload_body)
        path = "POST /queue/call-next"
    else:
        status, _, called = request("POST", f"{api}/queue/tickets/{ticket_id}/call", token, {})
        path = f"POST /queue/tickets/{number}/call"
    if status != 200 or not isinstance(called, dict):
        print(f"  [FAIL] {path} -> HTTP {status}: {called}")
        return 1
    step.ok(called.get("status") == "CALLED", "call moved the ticket to CALLED",
            f"{called.get('ticket_number')} status={called.get('status')}")
    called_id = str(called.get("id"))

    # 6. The spoken line.
    status, _, line = request("GET", f"{api}/voice/announcements/{called_id}", token)
    if status != 200 or not isinstance(line, dict):
        print(f"  [FAIL] announcement -> HTTP {status}: {line}")
        return 1
    print(f"  ticket card : {number}")
    print(f"  speaker says: {line.get('text')!r}")
    print(f"  normalised  : {line.get('normalized_text')!r}")
    step.ok(bool(line.get("text")), "spoken line built")
    step.ok(not any(w in (line.get("text") or "") for w in ("MRN-",)), "spoken line carries no patient identifier")
    if args.room:
        step.ok(args.room.lower() in (line.get("text") or "").lower(), "spoken line names the room", args.room)

    # 7. The audio.
    status, headers, audio = request("GET", f"{api}/voice/announcements/{called_id}/audio", token, binary=True)
    audio_path = None
    if status != 200:
        step.ok(False, "audio rendered", f"HTTP {status}: {audio[:120]!r}")
    else:
        audio_path = pathlib.Path(args.audio_out) if args.audio_out else pathlib.Path(tempfile.gettempdir()) / f"aifya-call-{number}.mp3"
        audio_path.write_bytes(audio)
        step.ok(len(audio) > 1000, "audio rendered", f"{len(audio)} bytes {headers.get('content-type')}")
        print(f"  audio file  : {audio_path}")

    # 8. The board agrees.
    status, _, board = request("GET", f"{api}/queue", token)
    rows = board.get("items") if isinstance(board, dict) else None
    if status != 200 or rows is None:
        step.ok(False, "board readable", f"HTTP {status}")
    else:
        row = next((r for r in rows if str(r.get("id")) == called_id), None)
        step.ok(row is not None and row.get("status") in ("CALLED", "IN_SERVICE"),
                "ticket shows on the board as called", f"{len(rows)} row(s) on the board")
        step.ok(all(str(r.get("facility_id")) == facility_id for r in rows),
                "every board row belongs to this facility only")

    # 9. Play it, if asked.
    if args.play and audio_path is not None and hasattr(os, "startfile"):
        os.startfile(str(audio_path))

    # 10. Tidy up.
    if args.keep:
        print(f"  left open   : {number} ({ticket_id})")
    else:
        status, _, done = request("POST", f"{api}/queue/tickets/{ticket_id}/cancel", token, {"reason": "automated smoke test"})
        step.ok(status == 200, "test ticket cancelled", f"HTTP {status}")

    print(f"\n{'ALL CHECKS PASSED' if not step.failures else str(step.failures) + ' CHECK(S) FAILED'}")
    return step.failures


if __name__ == "__main__":
    sys.exit(main())
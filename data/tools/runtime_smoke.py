"""실행 중인 로컬 서비스의 최소 운영 계약을 빠르게 검증한다."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from scheduler.completion_audit import audit_latest_run


BACKEND = "http://localhost:8080"
FRONTEND = "http://localhost:5173"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _json(path: str) -> dict:
    with urlopen(f"{BACKEND}{path}", timeout=10) as response:
        assert response.status == 200, f"{path}: HTTP {response.status}"
        return json.load(response)


def _assert_frontend_routes() -> None:
    for path in ("/", "/app", "/stock/SPY", "/herd-lab"):
        with urlopen(f"{FRONTEND}{path}", timeout=10) as response:
            body = response.read().decode("utf-8")
            assert response.status == 200, f"frontend {path}: HTTP {response.status}"
            assert '<div id="root"></div>' in body, f"frontend {path}: app shell missing"


def _assert_google_login_redirect() -> None:
    opener = build_opener(_NoRedirect)
    try:
        opener.open(
            Request(f"{BACKEND}/oauth2/authorization/google"),
            timeout=10,
        )
    except HTTPError as error:
        assert 300 <= error.code < 400, f"google login: HTTP {error.code}"
        location = error.headers.get("Location", "")
        assert "accounts.google.com" in location, "google login redirect target missing"
        return
    raise AssertionError("google login did not redirect")


def _assert_auth_contract() -> None:
    payload = _json("/api/auth/me")
    assert payload["success"] is True
    assert payload["data"]["authenticated"] is False


def _assert_spy_contract() -> None:
    payload = _json("/api/observations/SPY")
    observation = payload["data"]
    assert payload["success"] is True
    assert observation["availabilityStatus"] == "AVAILABLE"
    assert observation["freshnessStatus"] == "FRESH"
    assert observation["stateModelVersion"] == "HERD_STATE_S1"
    assert observation["transitionModelVersion"] == "HERD_TRANSITION_S1"
    assert observation["operationalAction"] == "HOLD"
    assert float(observation["operationalActionRatio"]) == 0.0
    assert observation["directionPrediction"] is False
    assert "v4" not in json.dumps(observation).lower()


def main() -> int:
    health = _json("/actuator/health")
    assert health["status"] == "UP"
    _assert_frontend_routes()
    _assert_auth_contract()
    _assert_google_login_redirect()
    _assert_spy_contract()
    audit = audit_latest_run()
    assert audit["passed"] is True, f"scheduler audit: {audit}"
    print(
        json.dumps(
            {
                "status": "PASS",
                "contracts": [
                    "backend_health",
                    "frontend_routes",
                    "anonymous_auth",
                    "google_oauth_redirect",
                    "spy_state_s1_freshness",
                    "operational_hold_boundary",
                    "scheduler_completion",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

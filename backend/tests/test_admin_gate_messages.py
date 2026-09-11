"""What a refused admin request is allowed to say (spec section 6.6).

`"Not authorised."` used to answer three different situations, and one of them
is not an authorisation failure at all:

1. a wrong token, when real admins are provisioned
2. a wrong token, when only a bootstrap token is configured
3. **no admin users and no bootstrap token** -- the server cannot accept any
   token from anyone, and no value the operator types will ever work

(3) is a configuration fault wearing an authorisation error's clothes. It cost
real time: an operator typing correct-looking tokens into `/admin/schemes` has
no way to learn that the server was never able to accept one. It now answers
503, matching how `_require_database` already reports "admin needs something
the deployment has not given it".

(1) and (2) must stay identical to each other. Distinguishing them would tell
an unauthenticated caller whether admins have been provisioned, which is a fact
about the deployment they have no business learning. The distinction this file
protects is *configured vs not*, never *provisioned vs not*.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings, reload_settings
from app.main import app

# Pinned in conftest.py, so it is the same on a laptop and on CI.
GOOD_TOKEN = "test-bootstrap-token-not-a-real-one"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unconfigured(monkeypatch):
    """A server with no admin users and no bootstrap token."""
    monkeypatch.setenv("ADMIN_BOOTSTRAP_TOKEN", "")
    reload_settings()
    yield
    monkeypatch.undo()
    reload_settings()


class TestTheServerCanAuthoriseSomeone:
    def test_the_bootstrap_token_is_accepted(self, client):
        response = client.get(
            "/api/admin/whoami", headers={"Authorization": f"Bearer {GOOD_TOKEN}"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == "owner"

    def test_a_wrong_token_is_refused_without_explanation(self, client):
        response = client.get(
            "/api/admin/whoami", headers={"Authorization": "Bearer wrong"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not authorised."

    def test_no_token_asks_for_one(self, client):
        response = client.get("/api/admin/whoami")
        assert response.status_code == 401
        assert response.json()["detail"] == "Admin token required."


class TestTheServerCannotAuthoriseAnyone:
    """The case that used to be indistinguishable from a typo."""

    def test_it_says_so_rather_than_refusing(self, client, unconfigured):
        assert get_settings().admin_bootstrap_token in (None, "")

        response = client.get(
            "/api/admin/whoami", headers={"Authorization": "Bearer anything-at-all"}
        )

        assert response.status_code == 503, (
            "a server that can accept no token is misconfigured, not refusing"
        )
        detail = response.json()["detail"]
        assert "not configured" in detail.lower()
        # Actionable: it must name what to set, or it is the old message with
        # a new status code.
        assert "ADMIN_BOOTSTRAP_TOKEN" in detail or "admin_users" in detail

    def test_a_missing_token_still_asks_for_one_first(self, client, unconfigured):
        """Header checks come before configuration checks: the caller's own
        mistake is the more useful thing to report when they made one."""
        response = client.get("/api/admin/whoami")

        assert response.status_code == 401
        assert response.json()["detail"] == "Admin token required."

    def test_writes_report_it_too(self, client, unconfigured):
        response = client.post(
            "/api/admin/taxonomy",
            json={"code": "SK999", "name": "Fake", "category": "Fake"},
            headers={"Authorization": "Bearer anything-at-all"},
        )

        assert response.status_code == 503


class TestItDoesNotLeakWhetherAdminsExist:
    def test_wrong_token_says_the_same_thing_either_way(self, client):
        """With a bootstrap token configured, a wrong token gets the plain
        refusal -- the same one a provisioned deployment gives. Whether admins
        exist is not a fact an unauthenticated caller may probe for."""
        response = client.get(
            "/api/admin/whoami", headers={"Authorization": "Bearer wrong"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Not authorised."
        # No hint about provisioning, bootstrap mode, or how close the guess was.
        body = response.text.lower()
        for leak in ("bootstrap", "admin_users", "provision", "no admins"):
            assert leak not in body, f"the refusal leaked {leak!r}"

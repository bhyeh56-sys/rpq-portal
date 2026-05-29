import os
import urllib.error
import urllib.request

import pytest


def test_app_imports():
    from app.main import app

    assert app.title == "RPQ Portal"


def test_required_routes_are_registered():
    from app.main import app

    routes = {
        (path, method)
        for route in app.routes
        for path in [getattr(route, "path", None)]
        for method in (getattr(route, "methods", None) or [])
    }

    assert ("/health", "GET") in routes
    assert ("/admin/investors", "GET") in routes
    assert ("/admin/cashflows", "GET") in routes
    assert ("/admin/unit-price", "GET") in routes
    assert ("/portal/me/summary", "GET") in routes
    assert ("/portal/me/ledger", "GET") in routes
    assert ("/fx/mt5/snapshot", "POST") in routes


def test_health_endpoint_function():
    from app.main import health

    assert health() == {"ok": True}


def _get(base_url: str, path: str, headers: dict[str, str] | None = None):
    request = urllib.request.Request(base_url.rstrip("/") + path, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


@pytest.fixture
def live_base_url():
    base_url = os.getenv("RPQ_TEST_BASE_URL")
    if not base_url:
        pytest.skip("Set RPQ_TEST_BASE_URL to run live HTTP smoke tests")
    return base_url


def test_live_admin_pages_render(live_base_url):
    for path in ("/admin/investors", "/admin/cashflows", "/admin/unit-price"):
        status, body = _get(live_base_url, path)
        assert status == 200
        assert "<html" in body.lower()


def test_live_portal_summary_and_ledger(live_base_url):
    headers = {"X-Investor-Id": "1"}

    status, summary_body = _get(live_base_url, "/portal/me/summary?fund_id=1", headers)
    assert status == 200
    assert '"fund_id":1' in summary_body
    assert '"investor_id":1' in summary_body

    status, ledger_body = _get(live_base_url, "/portal/me/ledger?fund_id=1", headers)
    assert status == 200
    assert '"rows":[' in ledger_body
    assert '"entry_type":"CASH"' in ledger_body

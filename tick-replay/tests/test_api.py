import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

NINJA = b"20240305 093000 1230000;18123.25;18123;18123.25;2\n20240305 093001 0000000;18123.5;18123.25;18123.5;1\n"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TICK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TICK_BACKTESTS", str(tmp_path / "backtests.json"))
    import server.app as app_mod
    importlib.reload(app_mod)
    return TestClient(app_mod.app)


def test_import_then_delete(client):
    assert client.get("/api/symbols").json() == []
    r = client.post("/api/import", data={"symbol": "nq", "tz": "America/New_York"},
                    files=[("files", ("NQ.txt", NINJA, "text/plain"))])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["symbol"] == "NQ" and body["ticks"] == 2 and body["first_ts"] == 1709649000123
    (sym,) = client.get("/api/symbols").json()
    assert sym["symbol"] == "NQ" and sym["point_value"] == 20.0

    # re-import replaces the day instead of doubling it
    client.post("/api/import", data={"symbol": "NQ", "tz": "America/New_York"},
                files=[("files", ("NQ.txt", NINJA, "text/plain"))])
    t = client.get("/api/ticks", params={"symbol": "NQ", "after": 0, "until": 2_000_000_000_000}).json()
    assert len(t["ts"]) == 2

    assert client.delete("/api/symbols/NQ").status_code == 200
    assert client.get("/api/symbols").json() == []


def test_import_rejects_bad_input(client):
    r = client.post("/api/import", data={"symbol": "../x", "tz": "UTC"},
                    files=[("files", ("a.csv", b"ts,price\n1,2\n", "text/csv"))])
    assert r.status_code == 400
    r = client.post("/api/import", data={"symbol": "NQ", "tz": "UTC"},
                    files=[("files", ("a.csv", b"foo,bar\n1,2\n", "text/csv"))])
    assert r.status_code == 400 and "timestamp" in r.json()["detail"]


def test_demo_symbols_use_contract_spec(tmp_path):
    from server.store import spec_for
    assert spec_for("NQ-DEMO")["point_value"] == 20.0
    assert spec_for("MNQ")["point_value"] == 2.0
    assert spec_for("ESZ4")["point_value"] == 50.0


def test_backtest_lifecycle(client):
    client.post("/api/import", data={"symbol": "NQ", "tz": "America/New_York"},
                files=[("files", ("NQ.txt", NINJA, "text/plain"))])
    r = client.post("/api/backtests", json={"name": "Opens", "symbols": ["nq"], "start_ts": 1709600000000,
                                            "end_ts": 1709700000000, "balance": 50000, "fee_per_side": 2.25})
    assert r.status_code == 200, r.text
    bt = r.json()
    assert bt["symbols"] == ["NQ"] and bt["current_ts"] == 1709600000000

    r = client.post(f"/api/backtests/{bt['id']}/progress",
                    content='{"current_ts": 1709649000500, "add_time_ms": 5000, "add_replayed_ms": 60000}',
                    headers={"content-type": "text/plain"})  # what sendBeacon sends
    assert r.status_code == 200, r.text
    trade = {"symbol": "NQ", "side": 1, "qty": 2, "entry_ts": 1709649000123, "entry_px": 18123.25,
             "exit_ts": 1709649000500, "exit_px": 18124.5, "pnl": 45.5, "fees": 4.5}
    assert client.post(f"/api/backtests/{bt['id']}/trades", json=trade).status_code == 200

    got = client.get(f"/api/backtests/{bt['id']}").json()
    assert got["current_ts"] == 1709649000500 and got["time_spent_ms"] == 5000 and got["replayed_ms"] == 60000
    assert len(got["trades"]) == 1 and got["trades"][0]["pnl"] == 45.5

    dup = client.post(f"/api/backtests/{bt['id']}/duplicate").json()
    assert dup["trades"] == [] and dup["name"] == "Opens (copy)"
    assert len(client.get("/api/backtests").json()) == 2
    assert client.delete(f"/api/backtests/{bt['id']}").status_code == 200
    assert client.get(f"/api/backtests/{bt['id']}").status_code == 404


def test_backtest_rejects_unknown_symbol(client):
    r = client.post("/api/backtests", json={"symbols": ["ZZ"], "start_ts": 1, "end_ts": 2})
    assert r.status_code == 404

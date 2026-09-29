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

import os, sys, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"
os.environ["DEMO_PASSWORD"] = "test-pass-1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from fastapi.testclient import TestClient
import main

def client():
    c = TestClient(main.app); c.__enter__()
    t = c.post("/auth/login", json={"email": "demo@aftershock.local", "password": "test-pass-1"}).json()["token"]
    c.headers["Authorization"] = f"Bearer {t}"
    return c

def stolen(c):
    i = c.post("/incidents", json={"description": "My phone was stolen yesterday. Worried about banking and SIM."}).json()
    c.post(f"/incidents/{i['id']}/analyze")
    return i["id"]

def test_auth_rejects_bad_password_and_missing_token():
    c = TestClient(main.app); c.__enter__()
    assert c.post("/auth/login", json={"email": "demo@aftershock.local", "password": "x"}).status_code == 401
    assert c.get("/incidents").status_code == 401

def test_classification_and_orchestration():
    assert main.classify("my passport is gone") == "Passport lost"
    assert "Security Agent" not in main.orchestrate("Passport lost")
    assert "Security Agent" in main.orchestrate("Phone stolen")

def test_plan_and_approval_gate():
    c = client(); iid = stolen(c)
    acts = c.get(f"/incidents/{iid}/actions").json()
    sim = next(a for a in acts if a["title"] == "Block your SIM card")
    assert sim["state"] == "WAITING_APPROVAL"
    assert all(a["state"] in ("COMPLETED", "MONITORING") for a in acts if not a["requires_approval"])

def test_approve_transitions_progress_and_audit():
    c = client(); iid = stolen(c)
    before = c.get(f"/incidents/{iid}").json()["progress"]["percent"]
    sim = next(a for a in c.get(f"/incidents/{iid}/actions").json() if a["title"] == "Block your SIM card")
    r = c.post(f"/actions/{sim['id']}/approve").json()
    assert r["state"] == "COMPLETED" and r["result"]["simulated"] is True
    assert c.get(f"/incidents/{iid}").json()["progress"]["percent"] > before
    log = " ".join(e["message"] for e in c.get(f"/incidents/{iid}/activity").json())
    for s in ("WAITING_APPROVAL -> APPROVED", "APPROVED -> EXECUTING", "EXECUTING -> VERIFYING", "VERIFYING -> COMPLETED"):
        assert s in log
    assert c.post(f"/actions/{sim['id']}/approve").status_code == 409

def test_reject_triggers_replan():
    c = client(); iid = stolen(c)
    fin = next(a for a in c.get(f"/incidents/{iid}/actions").json() if a["title"] == "Review financial exposure")
    r = c.post(f"/actions/{fin['id']}/reject").json()
    assert r["rejected"]["state"] == "REJECTED" and "Alternative" in r["alternative"]["title"]

def test_tool_failure_does_not_crash():
    import asyncio
    with main.Session_() as db:
        u = db.query(main.User).first()
        i = main.Incident(user_id=u.id, description="x"); db.add(i); db.flush()
        a = main.Action(incident_id=i.id, title="t", tool="Failing Tool", agent="Security Agent"); db.add(a); db.flush()
        asyncio.run(main.run_action(db, a))
        assert a.state == "FAILED"

def test_persistence_and_isolation():
    c = client(); iid = stolen(c)
    assert any(i["id"] == iid for i in c.get("/incidents").json())
    t2 = c.post("/auth/register", json={"email": "b@x.io", "password": "pw12345678"}).json()["token"]
    assert c.get(f"/incidents/{iid}", headers={"Authorization": f"Bearer {t2}"}).status_code == 404

def test_seeded_incidents_and_notifications():
    c = client()
    types = {i["type"] for i in c.get("/incidents").json()}
    assert {"Passport lost", "Car accident"} <= types
    assert any(i["progress"]["percent"] == 100 for i in c.get("/incidents").json())
    stolen(c)
    assert any("requires your approval" in n["message"] for n in c.get("/notifications").json())

def test_assets_documents_settings():
    c = client()
    assert c.post("/assets", json={"kind": "Device", "name": "MacBook"}).status_code == 201
    assert c.post("/assets", json={"kind": "Bogus", "name": "x"}).status_code == 422
    r = c.post("/documents", files={"file": ("p.txt", b"Policy number: AB-12345\nProvider: Acme Insure")})
    assert r.status_code == 201 and r.json()["extracted"]["policy_number"] == "****345"
    assert c.post("/documents", files={"file": ("x.exe", b"bad")}).status_code == 415
    assert any(d["name"] == "p.txt" for d in c.get("/documents").json())
    assert c.get("/settings").json()["approval_rules"]["human_approval_required"] is True
    assert c.put("/settings", json={"human_approval_required": False}).status_code == 422

def test_graph_agents_monitoring_and_seed():
    c = client()
    def sim_done(i):
        return any(n["id"] == "SIM" and n["state"] == "COMPLETED" for n in c.get(f"/incidents/{i['id']}/graph").json()["nodes"])
    ph = next(i for i in c.get("/incidents").json() if i["type"] == "Phone stolen" and sim_done(i))
    g = c.get(f"/incidents/{ph['id']}/graph").json()
    assert {n["id"] for n in g["nodes"]} >= {"DEVICE", "SIM", "FINANCE", "INSURANCE"}
    assert next(n for n in g["nodes"] if n["id"] == "SIM")["state"] == "COMPLETED"
    ag = {a["agent"]: a for a in c.get(f"/incidents/{ph['id']}/agents").json()}
    assert ag["Security Agent"]["status"] in ("Completed", "Needs approval") and "Finance Agent" in ag
    assert c.post(f"/incidents/{ph['id']}/monitor").json()["checked"] >= 1

def test_langgraph_pipeline_routes_only_relevant_agents():
    from pipeline import build
    run = build(main.PLANS, main.GENERIC, main.orchestrate)
    out = run({"itype": "Passport lost", "agents": [], "findings": [], "plan": []})
    names = {a for a, _ in out["findings"]}
    assert "Security Agent" not in names and "Recovery Agent" in names and out["plan"]
    out = run({"itype": "Phone stolen", "agents": [], "findings": [], "plan": []})
    assert {"Security Agent", "Finance Agent", "Research Agent"} <= {a for a, _ in out["findings"]}

def test_sse_stream_and_query_token():
    c = client(); iid = stolen(c); tok = c.headers["Authorization"].removeprefix("Bearer ")
    bare = TestClient(main.app)
    with bare.stream("GET", f"/incidents/{iid}/stream", params={"token": tok, "max_seconds": 0}) as r:
        assert r.status_code == 200 and "data:" in "".join(r.iter_text())
    assert bare.get(f"/incidents/{iid}/stream").status_code == 401

class _Fake:
    mode = "LLM MODE"
    def __init__(self, outs): self.outs = list(outs)
    async def generate(self, system, prompt):
        o = self.outs.pop(0)
        if isinstance(o, Exception): raise o
        return o

def _run(provider):
    import asyncio, llm
    return asyncio.run(llm.structured(provider, llm.IncidentSummary, "s", "My phone was stolen in Paris", lambda: llm.heuristic_summary("My phone was stolen in Paris")))

GOOD = '```json\n{"severity":"critical","location":"Paris","summary":"Phone stolen","key_risks":["sim"]}\n```'

def test_llm_retry_then_success():
    obj, fb, issues = _run(_Fake(["not json", GOOD]))
    assert obj.severity == "critical" and fb is False and len(issues) == 1

def test_llm_invalid_schema_and_outage_use_fallback():
    obj, fb, issues = _run(_Fake(['{"severity":"apocalyptic","summary":"x"}', TimeoutError()]))
    assert fb is True and obj.location == "Paris" and "fallback" in issues[-1]

def test_analyze_survives_broken_llm():
    main.PROVIDER = _Fake([RuntimeError("down")] * 2)
    try:
        c = client(); iid = stolen(c)
        assert c.get(f"/incidents/{iid}").json()["progress"]["total"] == 8
        assert any("fallback" in e["message"] for e in c.get(f"/incidents/{iid}/activity").json())
    finally:
        main.PROVIDER = main.get_provider()

def test_pdf_extraction():
    fitz = __import__("pytest").importorskip("fitz")
    d = fitz.open(); d.new_page().insert_text((72, 72), "Policy number: ZX-99871\nProvider: Acme Insure"); raw = d.tobytes()
    c = client()
    r = c.post("/documents", files={"file": ("policy.pdf", raw)}).json()
    assert r["type"] == "Insurance policy" and r["extracted"]["policy_number"] == "****871"
    assert "99871" not in str(r)
    r = c.post("/documents", files={"file": ("scan.png", b"notanimage")}).json()
    assert "unavailable" in r["extracted"]["note"]

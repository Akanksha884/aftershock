"""AFTERSHOCK backend core (DEMO MODE: deterministic, offline, all external actions SIMULATED)."""
import hashlib, hmac, os, secrets, uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DB_URL = os.getenv("DATABASE_URL") or "sqlite:///./aftershock.db"
SECRET = os.getenv("SECRET_KEY") or secrets.token_hex(16)
MODE = "LLM MODE" if os.getenv("LLM_API_KEY") else "DEMO MODE"  # mirrors llm.get_provider()
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
Session_ = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()
now = lambda: datetime.now(timezone.utc)
uid = lambda: str(uuid.uuid4())

STATES = ["PROPOSED", "WAITING_APPROVAL", "APPROVED", "EXECUTING", "VERIFYING",
          "COMPLETED", "REJECTED", "FAILED", "MONITORING"]
ALLOWED = {"PROPOSED": {"WAITING_APPROVAL", "EXECUTING"}, "WAITING_APPROVAL": {"APPROVED", "REJECTED"},
           "APPROVED": {"EXECUTING"}, "EXECUTING": {"VERIFYING", "FAILED"},
           "VERIFYING": {"COMPLETED", "MONITORING", "FAILED"}, "FAILED": {"EXECUTING"},
           "COMPLETED": set(), "REJECTED": set(), "MONITORING": {"COMPLETED"}}

# ---------- database ----------
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=uid)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    approval_required = Column(Boolean, default=True)

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True, default=uid)
    code = Column(String, default=lambda: f"AS-{secrets.randbelow(90000) + 10000}")
    user_id = Column(String, ForeignKey("users.id"))
    incident_type = Column(String)
    description = Column(Text)
    severity = Column(String, default="medium")
    status = Column(String, default="CREATED")
    affected = Column(JSON, default=list)
    risks = Column(JSON, default=list)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

class Action(Base):
    __tablename__ = "recovery_actions"
    id = Column(String, primary_key=True, default=uid)
    incident_id = Column(String, ForeignKey("incidents.id"))
    title = Column(String)
    category = Column(String)
    agent = Column(String)
    tool = Column(String)
    requires_approval = Column(Boolean, default=False)
    why = Column(Text)
    shares = Column(String, default="")
    consequence = Column(String, default="")
    state = Column(String, default="PROPOSED")
    monitors_after = Column(Boolean, default=False)
    result = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now)

class Event(Base):  # activity log + audit log + tool trace in one append-only table
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=uid)
    incident_id = Column(String, ForeignKey("incidents.id"))
    kind = Column(String)  # audit | agent | tool
    actor = Column(String)
    message = Column(Text)
    at = Column(DateTime, default=now)

class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True, default=uid)
    user_id = Column(String, ForeignKey("users.id"))
    kind = Column(String)
    name = Column(String)
    details = Column(JSON, default=dict)

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=uid)
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String)
    doc_type = Column(String)
    extracted = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, default=uid)
    user_id = Column(String, ForeignKey("users.id"))
    incident_id = Column(String)
    level = Column(String, default="info")
    message = Column(Text)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)

class Pref(Base):
    __tablename__ = "prefs"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    data = Column(JSON, default=dict)

def log(db, inc_id, kind, actor, msg):
    db.add(Event(incident_id=inc_id, kind=kind, actor=actor, message=msg))

# ---------- tools (all mocks return structured, SIMULATED results) ----------
class BaseTool:
    name = "base"
    async def execute(self, **kw) -> dict:
        raise NotImplementedError
    def ok(self, msg, **data):
        return {"success": True, "simulated": True, "message": f"SIMULATED ACTION: {msg}", "data": data}

class MockDevice(BaseTool):
    name = "Mock Device Tool"
    async def execute(self, **kw): return self.ok("remote lock/wipe request prepared and simulated", device="primary")
class MockSIM(BaseTool):
    name = "Mock SIM Tool"
    async def execute(self, **kw): return self.ok("SIM block request simulated successfully")
class MockFinance(BaseTool):
    name = "Mock Finance Tool"
    async def execute(self, **kw): return self.ok("financial exposure review prepared", accounts_checked=3)
class MockPolice(BaseTool):
    name = "Mock Police Report Tool"
    async def execute(self, **kw): return self.ok("police report draft prepared (not submitted)")
class MockInsurance(BaseTool):
    name = "Mock Insurance Tool"
    async def execute(self, **kw): return self.ok("insurance claim package prepared (not submitted)")
class LocalResearch(BaseTool):
    name = "Web Search Tool"
    async def execute(self, **kw): return self.ok("local deterministic research (3 reference sources)", sources=3)
class Checklist(BaseTool):
    name = "Notification Tool"
    async def execute(self, **kw): return self.ok("checklist organised")
class FailingTool(BaseTool):
    name = "Failing Tool"
    async def execute(self, **kw): raise RuntimeError("tool unavailable")

TOOLS = {t.name: t for t in [MockDevice(), MockSIM(), MockFinance(), MockPolice(), MockInsurance(),
                             LocalResearch(), Checklist(), FailingTool()]}

# ---------- agents ----------
def classify(text: str) -> str:
    t = text.lower()
    rules = [("passport", "Passport lost"), ("stolen", "Phone stolen"), ("phone", "Phone stolen"),
             ("accident", "Car accident"), ("hacked", "Account compromised"), ("compromised", "Account compromised"),
             ("document", "Document lost"), ("flight", "Travel disruption"), ("travel", "Travel disruption")]
    return next((v for k, v in rules if k in t), "Other")

# (title, category, agent, tool, approval, why, shares, consequence, monitor_after)
PLANS = {
 "Phone stolen": [
  ("Secure device (remote lock)", "DEVICE", "Security Agent", "Mock Device Tool", False, "Prevents access to local data.", "", "", False),
  ("Secure primary email", "ACCOUNTS", "Security Agent", "Notification Tool", False, "Email controls account recovery.", "", "", False),
  ("Block your SIM card", "SIM", "Security Agent", "Mock SIM Tool", True, "The stolen device may still receive SMS verification codes.", "Phone number", "Your current SIM will stop working.", False),
  ("Review financial exposure", "FINANCE", "Finance Agent", "Mock Finance Tool", True, "Banking and payment apps may be reachable.", "Account names", "Cards may be frozen.", True),
  ("File police report", "IDENTITY", "Recovery Agent", "Mock Police Report Tool", True, "Needed for insurance and identity protection.", "Name, incident details", "Report becomes an official record.", False),
  ("Check insurance coverage", "INSURANCE", "Research Agent", "Mock Insurance Tool", True, "Device insurance may cover replacement.", "Policy number, invoice", "Claim is opened.", True),
  ("Research official recovery procedures", "DOCUMENTS", "Research Agent", "Web Search Tool", False, "Confirms provider requirements.", "", "", False),
  ("Monitor account activity", "ACCOUNTS", "Monitoring Agent", "Notification Tool", False, "Detects misuse after recovery.", "", "", True)],
 "Passport lost": [
  ("Research reissue procedure", "DOCUMENTS", "Research Agent", "Web Search Tool", False, "Procedures vary by country.", "", "", False),
  ("File police report", "IDENTITY", "Recovery Agent", "Mock Police Report Tool", True, "Required for reissue.", "Name, passport number", "Official record.", False),
  ("Submit emergency passport application", "DOCUMENTS", "Recovery Agent", "Mock Police Report Tool", True, "Starts replacement.", "Identity details", "Application filed.", False)],
 "Car accident": [
  ("Organise accident information", "DOCUMENTS", "Incident Agent", "Notification Tool", False, "Preserves evidence.", "", "", False),
  ("Submit insurance claim", "INSURANCE", "Research Agent", "Mock Insurance Tool", True, "Starts claim.", "Policy number, photos", "Claim opened.", True),
  ("File police report", "IDENTITY", "Recovery Agent", "Mock Police Report Tool", True, "Legal record.", "Statement", "Official record.", False)],
 "Account compromised": [
  ("Assess account exposure", "ACCOUNTS", "Security Agent", "Notification Tool", False, "Scopes the breach.", "", "", False),
  ("Reset credentials and sessions", "ACCOUNTS", "Security Agent", "Mock Device Tool", True, "Evicts the attacker.", "Account email", "You will be logged out everywhere.", True),
  ("Review financial exposure", "FINANCE", "Finance Agent", "Mock Finance Tool", True, "Check linked payments.", "Account names", "Cards may be frozen.", True)],
}
GENERIC = [("Organise incident information", "DOCUMENTS", "Incident Agent", "Notification Tool", False, "Creates a checklist.", "", "", False),
           ("Research recovery steps", "DOCUMENTS", "Research Agent", "Web Search Tool", False, "Finds official guidance.", "", "", False)]

def orchestrate(itype: str) -> list[str]:
    """Only run agents relevant to the incident."""
    agents = ["Incident Agent", "Research Agent", "Recovery Agent"]
    if itype in ("Phone stolen", "Account compromised"): agents += ["Security Agent", "Finance Agent"]
    if itype in ("Phone stolen", "Car accident", "Passport lost"): agents.append("Monitoring Agent")
    return agents

from pipeline import build
from llm import IncidentSummary, get_provider, heuristic_summary, structured
PROVIDER = get_provider()
PIPELINE = build(PLANS, GENERIC, orchestrate)

def move(db, a: Action, new: str, actor: str):
    if new not in ALLOWED[a.state]:
        raise HTTPException(409, f"Illegal transition {a.state} -> {new}")
    log(db, a.incident_id, "audit", actor, f"{a.title}: {a.state} -> {new}")
    a.state = new

async def run_action(db, a: Action):
    move(db, a, "EXECUTING", a.agent)
    try:
        r = await TOOLS[a.tool].execute(action=a.title)
        a.result = r
        log(db, a.incident_id, "tool", a.agent, f"-> {a.tool}: {r['message']}")
    except Exception as e:  # never crash the workflow
        a.result = {"success": False, "simulated": True, "message": str(e), "data": {}}
        move(db, a, "FAILED", a.agent); log(db, a.incident_id, "agent", a.agent, f"Tool failed: {e}")
        return
    move(db, a, "VERIFYING", a.agent)
    move(db, a, "MONITORING" if a.monitors_after else "COMPLETED", a.agent)

async def analyze(db, inc: Incident):
    log(db, inc.id, "audit", "system", "Incident created")
    inc.incident_type = classify(inc.description)
    inc.status = "ANALYZING"
    summ, fb, issues = await structured(
        PROVIDER, IncidentSummary, "Return ONLY JSON: severity(low|medium|high|critical), location, summary, key_risks[].",
        inc.description, lambda: heuristic_summary(inc.description))
    for m in issues: log(db, inc.id, "audit", "system", m)
    log(db, inc.id, "agent", "Incident Agent", f"Understood: {summ.summary}" + (f" (location: {summ.location})" if summ.location else ""))
    try:
        out = PIPELINE({"itype": inc.incident_type, "agents": [], "findings": [], "plan": []})
        plan, findings = out["plan"], out["findings"]
    except Exception as e:  # never crash: deterministic fallback
        log(db, inc.id, "audit", "system", f"Pipeline error, using fallback: {e}")
        plan, findings = PLANS.get(inc.incident_type, GENERIC), [("Recovery Agent", "Fallback plan used")]
    for ag, msg in findings: log(db, inc.id, "agent", ag, msg)
    inc.affected = sorted({p[1] for p in plan})
    inc.risks = [p[5] for p in plan if p[4]]
    inc.severity = "high" if sum(p[4] for p in plan) >= 3 else "medium"
    if not fb: inc.severity = summ.severity
    for t, cat, ag, tool, appr, why, sh, cons, mon in plan:
        db.add(Action(incident_id=inc.id, title=t, category=cat, agent=ag, tool=tool, requires_approval=appr,
                      why=why, shares=sh, consequence=cons, monitors_after=mon))
    db.flush()
    log(db, inc.id, "audit", "Recovery Agent", "Recovery plan generated")
    for a in db.query(Action).filter_by(incident_id=inc.id).all():
        if a.requires_approval:
            move(db, a, "WAITING_APPROVAL", "Recovery Agent")
            log(db, inc.id, "audit", "system", f"Approval requested: {a.title}")
            db.add(Notification(user_id=inc.user_id, incident_id=inc.id, level="warn", message=f"Action requires your approval: {a.title}"))
        else:
            await run_action(db, a)
    inc.status = "AWAITING_APPROVAL"
    refresh_status(db, inc)

def progress(db, incident_id: str) -> dict:
    acts = db.query(Action).filter_by(incident_id=incident_id).all()
    counted = [a for a in acts if a.state != "REJECTED"]
    done = [a for a in counted if a.state in ("COMPLETED", "MONITORING")]
    return {"total": len(acts), "addressed": len(done),
            "awaiting_approval": sum(a.state == "WAITING_APPROVAL" for a in acts),
            "completed": sum(a.state == "COMPLETED" for a in acts),
            "monitoring": sum(a.state == "MONITORING" for a in acts),
            "percent": round(100 * len(done) / len(counted)) if counted else 0}

def refresh_status(db, inc):
    p = progress(db, inc.id)
    pending = any(a.state in ("PROPOSED", "WAITING_APPROVAL", "FAILED") for a in db.query(Action).filter_by(incident_id=inc.id))
    inc.status = "AWAITING_APPROVAL" if pending else ("RESOLVED" if p["completed"] == p["addressed"] else "RECOVERY_IN_PROGRESS")

def replan(db, rejected: Action):
    alt = Action(incident_id=rejected.incident_id, title=f"Alternative: prepare manual instructions for '{rejected.title}'",
                 category=rejected.category, agent="Recovery Agent", tool="Notification Tool", why="You rejected the original action; "
                 "this prepares steps you can perform yourself.", requires_approval=False)
    db.add(alt); db.flush()
    log(db, rejected.incident_id, "agent", "Recovery Agent", f"Re-planned after rejection of '{rejected.title}'")
    return alt

# ---------- auth ----------
def hash_pw(pw: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
def check_pw(pw: str, stored: str) -> bool:
    return hmac.compare_digest(hash_pw(pw, stored.split("$")[0]), stored)
def make_token(user_id: str) -> str:
    return user_id + "." + hmac.new(SECRET.encode(), user_id.encode(), "sha256").hexdigest()

def get_db():
    db = Session_()
    try:
        yield db; db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()

def current_user(authorization: str = Header(default=""), token: str = "", db: Session = Depends(get_db)) -> User:
    uid_, _, sig = (authorization.removeprefix("Bearer ") or token).partition(".")
    if not hmac.compare_digest(sig, hmac.new(SECRET.encode(), uid_.encode(), "sha256").hexdigest()):
        raise HTTPException(401, "Invalid token")
    u = db.get(User, uid_)
    if not u: raise HTTPException(401, "Unknown user")
    return u

class Creds(BaseModel):
    email: str
    password: str
class IncidentIn(BaseModel):
    description: str
    location: str = ""
    occurred_at: str = ""
    people: str = ""

app = FastAPI(title="AFTERSHOCK")

def init_db():
    Base.metadata.create_all(engine)
    with Session_() as db:
        if not db.query(User).filter_by(email="demo@aftershock.local").first():
            pw = os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(9)
            db.add(User(email="demo@aftershock.local", password_hash=hash_pw(pw)))
            db.commit()
            if not os.getenv("DEMO_PASSWORD"): print(f"Demo login: demo@aftershock.local / {pw}")

@app.on_event("startup")
async def _startup():
    init_db()
    with Session_() as db:
        u = db.query(User).filter_by(email="demo@aftershock.local").first()
        if u and not db.query(Incident).filter_by(user_id=u.id).count():
            for text, auto in (("I lost my passport at the airport.", True), ("I was in a car accident this morning.", False), ("My phone was stolen yesterday while travelling. Worried about my accounts, banking apps and SIM.", "sim")):
                i = Incident(user_id=u.id, description=text); db.add(i); db.flush()
                await analyze(db, i)
                if auto is True:
                    for a in db.query(Action).filter_by(incident_id=i.id, state="WAITING_APPROVAL").all():
                        move(db, a, "APPROVED", "human"); await run_action(db, a)
                    refresh_status(db, i)
                elif auto == "sim":
                    for a in db.query(Action).filter_by(incident_id=i.id, title="Block your SIM card").all():
                        move(db, a, "APPROVED", "human"); await run_action(db, a)
                    refresh_status(db, i)
            db.commit()

@app.post("/auth/register", status_code=201)
def register(c: Creds, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=c.email).first(): raise HTTPException(409, "Email exists")
    u = User(email=c.email, password_hash=hash_pw(c.password)); db.add(u); db.flush()
    return {"token": make_token(u.id)}

@app.post("/auth/login")
def login(c: Creds, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=c.email).first()
    if not u or not check_pw(c.password, u.password_hash): raise HTTPException(401, "Bad credentials")
    return {"token": make_token(u.id), "mode": MODE}

def ser(db, i: Incident):
    return {"id": i.id, "code": i.code, "type": i.incident_type, "severity": i.severity, "status": i.status,
            "affected": i.affected, "risks": i.risks, "progress": progress(db, i.id), "created_at": i.created_at}

def own(db, user, iid) -> Incident:
    i = db.get(Incident, iid)
    if not i or i.user_id != user.id: raise HTTPException(404, "Incident not found")
    return i

@app.get("/me")
def me(u: User = Depends(current_user)):
    return {"email": u.email, "mode": MODE}

@app.get("/incidents")
def list_incidents(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [ser(db, i) for i in db.query(Incident).filter_by(user_id=u.id).order_by(Incident.created_at.desc())]

@app.post("/incidents", status_code=201)
def create_incident(b: IncidentIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not b.description.strip(): raise HTTPException(422, "Description required")
    extra = "".join(f"\n[{k}: {v.strip()[:120]}]" for k, v in (("Location", b.location), ("When", b.occurred_at), ("People", b.people)) if v.strip())
    full = b.description[:5000] + extra
    i = Incident(user_id=u.id, description=full, incident_type=classify(b.description)); db.add(i); db.flush()
    return ser(db, i)

@app.get("/incidents/{iid}")
def get_incident(iid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return ser(db, own(db, u, iid))

@app.post("/incidents/{iid}/analyze")
async def analyze_ep(iid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    i = own(db, u, iid)
    if i.status != "CREATED": raise HTTPException(409, "Already analyzed")
    await analyze(db, i)
    return ser(db, i)

def act_dict(a): return {c.name: getattr(a, c.name) for c in a.__table__.columns}

@app.get("/incidents/{iid}/actions")
def actions(iid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    own(db, u, iid)
    return [act_dict(a) for a in db.query(Action).filter_by(incident_id=iid).order_by(Action.created_at)]

@app.get("/incidents/{iid}/activity")
def activity(iid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    own(db, u, iid)
    return [{"at": e.at, "kind": e.kind, "actor": e.actor, "message": e.message}
            for e in db.query(Event).filter_by(incident_id=iid).order_by(Event.at)]

def own_action(db, user, aid) -> Action:
    a = db.get(Action, aid)
    if not a: raise HTTPException(404, "Action not found")
    own(db, user, a.incident_id)
    return a

@app.post("/actions/{aid}/approve")
async def approve(aid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = own_action(db, u, aid)
    if a.state != "WAITING_APPROVAL": raise HTTPException(409, f"Action is {a.state}")
    move(db, a, "APPROVED", "human"); await run_action(db, a)
    refresh_status(db, db.get(Incident, a.incident_id))
    return act_dict(a)

@app.post("/actions/{aid}/reject")
async def reject(aid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = own_action(db, u, aid)
    if a.state != "WAITING_APPROVAL": raise HTTPException(409, f"Action is {a.state}")
    move(db, a, "REJECTED", "human"); alt = replan(db, a); await run_action(db, alt)
    refresh_status(db, db.get(Incident, a.incident_id))
    return {"rejected": act_dict(a), "alternative": {"id": alt.id, "title": alt.title}}


# ---------- assets, documents, notifications, settings ----------
KINDS = {"Device", "Vehicle", "Document", "Insurance", "Financial Account"}
class AssetIn(BaseModel):
    kind: str
    name: str
    details: dict = {}

@app.get("/assets")
def assets(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": a.id, "kind": a.kind, "name": a.name, "details": a.details} for a in db.query(Asset).filter_by(user_id=u.id)]

@app.post("/assets", status_code=201)
def add_asset(b: AssetIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if b.kind not in KINDS or not b.name.strip(): raise HTTPException(422, f"kind must be one of {sorted(KINDS)}")
    a = Asset(user_id=u.id, kind=b.kind, name=b.name, details=b.details); db.add(a); db.flush()
    return {"id": a.id, "kind": a.kind, "name": a.name, "details": a.details}

import re
from fastapi import File, UploadFile
EXT = {"pdf", "png", "jpg", "jpeg", "txt"}

def _text(name: str, raw: bytes) -> tuple[str, str]:
    """Best-effort text extraction. Optional libs (PyMuPDF, Pillow, pytesseract) degrade gracefully."""
    n = name.lower()
    try:
        if n.endswith(".txt"): return raw.decode("utf-8", "ignore"), ""
        if n.endswith(".pdf"):
            import fitz
            with fitz.open(stream=raw, filetype="pdf") as d: return "\n".join(p.get_text() for p in d), ""
        import io
        from PIL import Image
        import pytesseract
        return pytesseract.image_to_string(Image.open(io.BytesIO(raw))), ""
    except Exception as e:
        return "", f"Stored; text extraction unavailable ({type(e).__name__})"

def extract(name: str, raw: bytes) -> dict:
    out = {"document_type": "Unknown"}
    t, note = _text(name, raw)
    if note: out["note"] = note
    if m := re.search(r"policy\s*(?:no|number)?[:#\s]+([A-Z0-9-]{5,})", t, re.I):
        out.update(document_type="Insurance policy", policy_number="****" + m.group(1)[-3:])  # masked
    if m := re.search(r"provider[:\s]+(.+)", t, re.I): out["provider"] = m.group(1).strip()[:60]
    if m := re.search(r"(iphone|pixel|galaxy)[\w ]{0,12}", t, re.I): out["device_model"] = m.group(0).strip()
    return out

@app.get("/documents")
def documents(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": d.id, "name": d.name, "type": d.doc_type, "extracted": d.extracted, "created_at": d.created_at}
            for d in db.query(Document).filter_by(user_id=u.id)]

@app.post("/documents", status_code=201)
async def upload_doc(file: UploadFile = File(...), u: User = Depends(current_user), db: Session = Depends(get_db)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in EXT: raise HTTPException(415, f"Unsupported file type; allowed: {sorted(EXT)}")
    raw = await file.read()
    if len(raw) > 5_000_000: raise HTTPException(413, "File too large")
    ex = extract(file.filename, raw)
    d = Document(user_id=u.id, name=file.filename, doc_type=ex["document_type"], extracted=ex); db.add(d); db.flush()
    return {"id": d.id, "name": d.name, "type": d.doc_type, "extracted": ex}

@app.get("/notifications")
def notifications(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": n.id, "level": n.level, "message": n.message, "read": n.read, "incident_id": n.incident_id}
            for n in db.query(Notification).filter_by(user_id=u.id).order_by(Notification.created_at.desc())]

@app.post("/notifications/{nid}/read")
def read_notification(nid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.user_id != u.id: raise HTTPException(404, "Not found")
    n.read = True
    return {"id": n.id, "read": True}

DEFAULT_RULES = {k: True for k in ("human_approval_required", "financial", "account_changes", "external_comms", "document_submissions", "bookings")}

@app.get("/settings")
def get_settings(u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Pref, u.id)
    return {"mode": MODE, "approval_rules": {**DEFAULT_RULES, **(p.data if p else {})}}

@app.put("/settings")
def put_settings(rules: dict, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if any(k not in DEFAULT_RULES or not isinstance(v, bool) for k, v in rules.items()): raise HTTPException(422, "Unknown rule")
    if rules.get("human_approval_required") is False: raise HTTPException(422, "Human approval cannot be disabled")
    p = db.get(Pref, u.id) or Pref(user_id=u.id, data={}); db.add(p)
    p.data = {**p.data, **rules}
    return {"mode": MODE, "approval_rules": {**DEFAULT_RULES, **p.data}}

# ---------- graph, impact, agents, monitoring ----------
def _state(acts):
    st = {a.state for a in acts}
    for k in ("FAILED", "REJECTED", "WAITING_APPROVAL", "PROPOSED", "MONITORING"):
        if k in st: return k
    return "COMPLETED"

@app.get("/incidents/{iid}/graph")
def graph(iid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    i = own(db, u, iid)
    by = {}
    for a in db.query(Action).filter_by(incident_id=iid).order_by(Action.created_at): by.setdefault(a.category, []).append(a)
    nodes = []
    for cat, acts in by.items():
        done = [a for a in acts if a.state in ("COMPLETED", "MONITORING")]
        nodes.append({"id": cat, "label": cat, "state": _state(acts), "percent": round(100 * len(done) / len(acts)),
                      "actions": [{"title": a.title, "state": a.state, "why": a.why, "agent": a.agent} for a in acts]})
    return {"center": i.incident_type, "nodes": nodes}

@app.get("/incidents/{iid}/agents")
def agents_ep(iid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    own(db, u, iid)
    acts = db.query(Action).filter_by(incident_id=iid).all()
    out = {}
    for e in db.query(Event).filter_by(incident_id=iid, kind="agent").order_by(Event.at):
        out[e.actor] = {"agent": e.actor, "task": e.message, "at": e.at}
    for name, r in out.items():
        mine = [a for a in acts if a.agent == name]
        r["status"] = ("Needs approval" if any(a.state == "WAITING_APPROVAL" for a in mine) else
                       "Failed" if any(a.state == "FAILED" for a in mine) else
                       "Waiting" if any(a.state == "PROPOSED" for a in mine) else "Completed")
        r["tools_used"] = sorted({a.tool for a in mine if a.state != "PROPOSED"})
    return list(out.values())

@app.post("/incidents/{iid}/monitor")
def monitor(iid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    own(db, u, iid)
    mon = db.query(Action).filter_by(incident_id=iid, state="MONITORING").all()
    for a in mon: log(db, iid, "agent", "Monitoring Agent", f"Checked '{a.title}': no new risk (simulated check)")
    if not mon: log(db, iid, "agent", "Monitoring Agent", "Nothing to monitor yet")
    return {"checked": len(mon)}

import asyncio, json
from fastapi.responses import StreamingResponse

@app.get("/incidents/{iid}/stream")
async def stream(iid: str, max_seconds: int = 300, u: User = Depends(current_user), db: Session = Depends(get_db)):
    own(db, u, iid)
    async def gen():
        seen, waited = -1, 0
        while waited <= max_seconds:
            with Session_() as d:
                n = d.query(Event).filter_by(incident_id=iid).count()
                last = d.query(Event).filter_by(incident_id=iid).order_by(Event.at.desc()).first()
            if n != seen:
                seen = n
                yield f"data: {json.dumps({'events': n, 'latest': last.message if last else ''})}\n\n"
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(1); waited += 1
    return StreamingResponse(gen(), media_type="text/event-stream")

# ---------- frontend (served last so API routes win) ----------
from fastapi.staticfiles import StaticFiles
_static = os.path.join(os.path.dirname(__file__), "static")
_react = os.path.join(os.path.dirname(__file__), "static_react")
if os.path.isdir(_react):  # React/Vite build, served at /app
    app.mount("/app", StaticFiles(directory=_react, html=True), name="react")
if os.path.isdir(_static):
    app.mount("/", StaticFiles(directory=_static, html=True), name="ui")

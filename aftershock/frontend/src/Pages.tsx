import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, label } from "./api";

const card = "bg-c1 border border-bd rounded-xl p-4 mb-3";
const inp = "bg-bg2 border border-bd rounded-lg p-2.5";
const btn = "bg-amber text-[#1a1100] font-bold rounded-lg px-4 py-2";
const H = ({ t, s }: { t: string; s: string }) => (<><h1 className="text-3xl font-extrabold">{t}</h1><p className="text-t2 mb-6">{s}</p></>);

export function Landing({ onStart }: { onStart: () => void }) {
  const nodes = ["DEVICE", "IDENTITY", "FINANCE", "DOCUMENTS", "INSURANCE", "RECOVERY"];
  const stages = [["01 UNDERSTAND", "The agent interprets what happened."], ["02 MAP IMPACT", "It identifies affected accounts, assets, documents, services and people."],
    ["03 PLAN RECOVERY", "Specialized agents research and build a step-by-step recovery plan."], ["04 KEEP YOU IN CONTROL", "Consequential actions always require human approval."]];
  return (
    <div>
      <header className="flex items-center gap-6 px-6 py-4 border-b border-bd bg-bg2">
        <b className="tracking-[.14em]">AFTERSHOCK</b>
        <nav className="flex gap-4 text-t2 flex-1 max-sm:hidden"><a href="#product">Product</a><a href="#how">How it works</a><a href="#how">Security</a><a href="#how">About</a></nav>
        <button onClick={onStart} className="text-t2">Sign in</button><button onClick={onStart} className={btn}>Start an Incident</button>
      </header>
      <section id="product" className="max-w-[1180px] mx-auto px-6 py-16 grid md:grid-cols-2 gap-10 items-center">
        <div>
          <h1 className="text-5xl font-extrabold leading-tight">When something goes wrong, know what happens next.</h1>
          <p className="text-t2 my-6">AFTERSHOCK uses AI agents to understand real-world incidents, identify what is affected, coordinate recovery tasks, and keep you in control.</p>
          <button onClick={onStart} className={btn}>Start an Incident →</button>
          <a href="#how" className="ml-3 border border-bd rounded-lg px-4 py-2 inline-block">See How It Works</a>
        </div>
        <svg viewBox="0 0 400 320" role="img" aria-label="Incident network">
          {nodes.map((n, k) => { const a = (2 * Math.PI * k) / 6 - Math.PI / 2, x = 200 + 140 * Math.cos(a), y = 160 + 110 * Math.sin(a);
            return (<motion.g key={n} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: k * 0.12 }}>
              <line x1="200" y1="160" x2={x} y2={y} stroke="#28313C" /><circle r="3" fill="#FF9F43"><animateMotion dur={`${2.5 + k * 0.4}s`} repeatCount="indefinite" path={`M200,160 L${x},${y}`} /></circle>
              <circle cx={x} cy={y} r="6" fill="#151A22" stroke="#929CAA" /><text x={x} y={y + 22} fill="#929CAA" fontSize="9" textAnchor="middle">{n}</text></motion.g>); })}
          <circle cx="200" cy="160" r="26" fill="#FF9F43" /><text x="200" y="163" fontSize="8" fontWeight="800" textAnchor="middle" fill="#1a1100">INCIDENT</text>
        </svg>
      </section>
      <section id="how" className="max-w-[1180px] mx-auto px-6 pb-20">
        <h2 className="text-3xl font-extrabold mb-8">From incident to recovery.</h2>
        <div className="grid md:grid-cols-4 gap-6 relative">
          <motion.div className="absolute top-2 left-0 h-px bg-amber max-md:hidden" initial={{ width: 0 }} whileInView={{ width: "100%" }} transition={{ duration: 1.2 }} viewport={{ once: true }} />
          {stages.map(([t, d]) => (<div key={t} className="pt-6"><b className="font-mono text-sm text-amber">{t}</b><p className="text-t2 mt-1">{d}</p></div>))}
        </div>
      </section>
    </div>
  );
}

export function Assets() {
  const [l, setL] = useState<any[]>([]), [kind, setKind] = useState("Device"), [name, setName] = useState(""), [err, setErr] = useState("");
  const load = () => api("/assets").then(setL);
  useEffect(() => { load(); }, []);
  const add = async () => { try { await api("/assets", { method: "POST", json: { kind, name } }); setName(""); setErr(""); load(); } catch (e: any) { setErr(e.message); } };
  return (<div><H t="Assets" s="Agents use these during incident analysis." />
    <div className={card + " flex gap-2 flex-wrap"}><select aria-label="Kind" className={inp} value={kind} onChange={(e) => setKind(e.target.value)}>{["Device", "Vehicle", "Document", "Insurance", "Financial Account"].map((k) => <option key={k}>{k}</option>)}</select>
      <input aria-label="Asset name" className={inp + " flex-1"} placeholder="e.g. MacBook Pro" value={name} onChange={(e) => setName(e.target.value)} /><button className={btn} onClick={add}>Add</button><p className="text-crit w-full">{err}</p></div>
    {l.length ? l.map((a) => <div key={a.id} className={card}><span className="text-xs border border-bd rounded-full px-2 mr-2 text-t2">{a.kind}</span><b>{a.name}</b></div>) : <div className={card}>No assets yet.</div>}</div>);
}

export function Documents() {
  const [l, setL] = useState<any[]>([]), [err, setErr] = useState(""), [open, setOpen] = useState<any>(null);
  const load = () => api("/documents").then(setL);
  useEffect(() => { load(); }, []);
  const up = async (f?: File) => {
    if (!f) return; const fd = new FormData(); fd.append("file", f);
    const r = await fetch("/documents", { method: "POST", headers: { Authorization: "Bearer " + localStorage.getItem("token") }, body: fd });
    const d = await r.json().catch(() => ({})); setErr(r.ok ? "" : d.detail || "Upload failed"); load();
  };
  return (<div><H t="Documents" s="Add documents so AFTERSHOCK can help when you need it. PDF, PNG, JPG, TXT." />
    <div className={card}><input type="file" aria-label="Upload document" onChange={(e) => up(e.target.files?.[0])} /><p className="text-crit">{err}</p></div>
    {l.length ? l.map((d) => (<div key={d.id} className={card + " cursor-pointer hover:border-amber"} tabIndex={0} role="button" onClick={() => setOpen(d)} onKeyDown={(e) => e.key === "Enter" && setOpen(d)}><b>{d.name}</b> <span className="text-xs border border-bd rounded-full px-2 text-t2">AI Indexed</span>
      <div className="font-mono text-xs text-t2">{d.type} {Object.entries(d.extracted).filter(([k]) => k !== "document_type").map(([k, v]) => `· ${k}: ${v}`).join(" ")}</div></div>)) : <div className={card}>Your recovery context starts here.</div>}
    {open && (<motion.aside initial={{ x: 320 }} animate={{ x: 0 }} role="dialog" aria-label="Document details" className="fixed right-0 top-0 h-full w-80 bg-c2 border-l border-bd p-5 overflow-auto">
      <button className="float-right text-t2" onClick={() => setOpen(null)} aria-label="Close">✕</button><h2 className="font-bold mb-1">{open.name}</h2>
      <span className="text-xs border border-bd rounded-full px-2 text-t2">AI Indexed</span>
      <dl className="mt-4 font-mono text-xs space-y-2"><div><dt className="text-t3">TYPE</dt><dd>{open.type}</dd></div>{Object.entries(open.extracted).map(([k, v]) => (<div key={k}><dt className="text-t3">{k.toUpperCase()}</dt><dd>{String(v)}</dd></div>))}</dl>
      <p className="text-t3 text-xs mt-4">Sensitive values are masked.</p></motion.aside>)}</div>);
}

export function Settings() {
  const [s, setS] = useState<any>(null), [err, setErr] = useState(""), [me, setMe] = useState<any>({});
  useEffect(() => { api("/settings").then(setS); api("/me").then(setMe); }, []);
  if (!s) return null;
  const set = async (k: string, v: boolean) => { try { setS(await api("/settings", { method: "PUT", json: { [k]: v } })); setErr(""); } catch (e: any) { setErr(e.message); } };
  return (<div><H t="Settings" s={`AI CONTROL · ${s.mode}`} />
    <div className={card}>{Object.entries(s.approval_rules).map(([k, v]) => (
      <label key={k} className="flex justify-between py-1.5"><span>{label(k)[0].toUpperCase() + label(k).slice(1)}</span><input type="checkbox" checked={v as boolean} onChange={(e) => set(k, e.target.checked)} /></label>))}
      <p className="text-t2 mt-2">AFTERSHOCK will never perform consequential actions without your approval.</p><p className="text-crit">{err}</p></div>
    {[["Profile", `Signed in as ${me.email ?? "…"}`], ["Security", "Passwords are hashed; sessions use signed tokens."], ["Connected Accounts", "None connected. All external actions are simulated."],
      ["Notification Preferences", "In-app notifications are on for approvals and risks."], ["AI Permissions", "Agents can organise, research and draft. Consequential actions need approval."], ["Privacy", "Sensitive document values are masked in the UI."]]
      .map(([t, d]) => <div key={t} className={card}><h2 className="text-xs tracking-widest text-t2">{t.toUpperCase()}</h2><p>{d}</p></div>)}</div>);
}

export function Notifications() {
  const [l, setL] = useState<any[]>([]);
  const load = () => api("/notifications").then(setL);
  useEffect(() => { load(); }, []);
  return (<div><H t="Notifications" s="Persisted alerts from your incidents." />
    {l.length ? l.map((n) => (<div key={n.id} className={card + " flex items-center gap-3"} style={{ borderColor: n.level === "warn" ? "#FF9F43" : undefined, opacity: n.read ? 0.55 : 1 }}>
      <span className="flex-1">{n.message}</span>{!n.read && <button className="border border-bd rounded-lg px-3 py-1" onClick={() => api(`/notifications/${n.id}/read`, { method: "POST" }).then(load)}>Dismiss</button>}</div>)) : <div className={card}>No notifications.</div>}</div>);
}

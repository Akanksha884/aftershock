import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "./api";
import Detail from "./Detail";
import { Assets, Documents, Landing, Notifications, Settings } from "./Pages";

function Login({ onAuth }: { onAuth: () => void }) {
  const [email, setEmail] = useState("demo@aftershock.local"), [pw, setPw] = useState(""), [err, setErr] = useState("");
  const go = (p: string) => async () => {
    try { const d = await api(p, { method: "POST", json: { email, password: pw } }); localStorage.setItem("token", d.token); onAuth(); }
    catch (e: any) { setErr(e.message); }
  };
  const cls = "w-full bg-bg2 border border-bd rounded-lg p-2.5 mb-2.5";
  return (
    <main className="max-w-md mx-auto mt-[10vh] px-6">
      <div className="font-extrabold tracking-[.14em]">AFTERSHOCK</div>
      <h1 className="text-3xl font-extrabold mt-6">When something goes wrong,<br />know what happens next.</h1>
      <p className="text-t2 mb-6">Sign in to continue.</p>
      <input className={cls} aria-label="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input className={cls} aria-label="Password" type="password" placeholder="Password" value={pw} onChange={(e) => setPw(e.target.value)} />
      <div className="flex gap-2"><button onClick={go("/auth/login")} className="bg-amber text-[#1a1100] font-bold rounded-lg px-4 py-2">Sign in</button>
        <button onClick={go("/auth/register")} className="border border-bd rounded-lg px-4 py-2">Sign up</button></div>
      <p className="text-crit mt-2">{err}</p>
    </main>
  );
}

function NewIncident({ onDone }: { onDone: (id: string) => void }) {
  const [text, setText] = useState(""), [loc, setLoc] = useState(""), [when, setWhen] = useState(""), [people, setPeople] = useState(""), [files, setFiles] = useState<File[]>([]), [step, setStep] = useState(-1), [err, setErr] = useState("");
  const steps = ["Understanding the event", "Identifying affected areas", "Checking risks", "Researching required actions", "Building recovery plan"];
  const run = async () => {
    if (!text.trim()) return setErr("Please describe what happened.");
    setStep(0); const t = setInterval(() => setStep((s) => Math.min(s + 1, 4)), 500);
    try { const c = await api("/incidents", { method: "POST", json: { description: text, location: loc, occurred_at: when, people } });
      for (const f of files) { const fd = new FormData(); fd.append("file", f); await fetch("/documents", { method: "POST", headers: { Authorization: "Bearer " + localStorage.getItem("token") }, body: fd }); } await api(`/incidents/${c.id}/analyze`, { method: "POST" }); clearInterval(t); onDone(c.id); }
    catch (e: any) { clearInterval(t); setStep(-1); setErr(e.message); }
  };
  return (
    <div>
      <h1 className="text-3xl font-extrabold">What happened?</h1>
      <p className="text-t2 mb-4">Tell AFTERSHOCK what happened in your own words.</p>
      <textarea aria-label="Incident description" className="w-full min-h-[140px] bg-bg2 border border-bd rounded-lg p-3 mb-3" placeholder="My phone was stolen yesterday..." value={text} onChange={(e) => setText(e.target.value)} />
      <div className="flex gap-2 flex-wrap mb-3 text-sm">
        {["Photo", "Document"].map((k) => (<label key={k} className="border border-bd rounded-lg px-3 py-1.5 cursor-pointer">+ {k}<input type="file" className="sr-only" accept={k === "Photo" ? "image/*" : ".pdf,.txt,image/*"} onChange={(e) => e.target.files?.[0] && setFiles((f) => [...f, e.target.files![0]])} /></label>))}
        <button className="border border-bd rounded-lg px-3 py-1.5" onClick={() => navigator.geolocation?.getCurrentPosition((p) => setLoc(`${p.coords.latitude.toFixed(3)}, ${p.coords.longitude.toFixed(3)}`), () => setErr("Location permission denied"))}>+ Location</button>
        <button className="border border-bd rounded-lg px-3 py-1.5" onClick={() => { const R = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition; if (!R) return setErr("Voice input is not supported in this browser"); const r = new R(); r.onresult = (e: any) => setText((t) => t + " " + e.results[0][0].transcript); r.start(); }}>🎙 Voice</button>
        {files.length > 0 && <span className="text-t2 self-center">{files.length} file(s) attached</span>}
      </div>
      <div className="grid sm:grid-cols-3 gap-2 mb-3">
        <input aria-label="Location" className="bg-bg2 border border-bd rounded-lg p-2" placeholder="Location" value={loc} onChange={(e) => setLoc(e.target.value)} />
        <input aria-label="Date and time" className="bg-bg2 border border-bd rounded-lg p-2" placeholder="Date/time" value={when} onChange={(e) => setWhen(e.target.value)} />
        <input aria-label="People involved" className="bg-bg2 border border-bd rounded-lg p-2" placeholder="People involved" value={people} onChange={(e) => setPeople(e.target.value)} />
      </div>
      <button disabled={step >= 0} onClick={run} className="bg-amber text-[#1a1100] font-bold rounded-lg px-4 py-2 disabled:opacity-50">Analyze Incident →</button>
      {step >= 0 && <div className="font-mono text-sm text-t2 mt-4">{steps.map((s, k) => <motion.div key={s} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{k < step ? "✓" : k === step ? "●" : "○"} {s}</motion.div>)}</div>}
      <p className="text-crit mt-2">{err}</p>
    </div>
  );
}

function List({ onOpen }: { onOpen: (id: string) => void }) {
  const [l, setL] = useState<any[] | null>(null);
  useEffect(() => { api("/incidents").then(setL); }, []);
  if (!l) return <p className="text-t2">Loading…</p>;
  return (
    <div>
      <h1 className="text-3xl font-extrabold">Here's what needs your attention.</h1>
      <p className="text-t2 mb-6">Everything below comes from the live backend.</p>
      {l.length === 0 && <div className="bg-c1 border border-bd rounded-xl p-4">Nothing has gone wrong. That's exactly how we like it.</div>}
      {l.map((i) => (
        <motion.button whileHover={{ y: -2 }} key={i.id} onClick={() => onOpen(i.id)} className="block w-full text-left bg-c1 border border-bd hover:border-amber rounded-xl p-4 mb-3">
          <div className="flex gap-3 items-center flex-wrap"><b>{i.type.toUpperCase()}</b><span className="font-mono text-xs text-t3">#{i.code}</span>
            <span className="text-xs border border-bd rounded-full px-2 text-t2">{i.status.replaceAll("_", " ")}</span><span className="ml-auto font-mono text-sm">{i.progress.percent}%</span></div>
          <div className="h-1 bg-bd rounded mt-3 overflow-hidden"><motion.div className="h-full bg-amber" initial={{ width: 0 }} animate={{ width: `${i.progress.percent}%` }} /></div>
        </motion.button>
      ))}
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(!!localStorage.getItem("token"));
  const [view, setView] = useState<{ k: "list" | "new" | "detail" | "assets" | "docs" | "settings" | "notes"; id?: string }>({ k: "list" });
  const [login, setLogin] = useState(false);
  if (!authed) return login ? <Login onAuth={() => setAuthed(true)} /> : <Landing onStart={() => setLogin(true)} />;
  return (
    <>
      <header className="flex items-center gap-5 px-6 py-3.5 border-b border-bd bg-bg2">
        <div className="font-extrabold tracking-[.14em]">AFTERSHOCK</div>
        <nav className="flex gap-1 flex-1">
          <button onClick={() => setView({ k: "list" })} className="px-3 py-1.5 rounded-lg text-t2 hover:bg-c1">Dashboard</button>
          <button onClick={() => setView({ k: "new" })} className="px-3 py-1.5 rounded-lg text-t2 hover:bg-c1">New incident</button>
          {([["assets", "Assets"], ["docs", "Documents"], ["settings", "Settings"], ["notes", "🔔 Notifications"]] as const).map(([k, t]) => (
            <button key={k} onClick={() => setView({ k })} className="px-3 py-1.5 rounded-lg text-t2 hover:bg-c1">{t}</button>))}
        </nav>
        <button className="border border-bd rounded-lg px-3 py-1.5" onClick={() => { localStorage.clear(); setAuthed(false); }}>Log out</button>
      </header>
      <main className="max-w-[1180px] mx-auto px-6 py-7">
        {view.k === "list" && <List onOpen={(id) => setView({ k: "detail", id })} />}
        {view.k === "new" && <NewIncident onDone={(id) => setView({ k: "detail", id })} />}
        {view.k === "assets" && <Assets />}{view.k === "docs" && <Documents />}{view.k === "settings" && <Settings />}{view.k === "notes" && <Notifications />}
        {view.k === "detail" && <Detail id={view.id!} onBack={() => setView({ k: "list" })} />}
      </main>
    </>
  );
}

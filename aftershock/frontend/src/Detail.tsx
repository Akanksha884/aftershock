import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Background, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api, COLOR, label } from "./api";

const Tag = ({ s }: { s: string }) => (
  <span className="font-mono text-[11px] px-2 py-0.5 rounded-full border" style={{ color: COLOR[s], borderColor: COLOR[s] }}>{label(s)}</span>
);

function Ring({ p }: { p: any }) {
  const c = 2 * Math.PI * 54;
  return (
    <svg width="140" height="140" role="img" aria-label={`Recovery progress ${p.percent}%`}>
      <circle cx="70" cy="70" r="54" stroke="#28313C" strokeWidth="8" fill="none" />
      <motion.circle cx="70" cy="70" r="54" stroke="#FF9F43" strokeWidth="8" fill="none" strokeLinecap="round" strokeDasharray={c}
        initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - p.percent / 100) }} transition={{ duration: 0.9 }} transform="rotate(-90 70 70)" />
      <text x="70" y="68" fill="#F2F4F7" fontSize="28" fontWeight="800" textAnchor="middle">{p.percent}%</text>
      <text x="70" y="88" fill="#929CAA" fontSize="10" textAnchor="middle">{p.addressed} of {p.total} addressed</text>
    </svg>
  );
}

function Graph({ g, sel, onSel }: { g: any; sel: string | null; onSel: (id: string) => void }) {
  const [hover, setHover] = useState<string | null>(null);
  const n = g.nodes.length, node = g.nodes.find((x: any) => x.id === sel);
  const nodes: Node[] = [
    { id: "center", position: { x: 220, y: 135 }, data: { label: g.center.toUpperCase() }, draggable: false, selectable: false,
      style: { background: "#FF9F43", color: "#1a1100", fontWeight: 800, fontSize: 10, borderRadius: 999, width: 90, height: 90, display: "flex", alignItems: "center", justifyContent: "center", border: "none", textAlign: "center" } },
    ...g.nodes.map((x: any, k: number): Node => {
      const a = (2 * Math.PI * k) / n - Math.PI / 2;
      return { id: x.id, position: { x: 240 + 230 * Math.cos(a) - 45, y: 150 + 125 * Math.sin(a) - 15 }, draggable: false, ariaLabel: `${x.label}: ${label(x.state)}`,
        data: { label: x.label }, style: { background: "#151A22", color: "#F2F4F7", fontSize: 11, border: `2px solid ${COLOR[x.state]}`, borderRadius: 10, width: 100, padding: 6, boxShadow: sel === x.id ? `0 0 0 3px ${COLOR[x.state]}55` : "none" } };
    }),
  ];
  const edges: Edge[] = g.nodes.map((x: any): Edge => ({ id: `e-${x.id}`, source: "center", target: x.id, animated: true,
    style: { stroke: COLOR[x.state], strokeWidth: hover === x.id ? 3 : 1.3, opacity: hover && hover !== x.id ? 0.2 : 0.8 } }));
  return (
    <div className="bg-c1 border border-bd rounded-xl p-4">
      <h2 className="text-xs tracking-widest text-t2 mb-2">INCIDENT GRAPH</h2>
      <div className="h-[340px] max-sm:hidden" role="group" aria-label="Incident graph">
        <ReactFlow nodes={nodes} edges={edges} fitView nodesConnectable={false} zoomOnScroll={false} panOnDrag={false} zoomOnDoubleClick={false} proOptions={{ hideAttribution: true }}
          onNodeClick={(_, nd) => nd.id !== "center" && onSel(nd.id)} onNodeMouseEnter={(_, nd) => setHover(nd.id)} onNodeMouseLeave={() => setHover(null)}>
          <Background color="#28313C" gap={24} />
        </ReactFlow>
      </div>
      <div className="sm:hidden space-y-2 border-l border-bd pl-3">
        {g.nodes.map((x: any) => (
          <button key={x.id} onClick={() => onSel(x.id)} className="block w-full text-left bg-c2 rounded px-3 py-2 border-l-4" style={{ borderColor: COLOR[x.state] }}>
            {x.label} · {label(x.state)}
          </button>
        ))}
      </div>
      {node ? (
        <div className="border-t border-bd mt-3 pt-3 space-y-2">
          <b>{node.label}</b> <Tag s={node.state} />
          {node.actions.map((a: any) => (
            <p key={a.title} className="text-sm"><b>{a.title}</b> <Tag s={a.state} /><br /><span className="text-t2">{a.why} ({a.agent})</span></p>
          ))}
        </div>
      ) : <p className="text-t2 text-sm mt-2">Select a node for details.</p>}
    </div>
  );
}

export default function Detail({ id, onBack }: { id: string; onBack: () => void }) {
  const [d, setD] = useState<any>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const load = useCallback(async () => {
    const [i, actions, log, graph, agents] = await Promise.all([api(`/incidents/${id}`), api(`/incidents/${id}/actions`), api(`/incidents/${id}/activity`), api(`/incidents/${id}/graph`), api(`/incidents/${id}/agents`)]);
    setD({ i, actions, log, graph, agents });
  }, [id]);
  useEffect(() => {
    load().catch(() => {});
    const es = new EventSource(`/incidents/${id}/stream?token=${localStorage.getItem("token")}`);
    es.onmessage = () => load().catch(() => {});
    return () => es.close();
  }, [id, load]);
  const act = async (aid: string, verb: "approve" | "reject") => {
    try {
      const r = await api(`/actions/${aid}/${verb}`, { method: "POST" });
      setToast(verb === "approve" ? "✓ COMPLETED (simulated)" : `Rejected — ${r.alternative.title}`);
    } catch (e: any) { setToast(e.message); }
    setTimeout(() => setToast(""), 3500); load();
  };
  if (!d) return <p className="text-t2">Loading…</p>;
  const pend = d.actions.filter((a: any) => a.state === "WAITING_APPROVAL");
  return (
    <div>
      <button onClick={onBack} className="border border-bd rounded-lg px-3 py-1.5 mb-4">← Incidents</button>
      {d.i.status === "RESOLVED" && (
        <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} className="border border-ok rounded-xl p-4 mb-4 bg-c1">
          <b className="text-ok">✓ Incident Resolved</b> — your recovery plan is complete. Recovery completed · 100%
          <ul className="text-sm text-t2 mt-1">{d.actions.filter((a: any) => a.state !== "REJECTED").map((a: any) => <li key={a.id}>✓ {a.title}</li>)}</ul>
        </motion.div>)}
      <h1 className="text-3xl font-extrabold">{d.i.type.toUpperCase()} <span className="font-mono text-sm text-t3">#{d.i.code}</span></h1>
      <p className="text-t2 mb-6">{d.i.progress.awaiting_approval} require approval · {d.i.progress.completed} completed · {d.i.progress.monitoring} monitoring · {d.i.progress.total} identified</p>
      <div className="grid lg:grid-cols-[2fr_1fr] gap-5">
        <div className="space-y-4">
          <AnimatePresence>
            {pend.map((a: any) => (
              <motion.div key={a.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }} className="border border-amber rounded-xl p-4 bg-c1">
                <small className="text-amber font-bold tracking-widest">ACTION REQUIRES YOUR APPROVAL</small>
                <h3 className="text-lg font-bold my-1">{a.title}</h3>
                <p><b>Why:</b> {a.why}</p><p><b>Information shared:</b> {a.shares || "None"}</p><p><b>Potential consequence:</b> {a.consequence}</p>
                <p className="font-mono text-[10px] tracking-widest text-info my-2">SIMULATED ACTION — nothing external will happen</p>
                <div className="flex gap-2">
                  <motion.button whileTap={{ scale: 0.96 }} onClick={() => act(a.id, "approve")} className="bg-amber text-[#1a1100] font-bold rounded-lg px-4 py-2">Approve Action</motion.button>
                  <button onClick={() => act(a.id, "reject")} className="border border-bd rounded-lg px-4 py-2">Reject</button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          <Graph g={d.graph} sel={sel} onSel={setSel} />
          <div className="bg-c1 border border-bd rounded-xl p-4">
            <h2 className="text-xs tracking-widest text-t2 mb-3">RECOVERY PLAN</h2>
            <div className="border-l border-bd ml-1">
              {d.actions.map((a: any) => (
                <motion.div layout key={a.id} className="pl-4 pb-3 relative">
                  <span className="absolute -left-[5px] top-2 w-2.5 h-2.5 rounded-full" style={{ background: COLOR[a.state] }} />
                  <b>{a.title}</b> <Tag s={a.state} />
                  <div className="font-mono text-xs text-t3">{a.agent}{a.result?.message ? ` → ${a.result.message}` : ""}</div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div className="bg-c1 border border-bd rounded-xl p-4 text-center"><Ring p={d.i.progress} /><h2 className="text-xs tracking-widest text-t2">RECOVERY PROGRESS</h2></div>
          <div className="bg-c1 border border-bd rounded-xl p-4">
            <h2 className="text-xs tracking-widest text-t2 mb-2">WHAT IS AFFECTED</h2>
            {d.graph.nodes.map((n: any) => (<div key={n.id} className="mb-2"><div className="flex justify-between font-mono text-xs"><span>{n.label}</span><Tag s={n.state} /></div>
              <div className="h-1 bg-bd rounded overflow-hidden"><motion.div className="h-full bg-amber" animate={{ width: `${n.percent}%` }} /></div></div>))}
          </div>
          <div className="bg-c1 border border-bd rounded-xl p-4">
            <h2 className="text-xs tracking-widest text-t2 mb-2">AGENT ACTIVITY</h2>
            {d.agents.map((a: any) => (
              <div key={a.agent} className="mb-2"><b>{a.agent}</b> <span className="text-xs text-t2">{a.status}</span>
                <div className="font-mono text-xs text-t3">{a.task}</div></div>
            ))}
            <button onClick={() => api(`/incidents/${id}/monitor`, { method: "POST" }).then(load)} className="border border-bd rounded-lg px-3 py-1.5 mt-2">Run monitoring check</button>
          </div>
          <div className="bg-c1 border border-bd rounded-xl p-4">
            <h2 className="text-xs tracking-widest text-t2 mb-2">ACTIVITY LOG</h2>
            <div className="font-mono text-xs text-t2 max-h-64 overflow-auto">
              {d.log.map((e: any, k: number) => <div key={k}><span className="text-t3 mr-2">{new Date(e.at + "Z").toLocaleTimeString()}</span>{e.message}</div>)}
            </div>
          </div>
        </div>
      </div>
      <AnimatePresence>{toast && <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} role="status" className="fixed right-5 bottom-5 bg-c2 border border-amber rounded-lg px-4 py-3">{toast}</motion.div>}</AnimatePresence>
    </div>
  );
}

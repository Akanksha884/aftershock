"""LangGraph orchestration: Incident Agent -> router -> (Security | Finance | Research) -> Recovery Agent.
Deterministic in DEMO MODE. Falls back to a plain sequential run if langgraph is unavailable."""
from typing import Callable, TypedDict

class PState(TypedDict):
    itype: str
    agents: list
    findings: list
    plan: list

def build(plans: dict, generic: list, relevant: Callable[[str], list]):
    def incident(s):
        return {"findings": s["findings"] + [("Incident Agent", f"Classified incident as {s['itype']}")]}
    def route(s):
        return {"agents": relevant(s["itype"])}
    def security(s):
        n = sum(1 for p in plans.get(s["itype"], []) if p[2] == "Security Agent")
        return {"findings": s["findings"] + [("Security Agent", f"Account exposure analysis: {n} security actions needed")]}
    def finance(s):
        n = sum(1 for p in plans.get(s["itype"], []) if p[2] == "Finance Agent")
        return {"findings": s["findings"] + [("Finance Agent", f"Payment exposure review: {n} financial actions needed")]}
    def research(s):
        return {"findings": s["findings"] + [("Research Agent", "Local deterministic research: 3 reference sources")]}
    def recovery(s):
        return {"plan": plans.get(s["itype"], generic),
                "findings": s["findings"] + [("Recovery Agent", "Combined findings into recovery plan")]}

    nodes = {"incident": incident, "route": route, "security": security, "finance": finance,
             "research": research, "recovery": recovery}
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        def seq(state):
            for k in ("incident", "route"): state = {**state, **nodes[k](state)}
            for k in ("security", "finance", "research"):
                if f"{k.title()} Agent" in state["agents"]: state = {**state, **nodes[k](state)}
            return {**state, **nodes["recovery"](state)}
        return seq
    g = StateGraph(PState)
    for k, f in nodes.items(): g.add_node(k, f)
    g.set_entry_point("incident"); g.add_edge("incident", "route")
    # conditional routing: only relevant agents run, in sequence
    def pick(target):
        return lambda s: target if f"{target.title()} Agent" in s["agents"] else None
    g.add_conditional_edges("route", lambda s: "security" if "Security Agent" in s["agents"] else "finance_or_research",
                            {"security": "security", "finance_or_research": "finance_gate"})
    g.add_node("finance_gate", lambda s: {})
    g.add_edge("security", "finance_gate")
    g.add_conditional_edges("finance_gate", lambda s: "finance" if "Finance Agent" in s["agents"] else "research",
                            {"finance": "finance", "research": "research"})
    g.add_edge("finance", "research"); g.add_edge("research", "recovery"); g.add_edge("recovery", END)
    return g.compile().invoke

from __future__ import annotations

import json
import os
import urllib.request

from urbix_data.pipeline import CONNECTORS

TOOL_NAMES = {
    "city_overview",
    "traffic",
    "environment",
    "crime",
    "population",
    "transport",
    "waste",
    "infrastructure",
    "correlations",
    "models",
    "documents",
}


def rule_plan(question: str) -> list[str]:
    text = question.lower()
    selected = []
    mapping = [
        ("traffic", ("traffic", "congestion", "speed", "atr")),
        ("environment", ("air", "pm2", "pollution", "weather", "temperature")),
        ("crime", ("crime", "complaint", "safety")),
        ("population", ("population", "density", "census")),
        ("transport", ("subway", "transit", "ridership", "gtfs")),
        ("waste", ("waste", "refuse", "recycling", "tonnage")),
        ("infrastructure", ("building", "pluto", "road", "shelter")),
        ("correlations", ("correlat", "relationship", "associat")),
        ("models", ("predict", "forecast", "model")),
        ("documents", ("method", "source", "license", "dataset")),
    ]
    for name, words in mapping:
        if any(word in text for word in words):
            selected.append(name)
    if not selected:
        selected = ["city_overview", "documents"]
    elif "city_overview" not in selected:
        selected.insert(0, "city_overview")
    return selected


def llm_plan(question: str, rule_selection: list[str]) -> tuple[list[str], str]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return rule_selection, "rules"
    payload = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "Choose URBIX tools. Return JSON {\"tools\": [names]}. "
                    f"Allowed names: {sorted(TOOL_NAMES)}. Do not invent tools or numbers."
                ),
            },
            {"role": "user", "content": question},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    request = urllib.request.Request(
        os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        names = [name for name in parsed.get("tools", []) if name in TOOL_NAMES]
        if not names:
            return rule_selection, "rules_fallback"
        return names, "llm"
    except Exception:
        return rule_selection, "rules_fallback"


def execute_tools(session, city_slug: str, names: list[str], question: str) -> dict:
    from app.services import query

    calls = {
        "city_overview": lambda: query.city_overview(session, city_slug),
        "traffic": lambda: query.traffic_analytics(session, city_slug),
        "environment": lambda: query.environment_analytics(session, city_slug),
        "crime": lambda: query.crime_analytics(session, city_slug),
        "population": lambda: query.population_analytics(session, city_slug),
        "transport": lambda: query.transport_analytics(session, city_slug),
        "waste": lambda: query.waste_analytics(session, city_slug),
        "infrastructure": lambda: query.infrastructure_analytics(session, city_slug),
        "correlations": lambda: query.correlations(session, city_slug),
        "models": lambda: query.model_catalog(session),
        "documents": lambda: query.search_documents(session, question),
    }
    evidence = {}
    for name in names:
        if name not in calls:
            continue
        evidence[name] = calls[name]()
    return evidence


def compose(question: str, evidence: dict) -> dict:
    from app.services.query import unsupported_numbers

    claims = []
    for name, payload in evidence.items():
        if isinstance(payload, dict) and payload.get("availability") == "unavailable":
            claims.append({"claim_type": "unavailable", "statement": payload.get("reason") or f"{name} has no verified rows for this question.", "dataset_code": None, "support": payload})
            continue
        if name == "documents":
            for doc in payload:
                claims.append({"claim_type": "documented", "statement": f"{doc['title']} is relevant methodology context.", "dataset_code": None, "support": doc})
            continue
        limitations = payload.get("limitations") if isinstance(payload, dict) else None
        if limitations:
            claims.append({"claim_type": "limitation", "statement": limitations[0], "dataset_code": None, "support": {"tool": name}})
        kpis = payload.get("kpis") if isinstance(payload, dict) else None
        for item in (kpis or [])[:3]:
            if item.get("availability") != "available":
                claims.append({"claim_type": "unavailable", "statement": f"{item['label']} is unavailable.", "dataset_code": item.get("dataset_code"), "support": item})
            else:
                claims.append(
                    {
                        "claim_type": "observed",
                        "statement": f"{item['label']}: {item['value']} {item['unit']}. {item['methodology']}",
                        "dataset_code": item.get("dataset_code"),
                        "support": item,
                    }
                )
        if name == "correlations" and isinstance(payload, dict) and payload.get("result"):
            result = payload["result"]
            reported = round(float(result["coefficient"]), 3)
            result["reported_coefficient"] = reported
            claims.append(
                {
                    "claim_type": "statistical",
                    "statement": f"Pearson coefficient {reported} on n={result['n']}. {payload['interpretation']}",
                    "dataset_code": "open-meteo-weather",
                    "support": payload,
                }
            )
    prose = " ".join(claim["statement"] for claim in claims[:8]) or "No verified evidence was retrieved."
    rejected = None
    if unsupported_numbers(prose, evidence):
        rejected = prose
        prose = "The drafted summary contained a number that was not in the tool evidence, so it was discarded."
        claims.insert(0, {"claim_type": "rejected", "statement": prose, "dataset_code": None, "support": {"rejected": rejected}})
    return {
        "question": question,
        "prose": prose,
        "claims": claims,
        "planner_note": "Observed values come from tool results. Statistical lines are associations. Unavailable data is stated rather than filled.",
    }


def investigate(session, question: str, city_slug: str = "nyc") -> dict:
    rules = rule_plan(question)
    names, planner = llm_plan(question, rules)
    try:
        from langgraph.graph import END, StateGraph

        class State(dict):
            pass

        def plan_node(state):
            state = dict(state)
            state["tools"] = names
            state["planner"] = planner
            return state

        def execute_node(state):
            state = dict(state)
            state["evidence"] = execute_tools(session, city_slug, state["tools"], question)
            return state

        def compose_node(state):
            state = dict(state)
            state["answer"] = compose(question, state["evidence"])
            return state

        graph = StateGraph(dict)
        graph.add_node("plan", plan_node)
        graph.add_node("execute", execute_node)
        graph.add_node("compose", compose_node)
        graph.set_entry_point("plan")
        graph.add_edge("plan", "execute")
        graph.add_edge("execute", "compose")
        graph.add_edge("compose", END)
        result = graph.compile().invoke({"question": question})
        answer = result["answer"]
        used_planner = result["planner"]
        used_tools = result["tools"]
    except Exception:
        evidence = execute_tools(session, city_slug, names, question)
        answer = compose(question, evidence)
        used_planner = planner
        used_tools = names
    from app.services.query import save_investigation

    investigation = save_investigation(session, question, city_slug, answer, used_planner, used_tools)
    answer["investigation_id"] = investigation.id
    answer["planner"] = used_planner
    answer["tools"] = used_tools
    return answer


def build_report(session, city_slug: str = "nyc") -> dict:
    from app.services.query import city_overview, save_report

    overview = city_overview(session, city_slug)
    evidence = []
    for domain, payload in overview.get("domains", {}).items():
        for item in payload.get("kpis", []):
            evidence.append(
                {
                    "claim_type": "observed" if item.get("availability") == "available" else "unavailable",
                    "statement": f"{domain}: {item['label']} is {item['value']} {item['unit']}" if item.get("availability") == "available" else f"{domain}: {item['label']} is unavailable.",
                    "dataset_code": item.get("dataset_code"),
                    "support": item,
                }
            )
        for limitation in payload.get("limitations", [])[:1]:
            evidence.append({"claim_type": "limitation", "statement": limitation, "dataset_code": None, "support": {}})
    body = {
        "title": f"URBIX evidence report — {city_slug}",
        "city": city_slug,
        "period": "loaded extracts",
        "observations": [item["statement"] for item in evidence if item["claim_type"] == "observed"],
        "limitations": [item["statement"] for item in evidence if item["claim_type"] == "limitation"],
        "methodology": "Every statement is copied from a KPI that the query service computed from stored rows. The language model is not used to create this report.",
    }
    report = save_report(session, body["title"], city_slug, body, evidence)
    body["id"] = report.id
    return body


ALLOWED_CONNECTORS = set(CONNECTORS) | {"reference-geography"}

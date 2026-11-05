"""Provider-independent draft generator. Deterministic fallback always works; Ollama is optional."""
import os, json, urllib.request

def evidence(t):
    return [s["subject"] + " - " + "; ".join(
        f"{p['term']}: {p['pct']}%" if p["pct"] is not None else f"{p['term']}: {p['status']}" for p in s["points"])
        for s in t["subjects"]]

def fallback(name, t, ev):
    lines = [f"DRAFT - not reviewed. Progress summary for {name}, based only on recorded results.", "", "From the records:"]
    for s in t["subjects"]:
        if s["average"] is None:
            lines.append(f"- {s['subject']}: no scored results yet.")
        else:
            ch = "" if s["change"] is None else f", change of {s['change']:+} points between first and latest assessed term"
            lines.append(f"- {s['subject']}: average {s['average']}%{ch}.")
    lines += ["", "Worth a teacher's attention:"]
    lines += [f"- {f['text']}" for f in t["flags"]] or ["- No indicators raised from the recorded results."]
    lines += ["", "This draft restates recorded scores only. It makes no diagnosis. Add your own observations before approving."]
    return "\n".join(lines)

def _ollama(prompt):
    req = urllib.request.Request(os.getenv("OLLAMA_URL", "http://localhost:11434") + "/api/generate",
        json.dumps({"model": os.getenv("OLLAMA_MODEL", "llama3.1"), "prompt": prompt, "stream": False}).encode(),
        {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))["response"]

def draft(name, t):
    ev = evidence(t)
    text, provider = fallback(name, t, ev), "deterministic"
    if os.getenv("AI_PROVIDER") == "ollama":
        try:
            p = ("Write a short teacher-facing progress summary for " + name + ". Use ONLY this evidence, invent nothing, "
                 "give no medical, psychological or disability diagnosis.\n" + "\n".join(ev) + "\nIndicators: " + "; ".join(f["text"] for f in t["flags"]))
            text, provider = "DRAFT - not reviewed.\n" + _ollama(p), "ollama"
        except Exception:
            pass
    return {"text": text, "evidence": ev, "provider": provider}

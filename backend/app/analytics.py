"""Longitudinal analytics with Pandas/NumPy. Missing results are never treated as zero."""
import numpy as np, pandas as pd

METHOD = ("Each score is converted to a percentage of its own maximum (score / max x 100) so different scales are comparable. "
          "Only scored results are used: absent, unassessed and missing results appear as gaps and are never counted as zero. "
          "A decline flag needs 3+ assessed terms with a drop in each of the last two and 5+ points in total. "
          "An inconsistency flag needs 3+ assessed terms with a standard deviation of 12+ points. "
          "Flags are prompts for teacher review, not diagnoses or decisions.")

def trends(rows):
    out = {"subjects": [], "flags": [], "method": METHOD}
    if not rows:
        return out
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["pct"] = df["value"] / df["max"] * 100
    df.loc[df["status"] != "scored", "pct"] = np.nan
    for sub, g in df.sort_values("ord").groupby("subject", sort=True):
        pts = [{"term": t, "pct": None if pd.isna(p) else round(float(p), 1), "status": s}
               for t, p, s in zip(g["term"], g["pct"], g["status"])]
        v = g["pct"].dropna().to_numpy(dtype=float)
        out["subjects"].append({"subject": sub, "points": pts,
                                "average": round(float(v.mean()), 1) if len(v) else None,
                                "change": round(float(v[-1] - v[0]), 1) if len(v) > 1 else None})
        if len(v) >= 3 and v[-1] < v[-2] < v[-3] and v[-3] - v[-1] >= 5:
            out["flags"].append({"subject": sub, "type": "declining",
                                 "text": f"{sub}: scores fell in each of the last 3 assessed terms ({v[-3]:.0f}, {v[-2]:.0f}, {v[-1]:.0f})."})
        elif len(v) >= 3 and float(v.std()) >= 12:
            out["flags"].append({"subject": sub, "type": "inconsistent",
                                 "text": f"{sub}: results vary widely between terms (standard deviation {v.std():.0f} points)."})
    return out

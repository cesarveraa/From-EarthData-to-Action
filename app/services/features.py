import numpy as np

def summarize_openaq(openaq_json):
    vals = {"pm25": [], "no2": [], "o3": []}
    for item in openaq_json.get("results", []):
        p = item.get("parameter")
        if p in vals:
            vals[p].append(item.get("value"))
    def stats(x):
        if not x: return None
        a = np.array(x, dtype=float)
        return {"mean": float(a.mean()), "p90": float(np.quantile(a, 0.9)), "last": float(a[0])}
    return {k: stats(v) for k, v in vals.items()}

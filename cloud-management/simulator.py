"""Simulated cloud environment for a retail business (no real cloud account needed).

Load is the average requests/minute each service receives per hour.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)

# capacity = requests/min one instance can handle, cost = USD per instance-hour
SERVICES = {
    "web-store":       dict(base=1800, capacity=600, cost=0.12, min=2, max=20, instances=5),
    "pos-api":         dict(base=900,  capacity=300, cost=0.10, min=2, max=12, instances=4),
    "inventory-db":    dict(base=400,  capacity=200, cost=0.25, min=2, max=8,  instances=3),
    "payment-gateway": dict(base=250,  capacity=100, cost=0.15, min=2, max=10, instances=4),
}


def generate_history(hours: int = 24 * 14) -> pd.DataFrame:
    """Hourly load per service: daily cycle, weekend uplift, trend, noise, one anomaly."""
    idx = pd.date_range(end=pd.Timestamp.now().floor("h"), periods=hours, freq="h")
    rows = []
    for name, s in SERVICES.items():
        for i, ts in enumerate(idx):
            daily = 0.6 + 0.4 * np.sin((ts.hour - 6) / 24 * 2 * np.pi)  # peak around noon
            weekend = 1.25 if ts.dayofweek >= 5 else 1.0
            trend = 1 + 0.0003 * i
            load = s["base"] * daily * weekend * trend * rng.normal(1, 0.05)
            rows.append((ts, name, max(load, 1.0)))
    df = pd.DataFrame(rows, columns=["ts", "service", "load"])
    # inject a past incident (e.g. bot traffic / retry storm) on the payment gateway
    mask = (df.service == "payment-gateway") & (df.ts == idx[-40])
    df.loc[mask, "load"] *= 4
    return df

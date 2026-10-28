"""Intelligent cloud manager: forecasting, auto-scaling, anomaly detection, cost optimisation."""
import math

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

import simulator

TARGET_UTIL = 0.65  # aim to run instances at ~65% utilisation


def _features(ts: pd.DatetimeIndex, start: pd.Timestamp) -> np.ndarray:
    hour = ts.hour.values
    t = ((ts - start) / pd.Timedelta(hours=1)).values.reshape(-1, 1) / 100.0
    cols = [t,
            np.sin(2 * np.pi * hour / 24).reshape(-1, 1), np.cos(2 * np.pi * hour / 24).reshape(-1, 1),
            np.sin(4 * np.pi * hour / 24).reshape(-1, 1), np.cos(4 * np.pi * hour / 24).reshape(-1, 1),
            (ts.dayofweek.values >= 5).astype(float).reshape(-1, 1)]
    return np.hstack(cols)


class CloudManager:
    def __init__(self):
        self.cfg = {k: dict(v) for k, v in simulator.SERVICES.items()}
        self.history = simulator.generate_history()
        self.action_log: list[dict] = []

    # ---------- helpers ----------
    def _hist(self, name: str) -> pd.DataFrame:
        return self.history[self.history.service == name].sort_values("ts").reset_index(drop=True)

    def _fit(self, name: str):
        h = self._hist(name)
        start = h.ts.min()
        model = Ridge(alpha=0.1).fit(_features(pd.DatetimeIndex(h.ts), start), h.load.values)
        return h, start, model

    def current_load(self, name: str) -> float:
        return float(self._hist(name).load.iloc[-1])

    def utilisation(self, name: str) -> float:
        c = self.cfg[name]
        return self.current_load(name) / (c["instances"] * c["capacity"])

    # ---------- 1. Traffic forecasting ----------
    def forecast(self, name: str, horizon: int = 6) -> list[dict]:
        h, start, model = self._fit(name)
        future = pd.date_range(h.ts.max() + pd.Timedelta(hours=1), periods=horizon, freq="h")
        pred = np.clip(model.predict(_features(future, start)), 0, None)
        return [{"ts": t.strftime("%Y-%m-%d %H:%M"), "predicted_load": round(float(p), 1)}
                for t, p in zip(future, pred)]

    # ---------- 2. Auto-scaling ----------
    def autoscale_plan(self, horizon: int = 3) -> list[dict]:
        plan = []
        for name, c in self.cfg.items():
            peak = max(self.current_load(name),
                       max(f["predicted_load"] for f in self.forecast(name, horizon)))
            desired = math.ceil(peak / (c["capacity"] * TARGET_UTIL))
            desired = max(c["min"], min(c["max"], desired))
            action = ("scale_up" if desired > c["instances"]
                      else "scale_down" if desired < c["instances"] else "none")
            plan.append({"service": name, "current": c["instances"], "desired": desired,
                         "action": action, "expected_peak_load": round(peak, 1),
                         "utilisation_pct": round(self.utilisation(name) * 100, 1)})
        return plan

    def apply_autoscaling(self) -> list[dict]:
        applied = []
        for p in self.autoscale_plan():
            if p["action"] != "none":
                self.cfg[p["service"]]["instances"] = p["desired"]
                entry = {"time": pd.Timestamp.now().isoformat(timespec="seconds"), **p}
                self.action_log.append(entry)
                applied.append(entry)
        return applied

    # ---------- 3. Anomaly detection ----------
    def anomalies(self, z_threshold: float = 4.0, min_change: float = 1.0) -> list[dict]:
        """Flag hours whose load deviates strongly from what the model expects.

        Needs both a high robust z-score and a large relative change (min_change=1.0 -> 2x expected)
        so tiny blips at low-traffic hours are ignored."""
        found = []
        for name in self.cfg:
            h, start, model = self._fit(name)
            fitted = np.clip(model.predict(_features(pd.DatetimeIndex(h.ts), start)), 1, None)
            rel = (h.load.values - fitted) / fitted
            med = np.median(rel)
            mad = np.median(np.abs(rel - med)) or 1e-9
            z = 0.6745 * (rel - med) / mad
            for i in np.where((np.abs(z) > z_threshold) & (np.abs(rel) > min_change))[0]:
                found.append({"service": name, "ts": h.ts[i].strftime("%Y-%m-%d %H:%M"),
                              "load": round(float(h.load[i]), 1),
                              "expected": round(float(fitted[i]), 1),
                              "z_score": round(float(z[i]), 1),
                              "type": "spike" if z[i] > 0 else "drop"})
        return sorted(found, key=lambda a: a["ts"], reverse=True)

    def inject_spike(self, name: str, factor: float = 4.0) -> float:
        """Simulate a sudden traffic surge on the latest hour (e.g. flash sale)."""
        m = (self.history.service == name) & (self.history.ts == self.history.ts.max())
        self.history.loc[m, "load"] *= factor
        return self.current_load(name)

    # ---------- 4. Cost optimisation ----------
    def cost_report(self) -> dict:
        rows, total, optimal_total = [], 0.0, 0.0
        for name, c in self.cfg.items():
            last24 = self._hist(name).load.tail(24)
            right = math.ceil(last24.median() / (c["capacity"] * TARGET_UTIL))  # typical-hour sizing
            right = max(c["min"], min(c["max"], right))
            hourly = c["instances"] * c["cost"]
            total += hourly
            rows.append({"service": name, "instances": c["instances"],
                         "hourly_cost": round(hourly, 2),
                         "monthly_cost": round(hourly * 730, 2),
                         "avg_utilisation_pct": round(float(last24.mean()) / (c["instances"] * c["capacity"]) * 100, 1)})
            optimal_total += right * c["cost"]
        return {"services": rows,
                "total_hourly": round(total, 2),
                "total_monthly": round(total * 730, 2),
                "note": "Monthly = hourly x 730. Autoscaling lowers cost off-peak vs a fixed fleet.",
                "fixed_fleet_vs_typical_hour_saving_pct":
                    round(max(0, (total - optimal_total) / total * 100), 1) if total else 0}

    # ---------- 5. Alerts ----------
    def alerts(self) -> list[dict]:
        out = []
        for name, c in self.cfg.items():
            u = self.utilisation(name) * 100
            if u > 85:
                out.append({"severity": "critical", "service": name, "message": f"Utilisation {u:.0f}% — scale up now"})
            elif u > 75:
                out.append({"severity": "warning", "service": name, "message": f"Utilisation {u:.0f}% — nearing capacity"})
            elif u < 20 and c["instances"] > c["min"]:
                out.append({"severity": "info", "service": name, "message": f"Utilisation {u:.0f}% — over-provisioned"})
        cutoff = (pd.Timestamp.now() - pd.Timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")
        for a in self.anomalies():
            if a["ts"] >= cutoff:
                out.append({"severity": "warning", "service": a["service"],
                            "message": f"Traffic {a['type']} at {a['ts']} (z={a['z_score']})"})
        return out

    def overview(self) -> list[dict]:
        return [{"service": n, "instances": c["instances"], "min": c["min"], "max": c["max"],
                 "load_req_min": round(self.current_load(n), 1),
                 "utilisation_pct": round(self.utilisation(n) * 100, 1),
                 "cost_per_hour": round(c["instances"] * c["cost"], 2)}
                for n, c in self.cfg.items()]

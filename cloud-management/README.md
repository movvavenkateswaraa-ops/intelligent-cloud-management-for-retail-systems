# Intelligent Cloud Management for Retail Systems

A simple base project that shows how AI/ML can manage cloud infrastructure for a retail business.
The cloud is **simulated** (no AWS/Azure/GCP account needed), so you can run and experiment offline.

## What it manages
Four retail services: `web-store`, `pos-api`, `inventory-db`, `payment-gateway`,
each with instance counts, capacity, hourly cost and min/max limits (see `simulator.py`).

## Features
| Module | What it does | Method |
|---|---|---|
| Traffic forecasting | Predicts load for the next hours | Ridge regression (daily cycle, weekend, trend) |
| Auto-scaling | Computes and applies the ideal instance count | Forecast peak / (capacity x 65% target utilisation) |
| Anomaly detection | Finds unusual traffic spikes/drops | Robust z-score on forecast residuals |
| Cost optimisation | Hourly/monthly cost and utilisation per service | Cost model + right-sizing |
| Alerts | Critical/warning/info messages | Utilisation thresholds + anomalies |

## Run
```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5001

Try it: click **Simulate flash-sale spike**, see the critical alert and anomaly appear,
then click **Apply auto-scaling** to watch instances scale up and cost change.

## API
- `GET  /api/services`
- `GET  /api/forecast/<service>?hours=6`
- `GET  /api/autoscale/plan`
- `POST /api/autoscale/apply`
- `GET  /api/actions` : scaling history
- `GET  /api/anomalies`
- `GET  /api/cost`
- `GET  /api/alerts`
- `POST /api/spike` with `{"service": "web-store", "factor": 4}`

## Structure
```
app.py          Flask API + dashboard
manager.py      Forecasting, auto-scaling, anomalies, cost, alerts
simulator.py    Simulated services and traffic history
requirements.txt
```

## Ideas to extend
Connect real cloud SDKs (boto3, Azure SDK), pull metrics from CloudWatch/Prometheus, use Prophet/LSTM
for forecasting, add spot-instance cost strategies, scheduled scaling for sale events, Slack/email alerts.

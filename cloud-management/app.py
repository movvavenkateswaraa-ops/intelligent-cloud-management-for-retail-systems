"""Flask API + dashboard for Intelligent Cloud Management for Retail Systems."""
from flask import Flask, jsonify, request, render_template_string

from manager import CloudManager

app = Flask(__name__)
mgr = CloudManager()

DASHBOARD = """
<!doctype html>
<title>Retail Cloud Manager</title>
<style>
  body{font-family:system-ui,sans-serif;margin:2rem auto;max-width:980px;padding:0 1rem;color:#222}
  section{margin:1.8rem 0} table{border-collapse:collapse;width:100%}
  th,td{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left}
  button{padding:8px 14px;border:0;border-radius:6px;background:#2563eb;color:#fff;cursor:pointer;margin-right:8px}
  button.warn{background:#dc2626}
  .critical{color:#b91c1c;font-weight:600}.warning{color:#b45309}.info{color:#2563eb}
</style>
<h1>Intelligent Cloud Management for Retail Systems</h1>
<p>Forecasting, auto-scaling, anomaly detection and cost optimisation (simulated cloud).</p>
<p><button onclick="act('/api/autoscale/apply')">Apply auto-scaling</button>
   <button class="warn" onclick="spike()">Simulate flash-sale spike (web-store x4)</button></p>

<section><h2>Services</h2><table id="svc"></table></section>
<section><h2>Alerts</h2><table id="alerts"></table></section>
<section><h2>Auto-scaling plan</h2><table id="plan"></table></section>
<section><h2>Cost</h2><table id="cost"></table><p id="total"></p></section>
<section><h2>Detected anomalies</h2><table id="anom"></table></section>

<script>
const J = async (u, o) => (await fetch(u, o)).json();
const rows = (id, cols, data) => {
  document.getElementById(id).innerHTML = '<tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr>' +
    (data.length ? data.map(r => '<tr>' + cols.map(c => `<td class="${c=='severity'?r[c]:''}">${r[c] ?? ''}</td>`).join('') + '</tr>').join('')
                 : `<tr><td colspan="${cols.length}">None</td></tr>`);
};
async function load(){
  rows('svc', ['service','instances','min','max','load_req_min','utilisation_pct','cost_per_hour'], await J('/api/services'));
  rows('alerts', ['severity','service','message'], await J('/api/alerts'));
  rows('plan', ['service','current','desired','action','expected_peak_load','utilisation_pct'], await J('/api/autoscale/plan'));
  const c = await J('/api/cost');
  rows('cost', ['service','instances','hourly_cost','monthly_cost','avg_utilisation_pct'], c.services);
  document.getElementById('total').innerText = `Total: $${c.total_hourly}/hour, about $${c.total_monthly}/month`;
  rows('anom', ['service','ts','load','expected','z_score','type'], await J('/api/anomalies'));
}
async function act(u){ await J(u, {method:'POST'}); load(); }
async function spike(){
  await J('/api/spike', {method:'POST', headers:{'Content-Type':'application/json'},
                         body: JSON.stringify({service:'web-store', factor:4})});
  load();
}
load();
</script>
"""


@app.get("/")
def home():
    return render_template_string(DASHBOARD)


@app.get("/api/services")
def services():
    return jsonify(mgr.overview())


@app.get("/api/forecast/<service>")
def forecast(service):
    if service not in mgr.cfg:
        return jsonify(error="unknown service"), 404
    return jsonify(mgr.forecast(service, request.args.get("hours", 6, type=int)))


@app.get("/api/autoscale/plan")
def plan():
    return jsonify(mgr.autoscale_plan())


@app.post("/api/autoscale/apply")
def apply_scaling():
    return jsonify(applied=mgr.apply_autoscaling())


@app.get("/api/actions")
def actions():
    return jsonify(mgr.action_log)


@app.get("/api/anomalies")
def anomalies():
    return jsonify(mgr.anomalies())


@app.get("/api/cost")
def cost():
    return jsonify(mgr.cost_report())


@app.get("/api/alerts")
def alerts():
    return jsonify(mgr.alerts())


@app.post("/api/spike")
def spike():
    body = request.get_json(force=True)
    name = body.get("service", "web-store")
    if name not in mgr.cfg:
        return jsonify(error="unknown service"), 404
    load = mgr.inject_spike(name, float(body.get("factor", 4)))
    return jsonify(service=name, new_load=round(load, 1))


if __name__ == "__main__":
    app.run(debug=True, port=5001)

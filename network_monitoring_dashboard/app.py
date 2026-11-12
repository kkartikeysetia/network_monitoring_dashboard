"""NOC-style network service monitoring and incident ticketing demo."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from database import init_db, save_check, create_or_update_incident, get_checks, get_incidents, update_incident
from monitor import check_service

st.set_page_config(page_title="NOC Monitor & Incident Desk", page_icon="🖧", layout="wide")
init_db()

SERVICES = [
    {"name": "Google Homepage", "url": "https://www.google.com"},
    {"name": "GitHub", "url": "https://github.com"},
    {"name": "Cloudflare", "url": "https://www.cloudflare.com"},
]

st.title("🖧 Network Service Monitoring & Incident Desk")
st.caption("Student project demo: HTTP availability, DNS/TCP checks, alert triage and incident ticket lifecycle.")

with st.sidebar:
    st.header("Monitoring controls")
    st.write("Checks are run when you click the button; this demo does not run as a 24×7 production monitor.")
    simulate = st.checkbox("Enable demo outage simulation", value=False)
    simulated_service = st.selectbox("Service to simulate as DOWN", [s["name"] for s in SERVICES])
    run = st.button("Run monitoring checks", type="primary", use_container_width=True)
    st.divider()
    st.caption("A simulated outage changes only the demo record; it does not affect the real website.")

if run:
    results = []
    for service in SERVICES:
        force_down = bool(simulate and service["name"] == simulated_service)
        result = check_service(service, force_down=force_down)
        results.append(result)
        save_check(result)
    down_count = sum(r["status"] == "DOWN" for r in results)
    degraded_count = sum(r["status"] == "DEGRADED" for r in results)
    for result in results:
        if result["status"] != "UP":
            severity = "P1" if down_count >= 2 else ("P2" if result["status"] == "DOWN" else "P3")
            create_or_update_incident(result, severity)
    st.success(f"Checks completed: {len(results)} services checked; {down_count} DOWN; {degraded_count} DEGRADED.")

checks = get_checks(50)
incidents = get_incidents()
latest_by_service = {}
for item in checks:
    latest_by_service.setdefault(item["service"], item)

open_incidents = [i for i in incidents if i["status"] != "RESOLVED"]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Services monitored", len(SERVICES))
col2.metric("Services currently DOWN", sum(1 for s in SERVICES if latest_by_service.get(s["name"], {}).get("status") == "DOWN"))
col3.metric("Open incidents", len(open_incidents))
col4.metric("Total tickets", len(incidents))

st.subheader("Service health")
health_rows = []
for service in SERVICES:
    latest = latest_by_service.get(service["name"])
    health_rows.append({
        "Service": service["name"],
        "URL": service["url"],
        "Status": latest["status"] if latest else "NOT CHECKED",
        "Latency (ms)": latest["latency_ms"] if latest else "—",
        "HTTP status": latest["http_status"] if latest else "—",
        "Last checked": latest["checked_at"] if latest else "—",
        "Diagnosis": latest["diagnosis"] if latest else "Run a check to collect data.",
    })
st.dataframe(pd.DataFrame(health_rows), use_container_width=True, hide_index=True)

st.subheader("Incident tickets")
if incidents:
    ticket_df = pd.DataFrame(incidents)
    st.dataframe(ticket_df[["ticket_id", "service", "severity", "status", "diagnosis", "created_at", "updated_at"]],
                 use_container_width=True, hide_index=True)
    actionable = [i for i in incidents if i["status"] != "RESOLVED"]
    if actionable:
        st.markdown("**Update an incident**")
        selected_ticket = st.selectbox("Ticket", [i["ticket_id"] for i in actionable])
        action = st.selectbox("Action", ["Acknowledge", "Resolve"])
        note = st.text_input("Resolution / handover note", placeholder="e.g. DNS configuration checked; service restored and verified")
        if st.button("Update ticket"):
            new_status = "ACKNOWLEDGED" if action == "Acknowledge" else "RESOLVED"
            update_incident(selected_ticket, new_status, note)
            st.success(f"{selected_ticket} updated to {new_status}.")
            st.rerun()
else:
    st.info("No incidents yet. Use the simulation control to create a safe demo ticket, or wait for a real check failure.")

st.subheader("Recent monitoring history")
if checks:
    history = pd.DataFrame(checks)
    st.dataframe(history[["service", "status", "latency_ms", "http_status", "resolved_ip", "diagnosis", "checked_at", "is_simulated"]],
                 use_container_width=True, hide_index=True)
    st.download_button("Download monitoring history (CSV)", history.to_csv(index=False).encode("utf-8"),
                       file_name="noc_monitoring_history.csv", mime="text/csv")
else:
    st.info("No monitoring results yet. Select 'Run monitoring checks' in the sidebar.")

st.caption("Scope: educational prototype only. It monitors a small list of public HTTP services; it is not a carrier-grade NOC platform.")

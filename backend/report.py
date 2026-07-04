# Report Generator for EdgeTwin AI
from datetime import datetime
from backend.database import get_financial_summary, get_all_incidents, get_maintenance_schedule

MACHINE_NAMES = {
    "M1": "CNC Mill (M1)",
    "M2": "Injection Molder (M2)",
    "M3": "6-Axis Robot Arm (M3)",
    "M4": "Air Compressor (M4)",
    "M5": "Smart Conveyor (M5)",
    "M6": "Hydraulic Press (M6)"
}

def generate_html_report(machines_status):
    """
    Compiles database statistics and live digital twin values 
    into a beautiful, styled, print-ready HTML page.
    """
    financials = get_financial_summary()
    incidents = get_all_incidents(limit=15)
    schedule = get_maintenance_schedule()
    
    # Calculate average factory health
    avg_health = sum(m["health_score"] for m in machines_status.values()) / len(machines_status)
    
    # Create HTML table for machines
    machine_rows = ""
    for mid, mdata in machines_status.items():
        metrics = mdata.get("metrics", {})
        ai_pred = mdata.get("ai_prediction", {})
        
        status_class = "status-green"
        if mdata["status"] == "warning":
            status_class = "status-yellow"
        elif mdata["status"] == "critical":
            status_class = "status-red"
            
        machine_rows += f"""
        <tr>
            <td><strong>{MACHINE_NAMES[mid]}</strong></td>
            <td><span class="status-badge {status_class}">{mdata['status'].upper()}</span> ({mdata['health_score']}%)</td>
            <td>{metrics.get('temperature', 0)} °C</td>
            <td>{metrics.get('vibration', 0)} mm/s</td>
            <td>{metrics.get('load', 0)} %</td>
            <td>{ai_pred.get('failure_probability', 0)} %</td>
            <td>{ai_pred.get('rul_hours', 0)} hrs</td>
        </tr>
        """
        
    # Incident history rows
    incident_rows = ""
    if not incidents:
        incident_rows = "<tr><td colspan='6' class='text-center'>No incidents logged today.</td></tr>"
    else:
        for inc in incidents:
            resolved_badge = '<span class="status-badge status-green">RESOLVED</span>' if inc['resolved'] else '<span class="status-badge status-red">ACTIVE</span>'
            time_parsed = datetime.fromisoformat(inc['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            incident_rows += f"""
            <tr>
                <td>{time_parsed}</td>
                <td>{MACHINE_NAMES.get(inc['machine_id'], inc['machine_id'])}</td>
                <td>{inc['type'].upper()}</td>
                <td><span class="status-badge status-{'red' if inc['severity'] == 'critical' else 'yellow'}">{inc['severity'].upper()}</span></td>
                <td>{inc['action_taken'] or 'None'}</td>
                <td>{resolved_badge}</td>
            </tr>
            """
            
    # Maintenance Schedule rows
    maint_rows = ""
    if not schedule:
        maint_rows = "<tr><td colspan='6' class='text-center'>No maintenance tasks scheduled. Click 'Optimize Plan' on the dashboard.</td></tr>"
    else:
        for slot in schedule:
            time_parsed = datetime.fromisoformat(slot['scheduled_time']).strftime('%Y-%m-%d %H:%M')
            priority_class = "status-red" if slot['priority'] == 'CRITICAL' else ("status-yellow" if slot['priority'] == 'HIGH' else "status-green")
            maint_rows += f"""
            <tr>
                <td>{time_parsed}</td>
                <td>{MACHINE_NAMES.get(slot['machine_id'], slot['machine_id'])}</td>
                <td>{slot['duration_mins']} mins</td>
                <td>{slot['required_parts']}</td>
                <td>{slot['assigned_engineer']}</td>
                <td><span class="status-badge {priority_class}">{slot['priority']}</span></td>
            </tr>
            """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>EdgeTwin AI - Operational & ROI Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #333;
            line-height: 1.5;
            padding: 20px;
            background-color: #fff;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 3px solid #10b981;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            color: #064e3b;
            font-size: 28px;
        }}
        .header p {{
            margin: 5px 0 0 0;
            color: #6b7280;
        }}
        .meta-info {{
            text-align: right;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 15px;
            background-color: #f9fafb;
            text-align: center;
        }}
        .card .title {{
            font-size: 12px;
            text-transform: uppercase;
            color: #6b7280;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .card .value {{
            font-size: 24px;
            font-weight: bold;
            color: #111827;
        }}
        .card .value.roi {{
            color: #10b981;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            font-size: 18px;
            color: #0f172a;
            border-bottom: 1px solid #e5e7eb;
            padding-bottom: 8px;
            margin-bottom: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: left;
            font-size: 13px;
            border-bottom: 1px solid #e5e7eb;
        }}
        th {{
            background-color: #f3f4f6;
            color: #374151;
            font-weight: 600;
        }}
        .status-badge {{
            display: inline-block;
            padding: 2px 6px;
            font-size: 11px;
            font-weight: bold;
            border-radius: 4px;
        }}
        .status-green {{
            background-color: #d1fae5;
            color: #065f46;
        }}
        .status-yellow {{
            background-color: #fef3c7;
            color: #92400e;
        }}
        .status-red {{
            background-color: #fee2e2;
            color: #991b1b;
        }}
        .text-center {{
            text-align: center;
        }}
        .print-btn {{
            background-color: #10b981;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            cursor: pointer;
            float: right;
            margin-bottom: 20px;
        }}
        @media print {{
            .print-btn {{
                display: none;
            }}
            body {{
                padding: 0;
            }}
        }}
    </style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">Print / Export PDF</button>

    <div class="header">
        <div>
            <h1>EdgeTwin AI &bull; Executive Intelligence Report</h1>
            <p style="margin: 5px 0 0 0; color: #6b7280; font-size: 14px;">Autonomous Factory Decision Intelligence Platform</p>
        </div>
        <div class="meta-info">
            <strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
            <strong>System Mode:</strong> <span class="status-badge status-green">Edge Production Mode</span>
        </div>
    </div>

    <!-- Section 1: Executive Summary -->
    <div class="section">
        <h2>1. Executive Summary</h2>
        <p>This executive intelligence report summarizes the operational health, diagnostic findings, and business impact projections for the manufacturing facility. EdgeTwin AI integrates real-time telemetry, probabilistic root cause modeling, and maintenance scheduling to provide a comprehensive decision support system. AI autonomously generates recommendations while physical component validation remains engineer-assisted to maximize safety and precision.</p>
    </div>

    <!-- Section 2: Factory Health & KPI Block -->
    <div class="section">
        <h2>2. Factory Health & Operational KPIs</h2>
        <div class="grid">
            <div class="card">
                <div class="title">Validated Business Impact</div>
                <div class="value roi">&#x20B9;{financials['cost_saved']:,}</div>
            </div>
            <div class="card">
                <div class="title">Prevented Downtime</div>
                <div class="value">{financials['downtime_prevented']} hrs</div>
            </div>
            <div class="card">
                <div class="title">Energy Conserved</div>
                <div class="value">{financials['energy_saved']} kWh</div>
            </div>
            <div class="card">
                <div class="title">Factory Health Index</div>
                <div class="value">{avg_health:.1f}%</div>
            </div>
        </div>
    </div>

    <!-- Section 3: Digital Twin Machine Summary / Critical Assets -->
    <div class="section">
        <h2>3. Critical Assets & Root Cause Analysis</h2>
        <p>Real-time edge sensor networks track machine wear patterns. Below is the current availability and prediction confidence for suspected degradations:</p>
        <table>
            <thead>
                <tr>
                    <th>Asset Name</th>
                    <th>Overall Health</th>
                    <th>Temp</th>
                    <th>Vibration</th>
                    <th>Load</th>
                    <th>Prediction Confidence</th>
                    <th>Est. RUL</th>
                </tr>
            </thead>
            <tbody>
                {machine_rows}
            </tbody>
        </table>
    </div>

    <!-- Section 4: Maintenance Plan & Scheduler Rationale -->
    <div class="section">
        <h2>4. Maintenance Plan & Scheduler Rationale</h2>
        <p>Optimized schedules designed to align maintenance activities with off-peak production schedules, minimizing total factory downtime.</p>
        <table>
            <thead>
                <tr>
                    <th>Scheduled Slot</th>
                    <th>Asset</th>
                    <th>Est. Duration</th>
                    <th>Required Spares</th>
                    <th>Assigned Engineer</th>
                    <th>Priority</th>
                </tr>
            </thead>
            <tbody>
                {maint_rows}
            </tbody>
        </table>
    </div>

    <!-- Section 5: Financial Impact & ROI Breakdown -->
    <div class="section">
        <h2>5. Financial Impact & ROI Breakdown</h2>
        <p>Quantifying cost avoidance comparing planned preventive maintenance against reactive breakdowns. Expected production loss is modeled on historical schedules and machine criticality.</p>
        <table>
            <thead>
                <tr>
                    <th>Asset Class</th>
                    <th>Planned Maintenance Cost</th>
                    <th>Unplanned Repair Cost</th>
                    <th>Hourly Production Loss Rate</th>
                    <th>Unplanned Downtime</th>
                    <th>ROM Ratio</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>6-Axis Robot (M3)</strong></td>
                    <td>₹18,000</td>
                    <td>₹2,10,000</td>
                    <td>₹80,000 / hr</td>
                    <td>6.0 hrs</td>
                    <td class="roi" style="color: #10b981; font-weight: bold;">3,733%</td>
                </tr>
                <tr>
                    <td><strong>Injection Molder (M2)</strong></td>
                    <td>₹25,000</td>
                    <td>₹2,40,000</td>
                    <td>₹80,000 / hr</td>
                    <td>6.0 hrs</td>
                    <td class="roi" style="color: #10b981; font-weight: bold;">2,780%</td>
                </tr>
                <tr>
                    <td><strong>CNC Mill (M1)</strong></td>
                    <td>₹15,000</td>
                    <td>₹1,80,000</td>
                    <td>₹60,000 / hr</td>
                    <td>5.0 hrs</td>
                    <td class="roi" style="color: #10b981; font-weight: bold;">3,100%</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Section 6: AI Recommendation & Decision Basis -->
    <div class="section">
        <h2>6. AI Recommendation & Decision Basis</h2>
        <p>Every operational decision generated by the system incorporates multi-criteria optimization: machine telemetry, failure probability, production schedules, machine criticality, spare parts availability, and production loss rates. Recommendations are locked until physical validation is completed by a maintenance engineer to ensure physical credibility.</p>
    </div>

    <!-- Section 7: Deployment Readiness -->
    <div class="section">
        <h2>7. Deployment Readiness</h2>
        <p><strong>Prototype Maturity:</strong> Current demonstration runs on simulated factory telemetry. Production deployments support connections to local PLCs, SCADA networks, OPC-UA protocols, MQTT streams, SAP PM, IBM Maximo, and NVIDIA Jetson hardware acceleration blocks.</p>
    </div>

    <div style="margin-top: 50px; text-align: center; color: #9ca3af; font-size: 11px; border-top: 1px solid #f3f4f6; padding-top: 15px; font-family: monospace; line-height: 1.6;">
        Generated by EdgeTwin AI<br>
        Autonomous Factory Decision Intelligence Platform
    </div>
</body>
</html>
"""
    return html

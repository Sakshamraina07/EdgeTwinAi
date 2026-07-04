# State-Aware AI Factory Copilot Engine
# Processes text queries and retrieves live digital twin context to answer

import re
from datetime import datetime
from backend.database import get_financial_summary, get_maintenance_schedule
from backend.decision_engine import calculate_recommendation_roi, run_what_if_simulation

MACHINE_MAP = {
    "1": "M1", "cnc": "M1", "mill": "M1", "m1": "M1",
    "2": "M2", "molder": "M2", "injection": "M2", "m2": "M2",
    "3": "M3", "robot": "M3", "arm": "M3", "m3": "M3",
    "4": "M4", "compressor": "M4", "air": "M4", "m4": "M4",
    "5": "M5", "conveyor": "M5", "smart": "M5", "m5": "M5",
    "6": "M6", "press": "M6", "hydraulic": "M6", "m6": "M6"
}

MACHINE_NAMES = {
    "M1": "CNC Mill (M1)",
    "M2": "Injection Molder (M2)",
    "M3": "6-Axis Robot Arm (M3)",
    "M4": "Air Compressor (M4)",
    "M5": "Smart Conveyor (M5)",
    "M6": "Hydraulic Press (M6)"
}

def respond_to_copilot_query(query, machines_status):
    """
    Parses user query, detects intent, extracts machine entities,
    and returns a highly specific, context-aware markdown response.
    """
    q = query.lower()
    
    # Intent 1: Check specific machine parameters or why it is overheating/warning
    if any(k in q for k in ["why", "overheat", "hot", "problem", "issue", "status", "health"]) and any(k in q for k in MACHINE_MAP):
        # Extract machine ID
        target_machine = None
        for key, val in MACHINE_MAP.items():
            if key in q:
                target_machine = val
                break
                
        if target_machine and target_machine in machines_status:
            status = machines_status[target_machine]
            metrics = status.get("metrics", {})
            ai_pred = status.get("ai_prediction", {})
            name = MACHINE_NAMES[target_machine]
            
            temp = metrics.get("temperature", 0)
            vib = metrics.get("vibration", 0)
            load = metrics.get("load", 0)
            prob = ai_pred.get("failure_probability", 0)
            rul = ai_pred.get("rul_hours", 0)
            
            roi = calculate_recommendation_roi(target_machine, prob)
            net_savings = roi.get("net_savings", 0)
            
            response = f"### 🔍 Diagnostics for **{name}**\n\n"
            response += f"**Current State:**\n"
            response += f"- **Health Score:** `{status.get('health_score')}%` ({status.get('status').upper()})\n"
            response += f"- **Temperature:** `{temp}°C` | **Vibration:** `{vib} mm/s`\n"
            response += f"- **Operating Load:** `{load}%` | **Running Hours:** `{status.get('runtime_hours')} hrs`\n\n"
            
            response += f"**Edge AI Analysis:**\n"
            response += f"- **Prediction Confidence:** `{prob}%` probability of suspected degradation.\n"
            response += f"- **Remaining Useful Life (RUL):** `{rul} hours` remaining.\n"
            response += f"- **XAI Focus:** {ai_pred.get('explanation')}\n\n"
            
            if prob > 35:
                response += f"💡 **Executive Recommendation:**\n"
                response += f"Schedule preventive service immediately. Doing so will cost **₹{roi.get('planned_maintenance_cost'):,}**, "
                response += f"but prevents a major failure cost of **₹{roi.get('estimated_failure_repair_cost'):,}** and **₹{roi.get('expected_production_loss'):,}** in lost output.\n"
                response += f"**Validated Business Impact:** Savings of **₹{net_savings:,}** (ROM: `{roi.get('return_on_maintenance')}%`)."
            else:
                response += f"💡 **Executive Recommendation:**\n"
                response += "No immediate maintenance is required. Keep running normal operations. Energy efficiency is currently stable."
                
            return response
            
    # Intent 2: Which machine should be repaired/serviced first?
    if any(k in q for k in ["repair", "service", "fix", "first", "prioritize", "critical", "worst"]):
        # Sort machines by failure probability
        sorted_machines = sorted(
            [(mid, mdata) for mid, mdata in machines_status.items()],
            key=lambda x: x[1].get("ai_prediction", {}).get("failure_probability", 0.0),
            reverse=True
        )
        
        highest_risk_mid, highest_risk_mdata = sorted_machines[0]
        prob = highest_risk_mdata.get("ai_prediction", {}).get("failure_probability", 0.0)
        rul = highest_risk_mdata.get("ai_prediction", {}).get("rul_hours", 200)
        
        response = "### 🛠️ Maintenance Priority Recommendation\n\n"
        response += f"Our local Edge AI suggests servicing **{MACHINE_NAMES[highest_risk_mid]}** first.\n\n"
        response += "**Risk Summary:**\n"
        
        for mid, mdata in sorted_machines:
            mprob = mdata.get("ai_prediction", {}).get("failure_probability", 0.0)
            mrul = mdata.get("ai_prediction", {}).get("rul_hours", 200)
            mstatus = mdata.get("status")
            status_emoji = "🔴" if mstatus == "critical" else ("🟡" if mstatus == "warning" else "🟢")
            response += f"- {status_emoji} **{MACHINE_NAMES[mid]}**: Prediction Confidence `{mprob}%` | RUL `{mrul} hrs`\n"
            
        roi = calculate_recommendation_roi(highest_risk_mid, prob)
        response += f"\n**Urgent Action ROI Details ({highest_risk_mid}):**\n"
        response += f"- **Planned Service Cost:** ₹{roi.get('planned_maintenance_cost'):,}\n"
        response += f"- **Unplanned Failure Avoided:** ₹{roi.get('estimated_failure_repair_cost'):,}\n"
        response += f"- **Production Loss Avoided:** ₹{roi.get('expected_production_loss'):,}\n"
        response += f"- 💰 **Validated Business Impact (Savings):** **₹{roi.get('net_savings'):,}**\n"
        response += f"- **Return on Maintenance (ROM):** `{roi.get('return_on_maintenance')}%`"
        
        return response
        
    # Intent 3: Show energy inefficiency / power waste / opportunities
    if any(k in q for k in ["energy", "inefficient", "waste", "power", "opportunity", "save"]):
        # Find machines with highest energy inefficiency
        sorted_ineff = sorted(
            [(mid, mdata) for mid, mdata in machines_status.items()],
            key=lambda x: x[1].get("ai_prediction", {}).get("energy_inefficiency", 0.0),
            reverse=True
        )
        
        response = "### ⚡ Energy & Efficiency Optimization Insights\n\n"
        response += "Here are the top opportunities detected by the Edge AI to reduce power waste:\n\n"
        
        for mid, mdata in sorted_ineff:
            ineff = mdata.get("ai_prediction", {}).get("energy_inefficiency", 0.0)
            load = mdata.get("metrics", {}).get("load", 0.0)
            energy = mdata.get("metrics", {}).get("energy", 0.0)
            
            emoji = "⚠️" if ineff > 50 else "✅"
            response += f"{emoji} **{MACHINE_NAMES[mid]}**:\n"
            response += f"  - Inefficiency Index: `{ineff}%` | Current Load: `{load}%` | Power Consumption: `{energy} kWh`\n"
            
            if ineff > 50:
                response += f"  - *Reason:* High power draw relative to mechanical output. Check for friction build-up or motor stator misalignment.\n"
                response += f"  - *Decision:* Clean/lubricate spindle and re-align bearings. Estimated daily energy savings: **₹1,200**.\n"
            else:
                response += f"  - *Reason:* Performing within nominal power factor bands.\n"
                
        return response

    # Intent 4: Can production continue tomorrow / safety / shifts?
    if any(k in q for k in ["tomorrow", "continue", "production", "shift", "safe"]):
        critical_machines = [mid for mid, mdata in machines_status.items() if mdata.get("status") == "critical" or mdata.get("ai_prediction", {}).get("failure_probability", 0) > 70]
        
        response = "### 📅 Production Continuity Assessment\n\n"
        if not critical_machines:
            response += "🟢 **Safe to Continue:** Yes, production can continue for the next 24 hours (Day and Night shifts) without major interruption.\n\n"
            response += "All critical systems are running within nominal parameters. Overall factory health is high."
        else:
            names_list = ", ".join([MACHINE_NAMES[mid] for mid in critical_machines])
            response += f"🔴 **High Risk detected for upcoming shifts!**\n\n"
            response += f"We do **NOT** recommend running the next shifts at 100% capacity due to high failure probability on: **{names_list}**.\n\n"
            response += "**Mitigation Strategy:**\n"
            response += f"1. Reduce load on the affected machines to under **60%** to lower mechanical wear.\n"
            response += f"2. Dispatch technicians during the low-demand Night Shift (22:00 - 06:00).\n"
            response += f"3. Expected downtime for scheduled maintenance is only 25-90 minutes, avoiding a multi-hour unplanned shutdown."
            
        return response

    # Intent 5: How much money saved / financial summary / ROI?
    if any(k in q for k in ["saving", "money", "cost", "roi", "financial"]):
        summary = get_financial_summary()
        
        response = "### 📊 Executive Financial ROI Summary\n\n"
        response += "Here is the running track record of EdgeTwin AI's cost avoidance today:\n\n"
        response += f"- 💰 **Total Downtime Costs Prevented:** **₹{summary['cost_saved']:,}**\n"
        response += f"- ⏱️ **Unplanned Downtime Blocked:** `{summary['downtime_prevented']} hours`\n"
        response += f"- ⚡ **Energy Waste Recovered:** `{summary['energy_saved']} kWh`\n"
        response += f"- 📈 **Active Production Hours Saved:** `{summary['hours_recovered']} hours`\n\n"
        response += "Every scheduled repair prevents an unplanned failure costing up to 10x more. The AI continues to optimize maintenance windows to minimize order delays."
        return response

    # Intent 6: What-if simulation questions
    what_if_match = re.search(r"what if (?:we )?(?:stop|shut down|service) (?:machine )?([1-6]|m[1-6]) for (\d+) hours", q)
    if what_if_match:
        m_num = what_if_match.group(1)
        hours = int(what_if_match.group(2))
        m_id = "M" + m_num[-1]
        
        if m_id in machines_status:
            health = machines_status[m_id].get("health_score", 100)
            metrics = machines_status[m_id].get("metrics", {})
            sim_res = run_what_if_simulation(m_id, "shutdown", hours, health, metrics)
            
            response = f"### 🔮 What-If Simulation: Planned Shutdown of **{MACHINE_NAMES[m_id]}**\n\n"
            response += f"**Scenario:** Halt machine for `{hours} hours` today for preventive maintenance.\n\n"
            response += "**Projected Business Impacts:**\n"
            response += f"- **Production Loss:** ₹{sim_res['production_loss']:,} (Controlled, non-critical window)\n"
            response += f"- **Energy Saved:** `{sim_res['energy_saved_kwh']} kWh` (worth ₹{sim_res['energy_saved_cost']:,})\n"
            response += f"- **Risk Mitigation:** Drops post-maintenance failure risk to `2%`\n"
            response += f"- **Delivery Delay Risk:** `{sim_res['delivery_delay_risk']}`\n"
            response += f"- **Net Financial Impact:** ₹{sim_res['net_financial_impact']:,}\n\n"
            response += f"**Justification:** {sim_res['justification']}"
            return response
            
    # Intent 7: Default fallback
    response = "### 👋 EdgeTwin AI Copilot\n\n"
    response += "Hello! I am your local Edge Twin Copilot. I can query our machines' physical sensors, model predictions, and financial databases to recommend optimal decisions.\n\n"
    response += "Try asking me:\n"
    response += "- *Why is Machine 3 overheating?*\n"
    response += "- *Which machine should be repaired first?*\n"
    response += "- *Show the most energy inefficient machine.*\n"
    response += "- *Can production continue until tomorrow?*\n"
    response += "- *Show our total savings today.*\n"
    response += "- *What if we shut down Machine 1 for 4 hours?*"
    return response

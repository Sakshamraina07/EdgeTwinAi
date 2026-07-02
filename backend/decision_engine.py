# Decision Engine for EdgeTwin AI
# Computes Recommendation ROI and runs What-If Simulations

MACHINE_FINANCIAL_BASES = {
    "M1": {
        "name": "CNC Mill",
        "planned_maint_cost": 15000,
        "failure_repair_cost": 180000,
        "production_loss_per_hour": 60000,
        "downtime_hours_unplanned": 5.0,
        "power_kw": 15.0
    },
    "M2": {
        "name": "Injection Molder",
        "planned_maint_cost": 25000,
        "failure_repair_cost": 240000,
        "production_loss_per_hour": 80000,
        "downtime_hours_unplanned": 6.0,
        "power_kw": 25.0
    },
    "M3": {
        "name": "6-Axis Robot Arm",
        "planned_maint_cost": 18000,
        "failure_repair_cost": 210000,
        "production_loss_per_hour": 80000,
        "downtime_hours_unplanned": 6.0,
        "power_kw": 8.0
    },
    "M4": {
        "name": "Air Compressor",
        "planned_maint_cost": 10000,
        "failure_repair_cost": 110000,
        "production_loss_per_hour": 40000,
        "downtime_hours_unplanned": 4.0,
        "power_kw": 30.0
    },
    "M5": {
        "name": "Smart Conveyor",
        "planned_maint_cost": 8000,
        "failure_repair_cost": 90000,
        "production_loss_per_hour": 50000,
        "downtime_hours_unplanned": 3.0,
        "power_kw": 5.0
    },
    "M6": {
        "name": "Hydraulic Press",
        "planned_maint_cost": 20000,
        "failure_repair_cost": 220000,
        "production_loss_per_hour": 90000,
        "downtime_hours_unplanned": 5.0,
        "power_kw": 40.0
    }
}

def calculate_recommendation_roi(machine_id, failure_prob):
    """
    Calculates detailed financial figures for the AI Recommendation Economy Engine.
    Exposits:
    - Planned Maintenance Cost
    - Failure Repair Cost
    - Expected Production Loss if Ignored
    - Net Savings
    - Return on Maintenance (ROM %)
    """
    base = MACHINE_FINANCIAL_BASES.get(machine_id)
    if not base:
        return {}
        
    prob_factor = failure_prob / 100.0
    
    # Costs
    maint_cost = base["planned_maint_cost"]
    failure_repair = base["failure_repair_cost"]
    
    # Expected production loss = prob * hours * rate
    prod_loss_rate = base["production_loss_per_hour"]
    downtime_hours = base["downtime_hours_unplanned"]
    raw_prod_loss = prod_loss_rate * downtime_hours
    
    expected_prod_loss = round(raw_prod_loss * prob_factor)
    expected_failure_cost = round(failure_repair * prob_factor)
    
    # Net savings if scheduled today = (Expected Failure Repair + Expected Production Loss) - Planned Maint
    net_savings = round((expected_failure_cost + expected_prod_loss) - maint_cost)
    net_savings = max(0, net_savings) # cannot save negative money
    
    # Return on Maintenance (ROM)
    rom = round((net_savings / maint_cost) * 100) if maint_cost > 0 else 0
    
    return {
        "machine_id": machine_id,
        "machine_name": base["name"],
        "planned_maintenance_cost": maint_cost,
        "estimated_failure_repair_cost": failure_repair,
        "expected_production_loss": expected_prod_loss,
        "net_savings": net_savings,
        "return_on_maintenance": rom,
        "priority": "HIGH" if failure_prob > 75 else ("MEDIUM" if failure_prob > 40 else "LOW")
    }

def run_what_if_simulation(machine_id, action, value, current_health_score, current_metrics):
    """
    Simulates operational what-if decisions and returns business & engineering outcomes.
    
    Actions:
    - 'postpone': delay maintenance by 'value' hours.
    - 'shutdown': perform planned shutdown for 'value' hours today.
    """
    base = MACHINE_FINANCIAL_BASES.get(machine_id)
    if not base:
        return {"error": "Invalid machine ID"}
        
    current_risk = 100.0 - current_health_score
    
    if action == "postpone":
        # Postpone maintenance by X hours
        hours_delayed = float(value)
        
        # Risk increases exponentially/linearly over time
        # E.g. risk grows 1.25% per hour delayed
        postponed_risk = min(99.5, current_risk + (hours_delayed * 1.3))
        failure_prob = postponed_risk
        
        # Energy consumption increases due to high friction & inefficiency
        # +0.15% per hour delayed
        additional_energy_pct = min(15.0, round(hours_delayed * 0.15, 1))
        
        # Production delay = failure risk * unplanned downtime
        expected_downtime_hours = round((failure_prob / 100.0) * base["downtime_hours_unplanned"], 1)
        
        # Expected financial loss
        # Failure repair cost + Production loss from downtime
        total_failure_consequence = base["failure_repair_cost"] + (base["production_loss_per_hour"] * base["downtime_hours_unplanned"])
        expected_financial_loss = round((failure_prob / 100.0) * total_failure_consequence)
        
        # Delivery delay severity
        delivery_delay = "LOW"
        if hours_delayed > 48:
            delivery_delay = "HIGH" if failure_prob > 80 else "MEDIUM"
        elif hours_delayed > 24:
            delivery_delay = "MEDIUM"
            
        justification = (
            f"Postponing maintenance by {hours_delayed} hours increases failure risk to {failure_prob:.0f}%. "
            f"This adds a projected ₹{expected_financial_loss:,} in potential unplanned repair and production losses, "
            f"along with {additional_energy_pct}% extra energy waste due to deteriorating mechanical components."
        )
            
        return {
            "action": "postpone",
            "hours": hours_delayed,
            "failure_risk": round(failure_prob, 1),
            "additional_energy_consumption_pct": additional_energy_pct,
            "expected_downtime_hours": expected_downtime_hours,
            "delivery_delay_risk": delivery_delay,
            "estimated_financial_loss": expected_financial_loss,
            "justification": justification
        }
        
    elif action == "shutdown":
        # Shut down machine for maintenance today for Y hours
        shutdown_hours = float(value)
        
        # Planned shutdown is controlled. Hourly loss rate is lower because:
        # 1. Nearby machines run load balancing / buffering.
        # 2. Production is scheduled/routed around this machine.
        planned_loss_rate = base["production_loss_per_hour"] * 0.35 # 65% reduction in impact!
        production_loss = round(planned_loss_rate * shutdown_hours)
        
        # Energy SAVED: machine is completely off, so we save its baseline draw!
        # kW rating * hours * average cost per kWh (e.g. ₹10 per kWh)
        energy_saved_kwh = base["power_kw"] * shutdown_hours
        energy_saved_cost = round(energy_saved_kwh * 10) # ₹10 per kWh
        
        # Post-maintenance failure risk goes down to a nominal 2%
        post_risk = 2.0
        
        # Delivery delay is negligible since it is short and scheduled
        delivery_delay = "LOW" if shutdown_hours > 4 else "NONE"
        
        total_planned_cost = base["planned_maint_cost"] + production_loss
        net_financial_impact = total_planned_cost - energy_saved_cost
        
        justification = (
            f"A controlled {shutdown_hours}-hour shutdown prevents a sudden failure. "
            f"Planned production loss is minimized to ₹{production_loss:,} (compared to ₹{(base['production_loss_per_hour'] * base['downtime_hours_unplanned']):,} if it fails). "
            f"We also save {energy_saved_kwh:.1f} kWh of electricity, worth ₹{energy_saved_cost:,}."
        )
        
        return {
            "action": "shutdown",
            "hours": shutdown_hours,
            "failure_risk": post_risk,
            "energy_saved_kwh": round(energy_saved_kwh, 1),
            "energy_saved_cost": energy_saved_cost,
            "production_loss": production_loss,
            "net_financial_impact": net_financial_impact,
            "delivery_delay_risk": delivery_delay,
            "justification": justification
        }
        
    return {"error": "Unknown action"}

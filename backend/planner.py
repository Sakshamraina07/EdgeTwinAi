# Production-Aware Maintenance Planner
# Schedules maintenance based on RUL, shift demands, engineer skills, and parts

from datetime import datetime, timedelta
import random

# Engineers database with specialties and shift schedules
ENGINEERS = [
    {"name": "Rajesh Kumar", "specialty": "Mechanical & Hydraulics", "shifts": ["A", "B"]},
    {"name": "Amit Sharma", "specialty": "Electrical & Robotics", "shifts": ["B", "C"]},
    {"name": "Vikram Singh", "specialty": "Pneumatics & Conveyors", "shifts": ["A", "C"]}
]

# Required spare parts mapping
SPARE_PARTS = {
    "M1": "Spindle Bearing Kit & Seals",
    "M2": "High-Temp Heating Band & Valves",
    "M3": "Joint-3 Harmonic Drive Gearset & Grease",
    "M4": "Air Filter Cartridge & Separator Kit",
    "M5": "Heavy-Duty V-Drive Belt & Pulley",
    "M6": "Proportional Pressure Valve & Oil Filter"
}

MACHINE_NAMES = {
    "M1": "CNC Mill",
    "M2": "Injection Molder",
    "M3": "6-Axis Robot Arm",
    "M4": "Air Compressor",
    "M5": "Smart Conveyor",
    "M6": "Hydraulic Press"
}

def generate_optimized_schedule(machines_status):
    """
    Given the current live health and RUL of all machines,
    automatically schedules maintenance slots over the next 3 days.
    
    Rules:
    - Sorts machines by urgency (lowest RUL / highest failure probability).
    - Machines with probability > 40% need maintenance scheduled.
    - Lowers business impact by scheduling during low-demand night shifts (Shift C: 22:00 - 06:00) 
      unless the RUL is under 12 hours, which forces scheduling in the next immediate slot.
    - Matches the machine needs with engineer specialties.
    """
    schedule = []
    
    # Sort machines by failure probability descending
    urgency_list = []
    for machine_id, data in machines_status.items():
        prob = data.get("failure_probability", 0.0)
        rul = data.get("rul_hours", 200.0)
        
        # Determine if it needs service (prob > 35% or RUL < 72 hours)
        if prob > 35.0 or rul < 72.0:
            urgency_list.append({
                "machine_id": machine_id,
                "name": MACHINE_NAMES.get(machine_id, "Machine"),
                "failure_probability": prob,
                "rul_hours": rul,
                "urgency": 100.0 - rul # higher means more urgent
            })
            
    # Sort by urgency
    urgency_list.sort(key=lambda x: x["urgency"], reverse=True)
    
    # Generate schedule starting from current time
    base_time = datetime.now()
    # Round base time to nearest hour
    base_time = base_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    scheduled_slots = [] # list of (start_time, end_time) to avoid overlapping engineers/machines
    
    for item in urgency_list:
        machine_id = item["machine_id"]
        rul = item["rul_hours"]
        prob = item["failure_probability"]
        
        # Decide duration
        duration_mins = 45 if machine_id in ["M4", "M5"] else (90 if machine_id in ["M1", "M6"] else 120)
        
        # Find best engineer
        assigned_eng = None
        if machine_id in ["M3", "M2"]: # Robotics & Electrical
            assigned_eng = next((e for e in ENGINEERS if "Robotics" in e["specialty"] or "Electrical" in e["specialty"]), ENGINEERS[0])
        elif machine_id in ["M1", "M6"]: # Mechanical & Hydraulics
            assigned_eng = next((e for e in ENGINEERS if "Mechanical" in e["specialty"]), ENGINEERS[0])
        else: # Generalist
            assigned_eng = next((e for e in ENGINEERS if "Conveyors" in e["specialty"] or "Pneumatics" in e["specialty"]), ENGINEERS[2])
            
        # Determine schedule time
        scheduled_time = None
        
        # If critical (RUL < 12 hours), schedule in the next immediate available hour
        if rul < 12.0:
            candidate_time = base_time
            # Ensure we don't overlap on this machine
            while any(abs((c - candidate_time).total_seconds()) < 7200 for c in scheduled_slots):
                candidate_time += timedelta(hours=2)
            scheduled_time = candidate_time
            justification = f"Emergency immediate dispatch due to critical Remaining Useful Life (RUL: {rul} hrs)."
            priority = "CRITICAL"
        else:
            # Production-Aware: schedule during the night shift (22:00 - 06:00) when production load is low
            # Try next 3 nights
            found = False
            for day in range(3):
                # Target night shift: 22:00 of day D to 06:00 of day D+1
                night_start = (base_time + timedelta(days=day)).replace(hour=22, minute=0)
                
                # Check 22:00, 00:00, 02:00, 04:00 slots
                for hour_offset in [0, 2, 4]:
                    slot_time = night_start + timedelta(hours=hour_offset)
                    # Check if slot is in future and doesn't overlap
                    if slot_time > base_time and not any(abs((c - slot_time).total_seconds()) < 7200 for c in scheduled_slots):
                        scheduled_time = slot_time
                        found = True
                        break
                if found:
                    break
            
            if not scheduled_time:
                # Fallback to next morning
                scheduled_time = base_time + timedelta(days=1, hours=2)
                
            justification = f"Optimized for low-load night shift to protect day delivery targets."
            priority = "HIGH" if prob > 70 else "MEDIUM"
            
        # Add to scheduled slots tracker
        scheduled_slots.append(scheduled_time)
        
        # Spare parts needed
        parts = SPARE_PARTS.get(machine_id, "Standard Maintenance Kit")
        
        schedule.append({
            "machine_id": machine_id,
            "machine_name": item["name"],
            "failure_probability": prob,
            "rul_hours": rul,
            "scheduled_time": scheduled_time.isoformat(),
            "duration_mins": duration_mins,
            "required_parts": parts,
            "assigned_engineer": assigned_eng["name"],
            "priority": priority,
            "justification": justification
        })
        
    return schedule

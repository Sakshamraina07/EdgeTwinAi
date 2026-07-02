# Factory Telemetry Simulator for EdgeTwin AI
import time
import random
import threading
from datetime import datetime
from backend.database import add_incident, init_db, get_db_connection
from backend.ai_model import predict_machine_health

# Global state of the factory
LATEST_DATA = {}
state_lock = threading.Lock()

# Normal operating parameters baseline
NOMINAL_METRICS = {
    "M1": {"temperature": 42.0, "vibration": 1.2, "load": 70.0, "rpm": 2200.0, "energy": 14.5},
    "M2": {"temperature": 225.0, "vibration": 0.6, "load": 80.0, "pressure": 118.0, "energy": 24.2},
    "M3": {"temperature": 38.0, "vibration": 0.7, "load": 55.0, "joint_load": 52.0, "energy": 7.8},
    "M4": {"temperature": 53.0, "vibration": 1.4, "load": 60.0, "pressure": 7.2, "energy": 28.5},
    "M5": {"temperature": 35.0, "vibration": 0.5, "load": 50.0, "tension": 98.0, "energy": 4.8},
    "M6": {"temperature": 48.0, "vibration": 1.1, "load": 75.0, "pressure": 240.0, "energy": 38.2}
}

def initialize_simulator():
    """Seeds the initial digital twin status for all 6 machines."""
    global LATEST_DATA
    init_db()
    
    with state_lock:
        for mid in NOMINAL_METRICS.keys():
            base = NOMINAL_METRICS[mid].copy()
            runtime = random.randint(80, 150)
            
            # Predict initial healthy state
            ai_pred = predict_machine_health(mid, base, runtime)
            
            LATEST_DATA[mid] = {
                "machine_id": mid,
                "health_score": 98,
                "runtime_hours": runtime,
                "status": "healthy",
                "metrics": base,
                "ai_prediction": ai_pred,
                "anomaly_active": False,
                "anomaly_type": None,
                "anomaly_start_time": None
            }

def update_simulation_tick():
    """Runs a single step of the simulator, updating metrics and running Edge AI."""
    global LATEST_DATA
    with state_lock:
        for mid in LATEST_DATA.keys():
            mdata = LATEST_DATA[mid]
            base_metrics = NOMINAL_METRICS[mid]
            
            # 1. Update running time
            mdata["runtime_hours"] += round(0.01, 2) # simulate slight wear accretion
            
            # 2. Simulate raw telemetry metrics with random noise
            curr_metrics = mdata["metrics"]
            
            if not mdata["anomaly_active"]:
                # Normal fluctuations (Gaussian-like noise)
                curr_metrics["temperature"] = round(base_metrics["temperature"] + random.uniform(-1.0, 1.0), 1)
                curr_metrics["vibration"] = round(base_metrics["vibration"] + random.uniform(-0.1, 0.1), 2)
                curr_metrics["load"] = round(base_metrics["load"] + random.uniform(-3.0, 3.0), 1)
                curr_metrics["energy"] = round(base_metrics["energy"] + random.uniform(-0.5, 0.5), 2)
                
                # Machine-specific normal metrics
                if mid == "M1":
                    curr_metrics["rpm"] = round(base_metrics["rpm"] + random.uniform(-50, 50))
                elif mid == "M2":
                    curr_metrics["pressure"] = round(base_metrics["pressure"] + random.uniform(-2.0, 2.0), 1)
                elif mid == "M3":
                    curr_metrics["joint_load"] = round(base_metrics["joint_load"] + random.uniform(-2.0, 2.0), 1)
                elif mid == "M4":
                    curr_metrics["pressure"] = round(base_metrics["pressure"] + random.uniform(-0.1, 0.1), 2)
                elif mid == "M5":
                    curr_metrics["tension"] = round(base_metrics["tension"] + random.uniform(-2.0, 2.0), 1)
                elif mid == "M6":
                    curr_metrics["pressure"] = round(base_metrics["pressure"] + random.uniform(-4.0, 4.0), 1)
            else:
                # Anomaly is active, ramp up the metrics to simulate wear failure!
                anom_type = mdata["anomaly_type"]
                
                # Temperature thermal ramp
                curr_metrics["temperature"] = round(curr_metrics["temperature"] + random.uniform(0.8, 1.8), 1)
                # Load remains elevated
                curr_metrics["load"] = round(min(98.0, curr_metrics["load"] + random.uniform(0.5, 2.0)), 1)
                
                if anom_type == "bearing_vibration":
                    curr_metrics["vibration"] = round(curr_metrics["vibration"] + random.uniform(0.08, 0.15), 2)
                    curr_metrics["energy"] = round(curr_metrics["energy"] + random.uniform(0.2, 0.6), 2) # extra energy friction
                elif anom_type == "pressure_leak":
                    curr_metrics["vibration"] = round(curr_metrics["vibration"] + random.uniform(0.02, 0.05), 2)
                    # For M4/M6 pressure decreases or fluctuates wildly
                    if "pressure" in curr_metrics:
                        curr_metrics["pressure"] = round(max(3.0, curr_metrics["pressure"] - random.uniform(0.1, 0.2)), 2)
                    curr_metrics["energy"] = round(curr_metrics["energy"] + random.uniform(0.4, 0.8), 2) # compressor working harder
                elif anom_type == "tension_stress":
                    curr_metrics["vibration"] = round(curr_metrics["vibration"] + random.uniform(0.05, 0.1), 2)
                    if "tension" in curr_metrics:
                        curr_metrics["tension"] = round(curr_metrics["tension"] + random.uniform(1.5, 3.5), 1)
                    curr_metrics["energy"] = round(curr_metrics["energy"] + random.uniform(0.3, 0.5), 2)
                else: # General mechanical wear
                    curr_metrics["vibration"] = round(curr_metrics["vibration"] + random.uniform(0.04, 0.08), 2)
                    curr_metrics["energy"] = round(curr_metrics["energy"] + random.uniform(0.1, 0.4), 2)
                    
            # 3. Call local Edge AI Prediction module
            ai_pred = predict_machine_health(mid, curr_metrics, mdata["runtime_hours"])
            mdata["ai_prediction"] = ai_pred
            
            # 4. Map health probability to status color levels
            prob = ai_pred["failure_probability"]
            mdata["health_score"] = round(100.0 - prob)
            
            old_status = mdata["status"]
            if prob > 75.0:
                mdata["status"] = "critical"
            elif prob > 35.0:
                mdata["status"] = "warning"
            else:
                mdata["status"] = "healthy"
                
            # If status transitioned to warning/critical and anomaly was active, log to DB
            if old_status == "healthy" and mdata["status"] in ["warning", "critical"]:
                # Log incident to Database
                anom_desc = mdata["anomaly_type"].replace("_", " ").title() if mdata["anomaly_active"] else "Mechanical Wear"
                add_incident(
                    machine_id=mid,
                    incident_type=anom_desc,
                    severity=mdata["status"],
                    metrics=curr_metrics,
                    action_taken="AI Recommendation: Replace faulty component immediately."
                )

def trigger_anomaly(machine_id, anomaly_type):
    """Manually or automatically starts an anomaly ramp on a machine."""
    global LATEST_DATA
    with state_lock:
        if machine_id in LATEST_DATA:
            mdata = LATEST_DATA[machine_id]
            mdata["anomaly_active"] = True
            mdata["anomaly_type"] = anomaly_type
            mdata["anomaly_start_time"] = time.time()
            return True
    return False

def resolve_machine_maintenance(machine_id):
    """Resets machine back to 100% health, turning off active anomalies."""
    global LATEST_DATA
    with state_lock:
        if machine_id in LATEST_DATA:
            mdata = LATEST_DATA[machine_id]
            base_metrics = NOMINAL_METRICS[machine_id].copy()
            
            # Reset simulator variables
            mdata["anomaly_active"] = False
            mdata["anomaly_type"] = None
            mdata["anomaly_start_time"] = None
            mdata["health_score"] = 98
            mdata["status"] = "healthy"
            mdata["metrics"] = base_metrics
            mdata["ai_prediction"] = predict_machine_health(machine_id, base_metrics, mdata["runtime_hours"])
            
            # Resolve database active incidents
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE incidents 
                SET resolved = 1, resolution_time = ?, action_taken = 'Completed Scheduled Maintenance / Spare Parts Replaced' 
                WHERE machine_id = ? AND resolved = 0
            """, (datetime.now().isoformat(), machine_id))
            conn.commit()
            conn.close()
            return True
    return False

def background_simulator_loop(stop_event):
    """Continuous thread loop ticking every 2 seconds."""
    initialize_simulator()
    
    tick_count = 0
    while not stop_event.is_set():
        update_simulation_tick()
        tick_count += 1
        
        # Every 45 ticks (90 seconds), randomly trigger an anomaly on a healthy machine to show live tracking!
        if tick_count % 45 == 0:
            healthy_mids = [
                mid for mid, data in LATEST_DATA.items() 
                if not data["anomaly_active"] and data["status"] == "healthy"
            ]
            if healthy_mids:
                target_mid = random.choice(healthy_mids)
                # Pick appropriate anomaly
                anom_type = "bearing_vibration"
                if target_mid in ["M2", "M4", "M6"]:
                    anom_type = "pressure_leak"
                elif target_mid == "M5":
                    anom_type = "tension_stress"
                    
                trigger_anomaly(target_mid, anom_type)
                
        time.sleep(2.0)

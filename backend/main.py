import asyncio
import threading
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

# Import local backend modules
from backend.database import (
    init_db, get_all_incidents, get_active_incidents, 
    get_maintenance_schedule, get_financial_summary, 
    update_maintenance_status, clear_future_schedule, add_maintenance_slot
)
from backend.simulator import (
    LATEST_DATA, background_simulator_loop, trigger_anomaly, 
    resolve_machine_maintenance, state_lock
)
from backend.decision_engine import run_what_if_simulation, calculate_recommendation_roi
from backend.planner import generate_optimized_schedule
from backend.copilot import respond_to_copilot_query
from backend.report import generate_html_report

# FastAPI Application
app = FastAPI(title="EdgeTwin AI Backend", description="Edge Digital Twin & Decision Intelligence API")

# Allow CORS for dev environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background thread control variables
stop_event = threading.Event()
simulator_thread = None

# Active WebSocket connections list
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Remove dead connection
                pass

manager = ConnectionManager()

# Lifecycle Management
@app.on_event("startup")
def startup_event():
    global simulator_thread
    print("Initializing SQLite Database...")
    init_db()
    
    print("Starting background factory simulator thread...")
    stop_event.clear()
    simulator_thread = threading.Thread(target=background_simulator_loop, args=(stop_event,), daemon=True)
    simulator_thread.start()
    
    # Run a helper task to broadcast telemetry to WS clients every 2 seconds
    asyncio.create_task(websocket_broadcast_loop())

async def websocket_broadcast_loop():
    while not stop_event.is_set():
        await asyncio.sleep(2.0)
        if manager.active_connections:
            with state_lock:
                data_copy = {mid: val.copy() for mid, val in LATEST_DATA.items()}
                # Remove thread object elements before JSON serializing
                for m in data_copy.values():
                    m.pop("anomaly_start_time", None)
            
            # Pack telemetry and financials
            payload = {
                "telemetry": data_copy,
                "financials": get_financial_summary()
            }
            await manager.broadcast(json.dumps(payload))

@app.on_event("shutdown")
def shutdown_event():
    print("Stopping simulator background thread...")
    stop_event.set()
    if simulator_thread:
        simulator_thread.join(timeout=3.0)

# Request Models
class SimulateRequest(BaseModel):
    machine_id: str
    action: str
    value: float

class CopilotRequest(BaseModel):
    query: str

class AnomalyRequest(BaseModel):
    machine_id: str
    anomaly_type: str

class MaintenanceStatusRequest(BaseModel):
    slot_id: int
    status: str

# --- API Endpoints ---

@app.get("/api/machines")
def get_machines():
    """Gets the current status and AI predictions of all machines."""
    with state_lock:
        data_copy = {mid: val.copy() for mid, val in LATEST_DATA.items()}
        for m in data_copy.values():
            m.pop("anomaly_start_time", None)
    return data_copy

@app.get("/api/financials")
def get_financials():
    """Retrieves executive financial savings and prevented downtime."""
    return get_financial_summary()

@app.get("/api/incidents")
def get_incidents(all_logs: bool = False):
    """Retrieves list of active incidents or full history."""
    if all_logs:
        return get_all_incidents()
    return get_active_incidents()

@app.get("/api/maintenance")
def get_maintenance():
    """Retrieves current maintenance tasks and schedules."""
    return get_maintenance_schedule()

@app.post("/api/maintenance/optimize")
def optimize_maintenance():
    """Triggers the production-aware planner to recompute schedules."""
    # Get current machine statuses
    with state_lock:
        data_copy = {mid: val.copy() for mid, val in LATEST_DATA.items()}
        
    schedule = generate_optimized_schedule(data_copy)
    
    # Clear current pending schedules from db and add new optimized ones
    clear_future_schedule()
    for slot in schedule:
        add_maintenance_slot(
            machine_id=slot["machine_id"],
            scheduled_time=slot["scheduled_time"],
            duration_mins=slot["duration_mins"],
            required_parts=slot["required_parts"],
            assigned_engineer=slot["assigned_engineer"],
            priority=slot["priority"]
        )
        
    return {"message": "Schedule optimized successfully", "schedule": schedule}

@app.post("/api/maintenance/status")
def change_maintenance_status(req: MaintenanceStatusRequest):
    """Updates status of a maintenance task. If marked 'completed', it resets machine metrics."""
    # If completed, reset the machine parameters to healthy
    if req.status == "completed":
        # Get machine_id associated with this slot
        schedule = get_maintenance_schedule()
        target_slot = next((s for s in schedule if s["id"] == req.slot_id), None)
        if target_slot:
            resolve_machine_maintenance(target_slot["machine_id"])
            
    update_maintenance_status(req.slot_id, req.status)
    return {"message": f"Slot {req.slot_id} updated to {req.status}"}

@app.post("/api/simulate")
def simulate_outcome(req: SimulateRequest):
    """Runs a What-If simulation to estimate costs of postponing or planned shutdown."""
    with state_lock:
        if req.machine_id not in LATEST_DATA:
            raise HTTPException(status_code=404, detail="Machine not found")
        mdata = LATEST_DATA[req.machine_id]
        
    health = mdata["health_score"]
    metrics = mdata["metrics"]
    
    res = run_what_if_simulation(req.machine_id, req.action, req.value, health, metrics)
    return res

@app.post("/api/copilot")
def query_copilot(req: CopilotRequest):
    """Handles text questions about machine diagnostics, ROI, and efficiency."""
    with state_lock:
        data_copy = {mid: val.copy() for mid, val in LATEST_DATA.items()}
    answer = respond_to_copilot_query(req.query, data_copy)
    return {"query": req.query, "answer": answer}

@app.post("/api/inject-anomaly")
def inject_anomaly(req: AnomalyRequest):
    """Manually forces a machine to fail for demonstration purposes."""
    success = trigger_anomaly(req.machine_id, req.anomaly_type)
    if not success:
        raise HTTPException(status_code=404, detail="Machine not found")
    return {"message": f"Anomaly {req.anomaly_type} injected into {req.machine_id}"}

@app.post("/api/reset")
def reset_all_machines():
    """Resets all machinery nodes back to 100% health."""
    for mid in ["M1", "M2", "M3", "M4", "M5", "M6"]:
        resolve_machine_maintenance(mid)
    return {"message": "All machinery nodes reset to healthy"}

@app.get("/api/report")
def export_report():
    """Generates the HTML print/PDF-ready summary report."""
    with state_lock:
        data_copy = {mid: val.copy() for mid, val in LATEST_DATA.items()}
    html_content = generate_html_report(data_copy)
    return Response(content=html_content, media_type="text/html")

# --- WebSocket Route ---

@app.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial status right away
        with state_lock:
            data_copy = {mid: val.copy() for mid, val in LATEST_DATA.items()}
            for m in data_copy.values():
                m.pop("anomaly_start_time", None)
        
        initial_payload = {
            "telemetry": data_copy,
            "financials": get_financial_summary()
        }
        await websocket.send_text(json.dumps(initial_payload))
        
        while True:
            # Keep connection open. We can also handle requests from frontend here
            data = await websocket.receive_text()
            # Ignore client messages or handle ping/pong if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

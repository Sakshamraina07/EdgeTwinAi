import sqlite3
import os
import json
from datetime import datetime
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edgetwin.db")
db_lock = threading.Lock()

def get_db_connection():
    """Returns a thread-safe sqlite3 connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Incidents Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metrics_at_incident TEXT NOT NULL,
                action_taken TEXT,
                resolved INTEGER DEFAULT 0,
                resolution_time TEXT
            )
        """)
        
        # 2. Maintenance Schedule Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                duration_mins INTEGER NOT NULL,
                required_parts TEXT NOT NULL,
                assigned_engineer TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled'
            )
        """)
        
        # 3. Financial Impact / Running Stats Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cost_saved REAL DEFAULT 0,
                downtime_prevented_hours REAL DEFAULT 0,
                energy_saved_kwh REAL DEFAULT 0,
                production_hours_recovered REAL DEFAULT 0,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Check if financial summary seed exists, if not, create one
        cursor.execute("SELECT COUNT(*) FROM financials")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO financials (cost_saved, downtime_prevented_hours, energy_saved_kwh, production_hours_recovered, timestamp)
                VALUES (482000.0, 18.5, 342.0, 12.0, ?)
            """, (datetime.now().isoformat(),))
            
        conn.commit()
        conn.close()

# Database Helper CRUD functions
def add_incident(machine_id, incident_type, severity, metrics, action_taken=""):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO incidents (machine_id, type, severity, timestamp, metrics_at_incident, action_taken, resolved)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (machine_id, incident_type, severity, now_str, json.dumps(metrics), action_taken))
        conn.commit()
        incident_id = cursor.lastrowid
        conn.close()
        return incident_id

def get_active_incidents():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE resolved = 0 ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

def get_all_incidents(limit=50):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

def resolve_incident(incident_id, action_taken="Resolved"):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()
        cursor.execute("""
            UPDATE incidents 
            SET resolved = 1, resolution_time = ?, action_taken = ?
            WHERE id = ?
        """, (now_str, action_taken, incident_id))
        conn.commit()
        conn.close()

def get_maintenance_schedule():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM maintenance_schedule ORDER BY scheduled_time ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

def add_maintenance_slot(machine_id, scheduled_time, duration_mins, required_parts, assigned_engineer, priority, status='scheduled'):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO maintenance_schedule (machine_id, scheduled_time, duration_mins, required_parts, assigned_engineer, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (machine_id, scheduled_time, duration_mins, required_parts, assigned_engineer, priority, status))
        conn.commit()
        slot_id = cursor.lastrowid
        conn.close()
        return slot_id

def clear_future_schedule():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM maintenance_schedule WHERE status = 'scheduled'")
        conn.commit()
        conn.close()

def update_maintenance_status(slot_id, status):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE maintenance_schedule SET status = ? WHERE id = ?", (status, slot_id))
        
        # If completing, add to financials
        if status == 'completed':
            # Retrieve slot to find machine
            cursor.execute("SELECT * FROM maintenance_schedule WHERE id = ?", (slot_id,))
            slot = cursor.fetchone()
            if slot:
                # Add default savings based on completing maintenance
                # CNC Mill, Injection Molder etc. have different estimated failure costs
                savings_map = {
                    "M1": 250000, # CNC Mill
                    "M2": 320000, # Injection Molder
                    "M3": 672000, # Robot Arm (Our showcase example!)
                    "M4": 180000, # Air Compressor
                    "M5": 120000, # Conveyor
                    "M6": 290000  # Hydraulic Press
                }
                machine_id = slot["machine_id"]
                val = savings_map.get(machine_id, 150000)
                downtime_saved = 4.5
                energy_saved = 75.0
                hours_recovered = 3.0
                
                now_str = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO financials (cost_saved, downtime_prevented_hours, energy_saved_kwh, production_hours_recovered, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (val, downtime_saved, energy_saved, hours_recovered, now_str))
                
        conn.commit()
        conn.close()

def get_financial_summary():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                SUM(cost_saved) as total_cost_saved,
                SUM(downtime_prevented_hours) as total_downtime_prevented,
                SUM(energy_saved_kwh) as total_energy_saved,
                SUM(production_hours_recovered) as total_hours_recovered
            FROM financials
        """)
        row = cursor.fetchone()
        conn.close()
        
        if row and row['total_cost_saved'] is not None:
            return {
                "cost_saved": row['total_cost_saved'],
                "downtime_prevented": row['total_downtime_prevented'],
                "energy_saved": row['total_energy_saved'],
                "hours_recovered": row['total_hours_recovered']
            }
        else:
            return {
                "cost_saved": 0.0,
                "downtime_prevented": 0.0,
                "energy_saved": 0.0,
                "hours_recovered": 0.0
            }

def update_financials(cost_saved, downtime_prevented, energy_saved, hours_recovered):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO financials (cost_saved, downtime_prevented_hours, energy_saved_kwh, production_hours_recovered, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (cost_saved, downtime_prevented, energy_saved, hours_recovered, now_str))
        conn.commit()
        conn.close()

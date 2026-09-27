"""
models.py
Core data structures and database logic for the MMU Modern Parking System.

Data structures used:
- List of dicts: represents the fixed set of physical parking slots.
- Dict (hash map): tracks currently active vehicles, keyed by plate number,
  for O(1) lookup on exit instead of scanning every slot (O(n)).
- SQLite table: permanent record of every parking session (the "dynamic database").

Concurrency note: a threading.Lock guards slot/dict changes so two near-
simultaneous requests (e.g. two cars entering at once) can't both grab the
same slot or corrupt the active_vehicles map.
"""

import sqlite3
import os
import threading
import re
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "parking.db")

TOTAL_SLOTS = 20  # adjust to however many slots the lot has

# Fee brackets as given by the client, in (max_hours, fee) order.
# We check these in sequence and stop at the first bracket that fits.
FEE_BRACKETS = [
    (0.5, 0),     # up to 30 minutes: free
    (2, 50),      # up to 2 hours: Kshs. 50
    (4, 100),     # up to 4 hours: Kshs. 100
    (6, 300),     # up to 6 hours: Kshs. 300
]
OVER_LIMIT_FEE = 500  # anything beyond 6 hours

# Kenyan plates are typically 3 letters + 3 digits + 1 letter (e.g. KAA123B),
# but we accept a slightly looser pattern to avoid rejecting valid variants.
PLATE_PATTERN = re.compile(r'^[A-Z0-9]{4,10}$')


def is_valid_plate(plate_number):
    """Rejects empty, too short/long, or non-alphanumeric plate numbers."""
    return bool(PLATE_PATTERN.match(plate_number))


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates the sessions table if it doesn't exist yet."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            slot_id INTEGER NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            fee INTEGER,
            paid INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


class ParkingSystem:
    def __init__(self):
        # The list: fixed slots, each either free or occupied.
        self.slots = [{"slot_id": i, "occupied": False} for i in range(1, TOTAL_SLOTS + 1)]
        # The hash map: active vehicles, keyed by plate number.
        # value = {"slot_id": int, "entry_time": datetime, "db_id": int}
        self.active_vehicles = {}
        # Guards against two requests modifying slots/active_vehicles at once.
        self.lock = threading.Lock()
        init_db()

    def available_slots(self):
        """Returns list of free slot IDs — used for the visual display before entry."""
        return [s["slot_id"] for s in self.slots if not s["occupied"]]

    def _find_free_slot(self):
        for s in self.slots:
            if not s["occupied"]:
                return s
        return None

    def park_vehicle(self, plate_number):
        """Records a vehicle on arrival. Returns (success, message_or_slot_id)."""
        if not is_valid_plate(plate_number):
            return False, "Invalid plate number format."

        with self.lock:
            if plate_number in self.active_vehicles:
                return False, "Vehicle already parked."

            slot = self._find_free_slot()
            if slot is None:
                return False, "Parking full."

            slot["occupied"] = True
            entry_time = datetime.now()

            conn = get_connection()
            cur = conn.execute(
                "INSERT INTO sessions (plate_number, slot_id, entry_time) VALUES (?, ?, ?)",
                (plate_number, slot["slot_id"], entry_time.isoformat())
            )
            conn.commit()
            db_id = cur.lastrowid
            conn.close()

            self.active_vehicles[plate_number] = {
                "slot_id": slot["slot_id"],
                "entry_time": entry_time,
                "db_id": db_id
            }
            return True, slot["slot_id"]

    def _calculate_fee(self, hours):
        for max_hours, fee in FEE_BRACKETS:
            if hours <= max_hours:
                return fee
        return OVER_LIMIT_FEE

    def exit_vehicle(self, plate_number):
        """Calculates time/fee on exit, for DISPLAY only. Nothing is charged
        or finalized here — that only happens in confirm_payment, which
        recalculates the fee fresh rather than trusting anything the
        browser sends back."""
        if not is_valid_plate(plate_number):
            return False, "Invalid plate number format."

        record = self.active_vehicles.get(plate_number)
        if record is None:
            return False, "Vehicle not found in parking."

        exit_time = datetime.now()
        duration = exit_time - record["entry_time"]
        hours = duration.total_seconds() / 3600
        fee = self._calculate_fee(hours)

        return True, {
            "plate_number": plate_number,
            "slot_id": record["slot_id"],
            "duration_minutes": round(duration.total_seconds() / 60, 1),
            "fee": fee,
            "db_id": record["db_id"]
        }

    def confirm_payment(self, plate_number, db_id):
        """Called once payment is made — frees the slot and opens the barrier.

        Security note: the fee is recalculated here from the vehicle's real
        entry_time, rather than accepted from the form. A hidden form field
        can be edited in the browser before submitting, so the server must
        never trust a client-supplied price — it must always recompute the
        amount owed itself.
        """
        with self.lock:
            record = self.active_vehicles.get(plate_number)
            if record is None:
                return False, None

            exit_time = datetime.now()
            duration = exit_time - record["entry_time"]
            hours = duration.total_seconds() / 3600
            fee = self._calculate_fee(hours)  # recomputed server-side, not trusted from client

            for s in self.slots:
                if s["slot_id"] == record["slot_id"]:
                    s["occupied"] = False

            conn = get_connection()
            conn.execute(
                "UPDATE sessions SET exit_time = ?, fee = ?, paid = 1 WHERE id = ?",
                (exit_time.isoformat(), fee, db_id)
            )
            conn.commit()
            conn.close()

            del self.active_vehicles[plate_number]
            return True, fee

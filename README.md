nano README.md
# MMU Modern Parking System

A web-based parking management system built with Python (Flask) and SQLite, developed for MMU's Data Structures and Algorithms Task One.

## Scenario
The client wants a system where drivers can see available parking slots before entry, vehicles are recorded on arrival, and on exit the system calculates time spent and fee owed, opening the barrier once payment is confirmed.

## a) Algorithms

### 1. Slot Availability Display
START
FOR each slot in the slot list
IF slot is not occupied
ADD slot number to free_slots list
DISPLAY free_slots and total count
END
This runs every time the homepage loads, so drivers always see current availability before entering.

### 2. Vehicle Entry
START
INPUT plate_number
IF plate_number already in active_vehicles
REJECT — vehicle already parked
SEARCH slot list for first slot where occupied = False
IF no free slot found
REJECT — parking full
MARK that slot as occupied
RECORD entry_time = current time
INSERT (plate_number, slot_id, entry_time) into database
STORE plate_number, slot_id, entry_time in active_vehicles map
DISPLAY assigned slot number
END
### 3. Vehicle Exit — Fee Calculation
START
INPUT plate_number
LOOKUP plate_number in active_vehicles map
IF not found
REJECT — vehicle not recognized
CALCULATE duration = current time - entry_time
CONVERT duration to hours
IF hours <= 0.5:    fee = 0
ELSE IF hours <= 2:  fee = 50
ELSE IF hours <= 4:  fee = 100
ELSE IF hours <= 6:  fee = 300
ELSE:                fee = 500
DISPLAY duration and fee, awaiting payment
END
### 4. Payment & Barrier Control
START
INPUT confirmed payment for plate_number
MARK the vehicle's slot as unoccupied (increments available slots)
UPDATE database record: set exit_time, fee, paid = true
REMOVE plate_number from active_vehicles map
OPEN barrier (implicit: driver may now exit)
END
## b) Data Structures Used

| Structure | Used for | Why |
|---|---|---|
| **List** (of slot records) | The fixed set of physical parking slots | The number of physical slots is fixed and known in advance, so a list with direct index access is the natural fit — like a numbered noticeboard where each position represents one real bay. |
| **Dict / Hash map** | Currently active (parked) vehicles, keyed by plate number | On exit, the system must find a vehicle instantly rather than scanning every slot one by one. A hash map gives O(1) lookup by plate number — like a fast lookup book indexed by name instead of searching page by page. |
| **SQLite table** (the dynamic database) | Permanent log of every parking session, past and present | The list and dict only hold *current* state in memory and are lost if the app restarts. The database is the durable filing cabinet — every session (entry, exit, fee, payment status) is preserved for records and billing history. |

## c) Dynamic Database Design

**Table: `sessions`**

| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK, autoincrement) | Unique session record ID |
| plate_number | TEXT | Vehicle's number plate |
| slot_id | INTEGER | Which physical slot was used |
| entry_time | TEXT (ISO datetime) | When the vehicle arrived |
| exit_time | TEXT (ISO datetime, nullable) | When the vehicle left (null while still parked) |
| fee | INTEGER (nullable) | Amount charged, set once calculated |
| paid | INTEGER (0/1) | Whether payment was confirmed |

It's "dynamic" because a new row is created on every entry and updated on every exit — the table grows and changes continuously as vehicles come and go, while also preserving full history for reporting.

## Tech Stack
- Python 3, Flask (web framework)
- SQLite (persistent storage)
- HTML/Jinja2 templates (frontend)

## Author
Deborah — CIT-227-044/2025, MMU Department of Computer Science, Programme Software engineering
## Limitations & Future Improvements

This system meets the brief's requirements, but a few areas are worth noting as known limitations rather than oversights:

- **Concurrency:** A `threading.Lock` protects slot allocation and the active-vehicles map from race conditions (e.g. two cars entering at the exact same instant). SQLite itself has limited support for concurrent writes under heavy load — a production system would move to PostgreSQL or MySQL for better multi-user handling.
- **Payment validation:** The fee is recalculated server-side at the moment of payment confirmation, rather than trusting any value submitted from the browser — this closes a tampering gap where a hidden form field could otherwise be edited before submission.
- **Barrier hardware:** The barrier "opening" is currently simulated via a confirmation message. A real deployment would integrate with physical barrier hardware (e.g. via a serial/GPIO interface) triggered only after payment is verified.
- - **Automated tests:** A `pytest` suite (`test_parking.py`) covers plate validation, entry, duplicate/full rejection, exit fee calculation, and payment confirmation — run with `pytest test_parking.py -v`.
- **Single-lot scope:** The system currently models one parking lot with a fixed slot count. A multi-location version would need a `lots` table and slots scoped per lot.

## Complexity Notes

| Operation | Structure | Complexity | Why |
|---|---|---|---|
| Find a vehicle on exit | Dict (hash map) | O(1) average | Direct key lookup by plate number, instead of scanning every slot. |
| Find a free slot on entry | List scan | O(n) | Slots aren't naturally ordered by availability, so a full scan is used; acceptable at this scale (20 slots), but a free-slot queue could make this O(1) at larger scale. |
| Check slot availability for display | List comprehension | O(n) | Runs once per page load; fine at this scale, would need caching at very high traffic. |
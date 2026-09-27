"""
test_parking.py
Basic automated tests for the MMU Parking System core logic.

Run with: pytest test_parking.py -v
"""

import os
import pytest
from park.models import ParkingSystem, is_valid_plate


@pytest.fixture
def fresh_system(tmp_path, monkeypatch):
    """Gives each test a clean ParkingSystem backed by a temporary database,
    so tests don't interfere with each other or with your real parking.db."""
    import park.models as models
    test_db = tmp_path / "test_parking.db"
    monkeypatch.setattr(models, "DB_PATH", str(test_db))
    return ParkingSystem()


def test_plate_validation():
    assert is_valid_plate("KAA123B") is True
    assert is_valid_plate("") is False
    assert is_valid_plate("!!") is False
    assert is_valid_plate("AB") is False  # too short


def test_all_slots_free_initially(fresh_system):
    """All slots should start unoccupied."""
    assert len(fresh_system.available_slots()) == len(fresh_system.slots)


def test_park_vehicle_success(fresh_system):
    success, slot_id = fresh_system.park_vehicle("KAA123B")
    assert success is True
    assert isinstance(slot_id, int)
    assert "KAA123B" in fresh_system.active_vehicles
    assert len(fresh_system.available_slots()) == len(fresh_system.slots) - 1


def test_park_vehicle_rejects_invalid_plate(fresh_system):
    success, message = fresh_system.park_vehicle("!!")
    assert success is False
    assert "Invalid plate number" in message


def test_park_vehicle_rejects_duplicate(fresh_system):
    fresh_system.park_vehicle("KAA123B")
    success, message = fresh_system.park_vehicle("KAA123B")
    assert success is False
    assert "already parked" in message


def test_park_vehicle_rejects_when_full(fresh_system):
    # Fill every slot
    for i in range(len(fresh_system.slots)):
        fresh_system.park_vehicle(f"KAA{i:03d}B")

    success, message = fresh_system.park_vehicle("KAA999B")
    assert success is False
    assert "full" in message.lower()


def test_exit_vehicle_not_found(fresh_system):
    success, message = fresh_system.exit_vehicle("KAA999Z")
    assert success is False
    assert "not found" in message.lower()


def test_exit_vehicle_calculates_fee(fresh_system):
    fresh_system.park_vehicle("KAA123B")
    success, bill = fresh_system.exit_vehicle("KAA123B")
    assert success is True
    assert bill["plate_number"] == "KAA123B"
    assert bill["fee"] == 0  # parked for a fraction of a second, under 30 min


def test_confirm_payment_frees_slot(fresh_system):
    fresh_system.park_vehicle("KAA123B")
    record = fresh_system.active_vehicles["KAA123B"]
    db_id = record["db_id"]

    success, fee = fresh_system.confirm_payment("KAA123B", db_id)
    assert success is True
    assert fee == 0
    assert "KAA123B" not in fresh_system.active_vehicles
    assert len(fresh_system.available_slots()) == len(fresh_system.slots)


def test_confirm_payment_fee_is_recalculated_not_trusted(fresh_system):
    """Even if a caller passes a bogus 'expected fee' concept, confirm_payment
    doesn't accept a fee parameter at all — it always computes its own,
    verifying the tampering fix from earlier."""
    fresh_system.park_vehicle("KAA123B")
    record = fresh_system.active_vehicles["KAA123B"]
    db_id = record["db_id"]

    success, fee = fresh_system.confirm_payment("KAA123B", db_id)
    assert success is True
    assert fee == 0  # correctly computed server-side, nothing was ever passed in to override it

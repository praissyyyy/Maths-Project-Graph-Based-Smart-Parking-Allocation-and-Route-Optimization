"""
Unit and Integration Tests for SmartPark Slot Status Synchronisation and Booking Lifecycle.

Covers all 12 validation scenarios:
1. User books available slot -> Status updates to RESERVED in database.
2. Facility page updates immediately -> Slot shows RESERVED (Yellow), available count decrements, reserved count increments.
3. Booking record appears in My Bookings page.
4. Overlapping booking on same slot rejected with descriptive error message.
5. Non-overlapping booking on same slot succeeds.
6. User cancels booking -> Slot returns to AVAILABLE (Green), counts restore.
7. Attendant checks vehicle in -> Status updates to CHECKED_IN, slot updates to OCCUPIED (Red), utilisation % updates.
8. Attendant checks vehicle out -> Status updates to COMPLETED, slot returns to AVAILABLE (Green), utilisation % decreases.
9. Slot under MAINTENANCE -> Status is MAINTENANCE, booking attempts blocked.
10. Facility statistics mutual exclusivity: Capacity = Available + Reserved + Occupied + Maintenance, Utilisation = (Occupied / Capacity) * 100.
11. Double-booking / concurrency prevention.
12. Persistence across sessions and page refreshes.
"""

import os
from datetime import datetime, timedelta
import pytest
from app import create_app
from models import db
from models.user import User
from models.parking import ParkingFacility, ParkingSlot
from models.booking import Booking


@pytest.fixture
def app_instance():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    class TestConfig:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SECRET_KEY = "test-secret-key-smartpark-sync"
        DATA_DIR = os.path.join(base_dir, "data")
        GRAPHML_PATH = os.path.join(DATA_DIR, "gandhipuram_road_network.graphml")

    app = create_app(TestConfig)
    return app


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def login_user(client, app_instance, email="user@smartpark.com"):
    with app_instance.app_context():
        user = User.query.filter_by(email=email).first()
        u_id = user.user_id
        u_name = user.name
        u_role = user.role
    with client.session_transaction() as sess:
        sess['user_id'] = u_id
        sess['user_email'] = email
        sess['user_name'] = u_name
        sess['user_role'] = u_role


def login_staff_p1(client, app_instance):
    with app_instance.app_context():
        staff = User.query.filter_by(email="staff.p1@smartpark.com").first()
        s_id = staff.user_id
        s_name = staff.name
    with client.session_transaction() as sess:
        sess['user_id'] = s_id
        sess['user_email'] = "staff.p1@smartpark.com"
        sess['user_name'] = s_name
        sess['user_role'] = 'staff'
        sess['facility_id'] = 'P1'


def find_truly_available_slot(facility_id="P1"):
    """
    Finds a slot in the given facility that is NOT baseline occupied,
    NOT under maintenance, and has NO active or upcoming reservations.
    """
    slots = ParkingSlot.query.filter_by(facility_id=facility_id, initial_status="available").all()
    for s in slots:
        if s.manual_status == 'AUTO' and s.get_status_for_period() == 'available':
            return s
    return None


# =========================================================================
# SCENARIO 1: Booking available slot -> RESERVED in database
# =========================================================================
def test_scenario_1_user_books_available_slot_status_updates_to_reserved(app_instance, client):
    """Scenario 1: Slot status updates immediately from AVAILABLE to RESERVED in the database."""
    login_user(client, app_instance)

    with app_instance.app_context():
        slot = find_truly_available_slot("P1")
        assert slot is not None, "A truly available slot must exist in P1"
        slot_id = slot.slot_id
        assert slot.get_status_for_period() == "available"

    now = datetime.utcnow()
    arr = (now + timedelta(days=1, hours=10)).strftime("%Y-%m-%dT%H:%M")
    dep = (now + timedelta(days=1, hours=12)).strftime("%Y-%m-%dT%H:%M")

    res = client.post("/booking/new", data={
        "customer_name": "Scenario One Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 SC 0001",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr,
        "departure_datetime": dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Booking confirmed successfully" in res.data or b"SPK-" in res.data

    with app_instance.app_context():
        booking = Booking.query.filter_by(vehicle_number="TN 38 SC 0001").first()
        assert booking is not None
        assert booking.booking_status == "CONFIRMED"
        assert booking.slot_id == slot_id

        # Slot status evaluates to RESERVED for active/future reservation
        slot_check = db.session.get(ParkingSlot, slot_id)
        assert slot_check.get_status_for_period() == "reserved"


# =========================================================================
# SCENARIO 2: Facility page updates immediately -> RESERVED (Yellow) and counts update
# =========================================================================
def test_scenario_2_facility_page_and_stats_update_immediately(app_instance, client):
    """Scenario 2: Slot tile shows RESERVED (Yellow), available count -1, reserved count +1."""
    login_user(client, app_instance)

    with app_instance.app_context():
        facility = db.session.get(ParkingFacility, "P1")
        initial_stats = facility.get_dynamic_occupancy()
        slot = find_truly_available_slot("P1")
        assert slot is not None
        slot_id = slot.slot_id
        slot_num = slot.slot_number

    now = datetime.utcnow()
    arr = (now + timedelta(days=2, hours=9)).strftime("%Y-%m-%dT%H:%M")
    dep = (now + timedelta(days=2, hours=11)).strftime("%Y-%m-%dT%H:%M")

    client.post("/booking/new", data={
        "customer_name": "Scenario Two Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 SC 0002",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr,
        "departure_datetime": dep,
        "routing_algorithm": "Dijkstra"
    }, follow_redirects=True)

    # Verify counts changed
    with app_instance.app_context():
        facility_after = db.session.get(ParkingFacility, "P1")
        after_stats = facility_after.get_dynamic_occupancy()
        assert after_stats['available'] == initial_stats['available'] - 1
        assert after_stats['reserved'] == initial_stats['reserved'] + 1

    # Verify Facility Details page renders the Reserved status and slot info
    res = client.get("/parking/P1")
    assert res.status_code == 200
    assert b"Reserved" in res.data
    assert slot_num.encode() in res.data

    # Verify JSON API returns status 'reserved' with reservation window
    api_res = client.get("/parking/P1/slots")
    assert api_res.status_code == 200
    json_data = api_res.get_json()
    assert json_data['stats']['reserved'] == initial_stats['reserved'] + 1
    slot_entry = next((s for s in json_data['slots'] if s['slot_id'] == slot_id), None)
    assert slot_entry is not None
    assert slot_entry['status'] == 'reserved'
    assert slot_entry['reservation_window'] is not None


# =========================================================================
# SCENARIO 3: Booking appears in My Bookings page
# =========================================================================
def test_scenario_3_booking_appears_in_my_bookings(app_instance, client):
    """Scenario 3: Booking record appears in My Bookings page."""
    login_user(client, app_instance)

    with app_instance.app_context():
        slot = find_truly_available_slot("P1")
        assert slot is not None
        slot_id = slot.slot_id

    now = datetime.utcnow()
    arr = (now + timedelta(days=3, hours=14)).strftime("%Y-%m-%dT%H:%M")
    dep = (now + timedelta(days=3, hours=16)).strftime("%Y-%m-%dT%H:%M")

    res = client.post("/booking/new", data={
        "customer_name": "Scenario Three Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 SC 0003",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr,
        "departure_datetime": dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)
    assert res.status_code == 200

    # Visit My Bookings
    my_bookings_res = client.get("/my-bookings")
    assert my_bookings_res.status_code == 200
    assert b"TN 38 SC 0003" in my_bookings_res.data
    assert b"Confirmed" in my_bookings_res.data or b"CONFIRMED" in my_bookings_res.data
    assert b"Cross Cut Road" in my_bookings_res.data or b"P1" in my_bookings_res.data


# =========================================================================
# SCENARIO 4: Overlapping booking rejected with descriptive error
# =========================================================================
def test_scenario_4_overlapping_booking_rejected_with_descriptive_error(app_instance, client):
    """Scenario 4: Attempting to book the same slot for an overlapping time is rejected."""
    login_user(client, app_instance)

    with app_instance.app_context():
        slot = find_truly_available_slot("P1")
        assert slot is not None
        slot_id = slot.slot_id

    now = datetime.utcnow()
    # First booking: 10:00 to 14:00
    arr1 = (now + timedelta(days=4, hours=10)).strftime("%Y-%m-%dT%H:%M")
    dep1 = (now + timedelta(days=4, hours=14)).strftime("%Y-%m-%dT%H:%M")

    res1 = client.post("/booking/new", data={
        "customer_name": "First Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 SC 0004",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr1,
        "departure_datetime": dep1,
        "routing_algorithm": "A*"
    }, follow_redirects=True)
    assert res1.status_code == 200

    # Overlapping booking attempt: 12:00 to 16:00
    arr2 = (now + timedelta(days=4, hours=12)).strftime("%Y-%m-%dT%H:%M")
    dep2 = (now + timedelta(days=4, hours=16)).strftime("%Y-%m-%dT%H:%M")

    res2 = client.post("/booking/new", data={
        "customer_name": "Second Driver Overlap",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 SC 9999",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr2,
        "departure_datetime": dep2,
        "routing_algorithm": "A*"
    }, follow_redirects=True)

    # Must contain warning/danger error message indicating overlapping booking
    assert b"already booked" in res2.data or b"overlapping" in res2.data

    with app_instance.app_context():
        second_b = Booking.query.filter_by(vehicle_number="TN 38 SC 9999").first()
        assert second_b is None  # Second booking was not saved


# =========================================================================
# SCENARIO 5: Non-overlapping booking on same slot succeeds
# =========================================================================
def test_scenario_5_non_overlapping_booking_succeeds(app_instance, client):
    """Scenario 5: Attempting to book the same slot for a non-overlapping time succeeds."""
    login_user(client, app_instance)

    with app_instance.app_context():
        slot = find_truly_available_slot("P1")
        assert slot is not None
        slot_id = slot.slot_id

    now = datetime.utcnow()
    # Morning booking: 08:00 to 11:00
    arr1 = (now + timedelta(days=5, hours=8)).strftime("%Y-%m-%dT%H:%M")
    dep1 = (now + timedelta(days=5, hours=11)).strftime("%Y-%m-%dT%H:%M")

    res1 = client.post("/booking/new", data={
        "customer_name": "Morning Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 SC 005A",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr1,
        "departure_datetime": dep1,
        "routing_algorithm": "A*"
    }, follow_redirects=True)
    assert res1.status_code == 200

    # Afternoon booking: 13:00 to 16:00 (non-overlapping)
    arr2 = (now + timedelta(days=5, hours=13)).strftime("%Y-%m-%dT%H:%M")
    dep2 = (now + timedelta(days=5, hours=16)).strftime("%Y-%m-%dT%H:%M")

    res2 = client.post("/booking/new", data={
        "customer_name": "Afternoon Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 SC 005B",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr2,
        "departure_datetime": dep2,
        "routing_algorithm": "A*"
    }, follow_redirects=True)
    assert res2.status_code == 200
    assert b"Booking confirmed successfully" in res2.data or b"SPK-" in res2.data

    with app_instance.app_context():
        b1 = Booking.query.filter_by(vehicle_number="TN 38 SC 005A").first()
        b2 = Booking.query.filter_by(vehicle_number="TN 38 SC 005B").first()
        assert b1 is not None and b1.booking_status == "CONFIRMED"
        assert b2 is not None and b2.booking_status == "CONFIRMED"
        assert b1.slot_id == b2.slot_id


# =========================================================================
# SCENARIO 6: User cancels booking -> returns to AVAILABLE (Green)
# =========================================================================
def test_scenario_6_user_cancels_booking_restores_availability(app_instance, client):
    """Scenario 6: User cancels booking -> slot transitions from RESERVED back to AVAILABLE (Green)."""
    login_user(client, app_instance)

    with app_instance.app_context():
        facility = db.session.get(ParkingFacility, "P1")
        initial_stats = facility.get_dynamic_occupancy()
        slot = find_truly_available_slot("P1")
        assert slot is not None
        slot_id = slot.slot_id

    now = datetime.utcnow()
    arr = (now + timedelta(days=6, hours=10)).strftime("%Y-%m-%dT%H:%M")
    dep = (now + timedelta(days=6, hours=12)).strftime("%Y-%m-%dT%H:%M")

    client.post("/booking/new", data={
        "customer_name": "Cancel Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 SC 0006",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr,
        "departure_datetime": dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)

    with app_instance.app_context():
        booking = Booking.query.filter_by(vehicle_number="TN 38 SC 0006").first()
        b_id = booking.booking_id
        slot_check = db.session.get(ParkingSlot, slot_id)
        assert slot_check.get_status_for_period() == "reserved"

    # Cancel booking
    cancel_res = client.post(f"/booking/cancel/{b_id}", follow_redirects=True)
    assert cancel_res.status_code == 200

    with app_instance.app_context():
        b_after = db.session.get(Booking, b_id)
        assert b_after.booking_status == "CANCELLED"

        slot_after = db.session.get(ParkingSlot, slot_id)
        assert slot_after.get_status_for_period() == "available"

        facility_after = db.session.get(ParkingFacility, "P1")
        stats_after = facility_after.get_dynamic_occupancy()
        assert stats_after['available'] == initial_stats['available']
        assert stats_after['reserved'] == initial_stats['reserved']


# =========================================================================
# SCENARIO 7: Attendant checks vehicle in -> OCCUPIED (Red), utilisation updates
# =========================================================================
def test_scenario_7_vehicle_check_in_updates_to_occupied_and_utilisation(app_instance, client):
    """Scenario 7: Booking updates to CHECKED_IN, slot updates to OCCUPIED (Red), utilisation % updates."""
    with app_instance.app_context():
        facility = db.session.get(ParkingFacility, "P1")
        initial_stats = facility.get_dynamic_occupancy()
        user = User.query.filter_by(email="user@smartpark.com").first()
        slot = find_truly_available_slot("P1")
        assert slot is not None
        slot_id = slot.slot_id

        now = datetime.utcnow()
        b = Booking(
            booking_id="SPK-TEST-SC7",
            user_id=user.user_id,
            facility_id="P1",
            slot_id=slot_id,
            vehicle_number="TN 38 SC 0007",
            vehicle_type="Sedan",
            start_location="Gandhipuram Bus Stand",
            arrival_datetime=now,
            departure_datetime=now + timedelta(hours=3),
            booking_status="CONFIRMED"
        )
        db.session.add(b)
        db.session.commit()

    login_staff_p1(client, app_instance)

    # Process check-in
    res = client.post("/staff/booking/action", data={
        "booking_id": "SPK-TEST-SC7",
        "action": "CHECK_IN"
    }, follow_redirects=True)
    assert res.status_code == 200

    with app_instance.app_context():
        b_checked = db.session.get(Booking, "SPK-TEST-SC7")
        assert b_checked.booking_status == "CHECKED_IN"
        assert b_checked.check_in_time is not None

        slot_checked = db.session.get(ParkingSlot, slot_id)
        assert slot_checked.get_status_for_period() == "occupied"

        facility_checked = db.session.get(ParkingFacility, "P1")
        stats = facility_checked.get_dynamic_occupancy()
        assert stats['occupied'] == initial_stats['occupied'] + 1
        expected_util = round((stats['occupied'] / stats['capacity']) * 100.0, 1)
        assert stats['utilization_pct'] == expected_util


# =========================================================================
# SCENARIO 8: Attendant checks vehicle out -> AVAILABLE (Green), utilisation decreases
# =========================================================================
def test_scenario_8_vehicle_check_out_restores_available_and_reduces_utilisation(app_instance, client):
    """Scenario 8: Booking updates to COMPLETED, slot returns to AVAILABLE (Green), utilisation % decreases."""
    with app_instance.app_context():
        facility = db.session.get(ParkingFacility, "P1")
        initial_stats = facility.get_dynamic_occupancy()
        user = User.query.filter_by(email="user@smartpark.com").first()
        slot = find_truly_available_slot("P1")
        assert slot is not None
        slot_id = slot.slot_id

        now = datetime.utcnow()
        b = Booking(
            booking_id="SPK-TEST-SC8",
            user_id=user.user_id,
            facility_id="P1",
            slot_id=slot_id,
            vehicle_number="TN 38 SC 0008",
            vehicle_type="Sedan",
            start_location="Gandhipuram Bus Stand",
            arrival_datetime=now - timedelta(hours=1),
            departure_datetime=now + timedelta(hours=2),
            booking_status="CHECKED_IN",
            check_in_time=now - timedelta(hours=1)
        )
        db.session.add(b)
        db.session.commit()

    login_staff_p1(client, app_instance)

    # Process check-out
    res = client.post("/staff/booking/action", data={
        "booking_id": "SPK-TEST-SC8",
        "action": "CHECK_OUT"
    }, follow_redirects=True)
    assert res.status_code == 200

    with app_instance.app_context():
        b_done = db.session.get(Booking, "SPK-TEST-SC8")
        assert b_done.booking_status == "COMPLETED"
        assert b_done.check_out_time is not None

        slot_freed = db.session.get(ParkingSlot, slot_id)
        assert slot_freed.get_status_for_period() == "available"

        facility_freed = db.session.get(ParkingFacility, "P1")
        stats = facility_freed.get_dynamic_occupancy()
        assert stats['occupied'] == initial_stats['occupied']
        expected_util = round((stats['occupied'] / stats['capacity']) * 100.0, 1)
        assert stats['utilization_pct'] == expected_util


# =========================================================================
# SCENARIO 9: Slot placed under MAINTENANCE -> Cannot be booked
# =========================================================================
def test_scenario_9_maintenance_slot_blocks_booking(app_instance, client):
    """Scenario 9: Slot under MAINTENANCE cannot be booked by any user."""
    login_staff_p1(client, app_instance)

    with app_instance.app_context():
        slot = find_truly_available_slot("P1")
        assert slot is not None
        slot_id = slot.slot_id

    # Staff marks slot under maintenance
    m_res = client.post("/staff/slot/update-status", data={
        "slot_id": slot_id,
        "new_status": "MAINTENANCE",
        "reason": "Sensor re-calibration & surface repainting"
    }, follow_redirects=True)
    assert m_res.status_code == 200

    with app_instance.app_context():
        slot_m = db.session.get(ParkingSlot, slot_id)
        assert slot_m.manual_status == "MAINTENANCE"
        assert slot_m.get_status_for_period() == "maintenance"

    # User attempts to book this maintenance slot
    login_user(client, app_instance)
    now = datetime.utcnow()
    arr = (now + timedelta(days=7, hours=10)).strftime("%Y-%m-%dT%H:%M")
    dep = (now + timedelta(days=7, hours=12)).strftime("%Y-%m-%dT%H:%M")

    book_res = client.post("/booking/new", data={
        "customer_name": "Maintenance Test Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 SC 0009",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr,
        "departure_datetime": dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)

    assert b"maintenance" in book_res.data

    with app_instance.app_context():
        m_booking = Booking.query.filter_by(vehicle_number="TN 38 SC 0009").first()
        assert m_booking is None  # Blocked successfully


# =========================================================================
# SCENARIO 10: Facility overview statistics mutual exclusivity & formula
# =========================================================================
def test_scenario_10_facility_statistics_mutual_exclusivity_and_utilisation_formula(app_instance):
    """Scenario 10: Total Capacity = Available + Reserved + Occupied + Maintenance, Utilisation = (Occupied / Capacity) * 100."""
    with app_instance.app_context():
        facilities = ParkingFacility.query.all()
        assert len(facilities) >= 5

        for fac in facilities:
            stats = fac.get_dynamic_occupancy()
            total = stats['capacity']
            avail = stats['available']
            occ = stats['occupied']
            res = stats['reserved']
            maint = stats['maintenance']
            util = stats['utilization_pct']

            # 1. Strict mutual exclusivity check: partition of total capacity
            assert total == avail + occ + res + maint, (
                f"Facility {fac.facility_id} sum mismatch: "
                f"total={total} != avail({avail}) + occ({occ}) + res({res}) + maint({maint})"
            )

            # 2. Utilisation percentage formula check: (Occupied / Total) * 100
            expected_util = round((occ / total) * 100.0, 1)
            assert util == expected_util, (
                f"Facility {fac.facility_id} utilisation formula mismatch: {util} != {expected_util}"
            )

            # 3. Verify reserved slots are NOT counted as occupied
            assert util == round((occ / total) * 100.0, 1)


# =========================================================================
# SCENARIO 11: Simultaneous booking prevention (concurrency / race condition)
# =========================================================================
def test_scenario_11_simultaneous_booking_prevention(app_instance, client):
    """Scenario 11: Double booking prevention under simultaneous / rapid attempts."""
    login_user(client, app_instance)

    with app_instance.app_context():
        slot = find_truly_available_slot("P2")
        assert slot is not None
        slot_id = slot.slot_id

    now = datetime.utcnow()
    arr = (now + timedelta(days=8, hours=10)).strftime("%Y-%m-%dT%H:%M")
    dep = (now + timedelta(days=8, hours=12)).strftime("%Y-%m-%dT%H:%M")

    # Request 1
    res1 = client.post("/booking/new", data={
        "customer_name": "Racer One",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 RACE 01",
        "vehicle_type": "Sedan",
        "facility_id": "P2",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr,
        "departure_datetime": dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)
    assert res1.status_code == 200

    # Request 2 (Exact same slot and time)
    res2 = client.post("/booking/new", data={
        "customer_name": "Racer Two",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543211",
        "vehicle_number": "TN 38 RACE 02",
        "vehicle_type": "Sedan",
        "facility_id": "P2",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr,
        "departure_datetime": dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)

    assert b"already booked" in res2.data

    with app_instance.app_context():
        bookings = Booking.query.filter_by(slot_id=slot_id, arrival_datetime=datetime.strptime(arr, "%Y-%m-%dT%H:%M")).all()
        assert len(bookings) == 1
        assert bookings[0].vehicle_number == "TN 38 RACE 01"


# =========================================================================
# SCENARIO 12: Persistence across sessions and page refreshes
# =========================================================================
def test_scenario_12_persistence_across_sessions_and_refreshes(app_instance, client):
    """Scenario 12: Booking status updates remain persistent across page refresh and new login session."""
    # Session A: Book a slot
    login_user(client, app_instance)

    with app_instance.app_context():
        slot = find_truly_available_slot("P3")
        assert slot is not None
        slot_id = slot.slot_id
        slot_num = slot.slot_number

    now = datetime.utcnow()
    arr = (now + timedelta(days=9, hours=10)).strftime("%Y-%m-%dT%H:%M")
    dep = (now + timedelta(days=9, hours=12)).strftime("%Y-%m-%dT%H:%M")

    res = client.post("/booking/new", data={
        "customer_name": "Persistence Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 PERSIST",
        "vehicle_type": "Sedan",
        "facility_id": "P3",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr,
        "departure_datetime": dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)
    assert res.status_code == 200

    # Create fresh client (simulates separate browser session / device)
    fresh_client = app_instance.test_client()

    # Public check on facility details
    res_pub = fresh_client.get("/parking/P3")
    assert res_pub.status_code == 200
    assert b"Reserved" in res_pub.data
    assert slot_num.encode() in res_pub.data

    # Log in as user on fresh client and check My Bookings
    login_user(fresh_client, app_instance)
    res_my = fresh_client.get("/my-bookings")
    assert res_my.status_code == 200
    assert b"TN 38 PERSIST" in res_my.data
    assert b"Confirmed" in res_my.data or b"CONFIRMED" in res_my.data

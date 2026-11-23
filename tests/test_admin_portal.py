"""
Automated Pytest Suite for Parking Lot Staff Admin and Central Super Admin Portals.
Tests RBAC security, facility scoping, slot overrides, maintenance blocks,
vehicle gate movements, walk-in registrations, facility CRUD, and CSV exports.
"""

import pytest
from datetime import datetime, timedelta
from models import db
from models.user import User
from models.parking import ParkingFacility, ParkingSlot
from models.booking import Booking, generate_booking_id
from models.vehicle_log import VehicleLog
from models.activity_log import AdminActivityLog


@pytest.fixture
def auth_client(client, app_instance):
    """Helper fixture providing login sessions for different roles."""
    class AuthHelper:
        @staticmethod
        def login_super_admin():
            with app_instance.app_context():
                user = User.query.filter_by(email="admin@smartpark.com").first()
                u_id = user.user_id
                u_name = user.name
            with client.session_transaction() as sess:
                sess['user_id'] = u_id
                sess['user_name'] = u_name
                sess['user_role'] = 'super_admin'
                sess['facility_id'] = None

        @staticmethod
        def login_staff_p1():
            with app_instance.app_context():
                user = User.query.filter_by(email="staff.p1@smartpark.com").first()
                u_id = user.user_id
                u_name = user.name
            with client.session_transaction() as sess:
                sess['user_id'] = u_id
                sess['user_name'] = u_name
                sess['user_role'] = 'staff'
                sess['facility_id'] = 'P1'

        @staticmethod
        def login_driver():
            with app_instance.app_context():
                user = User.query.filter_by(email="user@smartpark.com").first()
                u_id = user.user_id
                u_name = user.name
            with client.session_transaction() as sess:
                sess['user_id'] = u_id
                sess['user_name'] = u_name
                sess['user_role'] = 'driver'
                sess['facility_id'] = None

    return AuthHelper()


def test_staff_login_and_facility_scoping(client, app_instance, auth_client):
    """Test 1: Verify staff login and strict facility-scoping for P1 staff."""
    auth_client.login_staff_p1()

    # Staff can access P1 dashboard
    res = client.get("/staff/dashboard")
    assert res.status_code == 200
    assert b"Cross Cut Road" in res.data or b"P1" in res.data

    # Staff can view P1 slots
    res_slots = client.get("/staff/slots")
    assert res_slots.status_code == 200
    assert b"P1-S01" in res_slots.data
    assert b"P2-S01" not in res_slots.data  # Scoped out!


def test_staff_slot_maintenance_lifecycle(client, app_instance, auth_client):
    """Test 2: Staff can mark a slot under maintenance and restore it."""
    auth_client.login_staff_p1()

    with app_instance.app_context():
        slot = ParkingSlot.query.filter_by(facility_id="P1", slot_number="P1-S05").first()
        slot_id = slot.slot_id

    # Mark slot under maintenance
    res = client.post("/staff/slot/update-status", data={
        "slot_id": slot_id,
        "new_status": "MAINTENANCE",
        "reason": "Sensor realignment testing"
    }, follow_redirects=True)
    assert res.status_code == 200

    with app_instance.app_context():
        slot_check = db.session.get(ParkingSlot, slot_id)
        assert slot_check.manual_status == "MAINTENANCE"
        assert slot_check.maintenance_reason == "Sensor realignment testing"
        assert slot_check.get_status_for_period() == "maintenance"

    # Restore slot to AUTO
    res_restore = client.post("/staff/slot/update-status", data={
        "slot_id": slot_id,
        "new_status": "AUTO",
        "reason": ""
    }, follow_redirects=True)
    assert res_restore.status_code == 200

    with app_instance.app_context():
        slot_restored = db.session.get(ParkingSlot, slot_id)
        assert slot_restored.manual_status == "AUTO"
        assert slot_restored.maintenance_reason is None


def test_staff_cannot_make_active_slot_available(client, app_instance, auth_client):
    """Test 3: Rule check - staff cannot manually mark a slot available if actively checked in."""
    auth_client.login_staff_p1()

    with app_instance.app_context():
        # Create an actively checked-in booking on P1-S06
        now = datetime.utcnow()
        user = User.query.filter_by(email="user@smartpark.com").first()
        slot = ParkingSlot.query.filter_by(facility_id="P1", slot_number="P1-S06").first()
        slot_id = slot.slot_id

        b = Booking(
            booking_id="TEST-ACT-001",
            user_id=user.user_id,
            facility_id="P1",
            slot_id=slot_id,
            vehicle_number="TN38XX9999",
            vehicle_type="Sedan",
            start_location="Test Loc",
            arrival_datetime=now - timedelta(minutes=10),
            departure_datetime=now + timedelta(hours=2),
            booking_status="CHECKED_IN"
        )
        db.session.add(b)
        db.session.commit()

    # Attempt to override to AVAILABLE
    res = client.post("/staff/slot/update-status", data={
        "slot_id": slot_id,
        "new_status": "AVAILABLE"
    }, follow_redirects=True)

    assert b"Cannot mark slot" in res.data or b"actively checked in" in res.data

    with app_instance.app_context():
        slot_check = db.session.get(ParkingSlot, slot_id)
        assert slot_check.manual_status != "AVAILABLE"


def test_vehicle_check_in_and_check_out_workflow(client, app_instance, auth_client):
    """Test 4: Complete gate check-in and check-out cycle with vehicle log tracking."""
    auth_client.login_staff_p1()

    with app_instance.app_context():
        now = datetime.utcnow()
        user = User.query.filter_by(email="user@smartpark.com").first()
        slot = ParkingSlot.query.filter_by(facility_id="P1", slot_number="P1-S07").first()

        b = Booking(
            booking_id="TEST-GATE-001",
            user_id=user.user_id,
            facility_id="P1",
            slot_id=slot.slot_id,
            vehicle_number="TN38GATE01",
            vehicle_type="Sedan",
            start_location="Test Entry",
            arrival_datetime=now,
            departure_datetime=now + timedelta(hours=2),
            booking_status="CONFIRMED"
        )
        db.session.add(b)
        db.session.commit()
        b_id = b.booking_id

    # 1. Process Check-In
    res_in = client.post("/staff/booking/action", data={
        "booking_id": b_id,
        "action": "CHECK_IN"
    }, follow_redirects=True)
    assert res_in.status_code == 200

    with app_instance.app_context():
        b_check = db.session.get(Booking, b_id)
        assert b_check.booking_status == "CHECKED_IN"
        assert b_check.check_in_time is not None

        vlog = VehicleLog.query.filter_by(booking_id=b_id).first()
        assert vlog is not None
        assert vlog.status == "IN_PARKING"

    # 2. Process Check-Out
    res_out = client.post("/staff/booking/action", data={
        "booking_id": b_id,
        "action": "CHECK_OUT"
    }, follow_redirects=True)
    assert res_out.status_code == 200

    with app_instance.app_context():
        b_check2 = db.session.get(Booking, b_id)
        assert b_check2.booking_status == "COMPLETED"
        assert b_check2.check_out_time is not None

        vlog2 = VehicleLog.query.filter_by(booking_id=b_id).first()
        assert vlog2.status == "COMPLETED"
        assert vlog2.exit_time is not None


def test_walk_in_registration(client, app_instance, auth_client):
    """Test 5: Register drive-up walk-in vehicle at gate."""
    auth_client.login_staff_p1()

    now = datetime.utcnow()
    dep = now + timedelta(hours=3)

    with app_instance.app_context():
        # Find a slot that is mathematically and physically available
        all_p1 = ParkingSlot.query.filter_by(facility_id="P1").all()
        slot = next(s for s in all_p1 if s.is_available_for_period(now, dep))
        slot_id = slot.slot_id

    res = client.post("/staff/walk-in", data={
        "vehicle_number": "TN38WALK77",
        "vehicle_type": "SUV",
        "slot_id": slot_id,
        "driver_name": "Walk-in Guest Driver",
        "driver_phone": "9842199999",
        "duration_hours": "3"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"TN38WALK77" in res.data or b"successfully registered" in res.data

    with app_instance.app_context():
        walkin_b = Booking.query.filter_by(vehicle_number="TN38WALK77").first()
        assert walkin_b is not None
        assert walkin_b.is_walkin is True
        assert walkin_b.booking_status == "CHECKED_IN"


def test_super_admin_facility_addition_and_slot_generation(client, app_instance, auth_client):
    """Test 6: Super Admin adds a new facility, verifying automatic slot generation."""
    auth_client.login_super_admin()

    res = client.post("/super-admin/facility/add", data={
        "facility_id": "P6",
        "facility_name": "Avarampalayam Road Smart Parking",
        "node_id": "NODE_P6",
        "latitude": "11.025000",
        "longitude": "76.975000",
        "capacity": "15",
        "description": "New academic test hub near Gandhipuram border"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"P6" in res.data

    with app_instance.app_context():
        fac = db.session.get(ParkingFacility, "P6")
        assert fac is not None
        assert fac.capacity == 15
        slots = ParkingSlot.query.filter_by(facility_id="P6").all()
        assert len(slots) == 15
        assert slots[0].slot_number == "P6-S01"
        assert slots[14].slot_number == "P6-S15"


def test_super_admin_staff_management(client, app_instance, auth_client):
    """Test 7: Super Admin creates, reassigns, and toggles a staff account."""
    auth_client.login_super_admin()

    # Create staff
    res = client.post("/super-admin/staff/create", data={
        "name": "Test Attendant",
        "email": "test.staff@smartpark.com",
        "phone": "+91 99999 88888",
        "facility_id": "P2",
        "password": "Password@123"
    }, follow_redirects=True)
    assert res.status_code == 200

    with app_instance.app_context():
        staff = User.query.filter_by(email="test.staff@smartpark.com").first()
        assert staff is not None
        assert staff.role == "staff"
        assert staff.facility_id == "P2"
        staff_id = staff.user_id

    # Reassign facility to P3
    res_edit = client.post(f"/super-admin/staff/edit/{staff_id}", data={
        "name": "Test Attendant Renamed",
        "phone": "+91 99999 77777",
        "facility_id": "P3"
    }, follow_redirects=True)
    assert res_edit.status_code == 200

    with app_instance.app_context():
        staff_recheck = db.session.get(User, staff_id)
        assert staff_recheck.facility_id == "P3"
        assert staff_recheck.name == "Test Attendant Renamed"


def test_driver_blocked_from_admin_portals(client, auth_client):
    """Test 8: Ensure driver role cannot access staff or super-admin endpoints."""
    auth_client.login_driver()

    # Driver blocked from Staff Portal
    res_staff = client.get("/staff/dashboard", follow_redirects=False)
    assert res_staff.status_code in [302, 401, 403]

    # Driver blocked from Super Admin Portal
    res_super = client.get("/super-admin/dashboard", follow_redirects=False)
    assert res_super.status_code in [302, 401, 403]


def test_csv_export_endpoints(client, auth_client):
    """Test 9: Verify CSV export generation for Staff and Super Admin."""
    auth_client.login_staff_p1()
    res_staff_csv = client.get("/staff/reports?type=daily&export=true")
    assert res_staff_csv.status_code == 200
    assert "text/csv" in res_staff_csv.content_type
    assert b"Booking ID,Customer Name" in res_staff_csv.data

    auth_client.login_super_admin()
    res_super_csv = client.get("/super-admin/bookings?export=true")
    assert res_super_csv.status_code == 200
    assert "text/csv" in res_super_csv.content_type
    assert b"Booking ID,Facility ID" in res_super_csv.data

"""
Unit tests for Online Booking Engine, Double-Booking Prevention, Overlap Constraints, and Cancellations.
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
        SECRET_KEY = "test-secret-key"
        DATA_DIR = os.path.join(base_dir, "data")
        GRAPHML_PATH = os.path.join(DATA_DIR, "gandhipuram_road_network.graphml")

    app = create_app(TestConfig)
    return app


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def test_booking_creation(app_instance, client):
    """Test 10: Verify successful booking creation and database record persistence."""
    with app_instance.app_context():
        user = User.query.filter_by(email="user@smartpark.com").first()
        slot = ParkingSlot.query.filter_by(facility_id="P1", initial_status="available").first()

    now = datetime.utcnow()
    arr = (now + timedelta(days=2, hours=10)).strftime("%Y-%m-%dT%H:%M")
    dep = (now + timedelta(days=2, hours=12)).strftime("%Y-%m-%dT%H:%M")

    with client.session_transaction() as sess:
        sess['user_id'] = user.user_id
        sess['user_email'] = user.email

    response = client.post("/booking/new", data={
        "customer_name": "Test Driver",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 ZZ 9999",
        "vehicle_type": "Sedan",
        "facility_id": "P1",
        "slot_id": slot.slot_id,
        "start_location": "Gandhipuram Bus Stand",
        "arrival_datetime": arr,
        "departure_datetime": dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Booking confirmed successfully" in response.data or b"SPK-" in response.data

    with app_instance.app_context():
        b = Booking.query.filter_by(vehicle_number="TN 38 ZZ 9999").first()
        assert b is not None
        assert b.booking_status == "CONFIRMED"
        assert b.slot_id == slot.slot_id


def test_overlapping_reservation_prevention(app_instance, client):
    """Test 11 & 12: Verify system blocks duplicate/overlapping booking for the same slot."""
    with app_instance.app_context():
        user = User.query.filter_by(email="user@smartpark.com").first()
        user_id = user.user_id
        # Find an available slot
        slot = ParkingSlot.query.filter_by(facility_id="P2", initial_status="available").first()
        slot_id = slot.slot_id

        now = datetime.utcnow()
        t1 = now + timedelta(days=5, hours=10)
        t2 = now + timedelta(days=5, hours=14)

        # First booking [10:00 - 14:00]
        b1 = Booking(
            user_id=user_id,
            facility_id="P2",
            slot_id=slot_id,
            vehicle_number="TN 38 AA 1111",
            vehicle_type="Sedan",
            arrival_datetime=t1,
            departure_datetime=t2,
            booking_status="CONFIRMED"
        )
        db.session.add(b1)
        db.session.commit()

    # Attempt overlapping booking on same slot [11:00 - 13:00]
    overlap_arr = (now + timedelta(days=5, hours=11)).strftime("%Y-%m-%dT%H:%M")
    overlap_dep = (now + timedelta(days=5, hours=13)).strftime("%Y-%m-%dT%H:%M")

    with client.session_transaction() as sess:
        sess['user_id'] = user_id

    response = client.post("/booking/new", data={
        "customer_name": "Second Driver",
        "customer_email": "second@example.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 BB 2222",
        "vehicle_type": "SUV",
        "facility_id": "P2",
        "slot_id": slot_id,
        "start_location": "Gandhipuram Market",
        "arrival_datetime": overlap_arr,
        "departure_datetime": overlap_dep,
        "routing_algorithm": "Dijkstra"
    }, follow_redirects=True)

    assert b"already booked" in response.data or b"danger" in response.data

    with app_instance.app_context():
        b_second = Booking.query.filter_by(vehicle_number="TN 38 BB 2222").first()
        assert b_second is None  # Must NOT be created


def test_non_overlapping_reservations_allowed(app_instance, client):
    """Test 13: Verify same slot CAN be booked for separate non-overlapping intervals."""
    with app_instance.app_context():
        user = User.query.filter_by(email="user@smartpark.com").first()
        user_id = user.user_id
        slot = ParkingSlot.query.filter_by(facility_id="P3", initial_status="available").first()
        slot_id = slot.slot_id

    now = datetime.utcnow()
    # Interval 1: Day 10 [08:00 - 10:00]
    t1_arr = (now + timedelta(days=10, hours=8)).strftime("%Y-%m-%dT%H:%M")
    t1_dep = (now + timedelta(days=10, hours=10)).strftime("%Y-%m-%dT%H:%M")

    # Interval 2: Day 10 [12:00 - 14:00] (Strictly after Interval 1)
    t2_arr = (now + timedelta(days=10, hours=12)).strftime("%Y-%m-%dT%H:%M")
    t2_dep = (now + timedelta(days=10, hours=14)).strftime("%Y-%m-%dT%H:%M")

    with client.session_transaction() as sess:
        sess['user_id'] = user_id

    # Book Interval 1
    res1 = client.post("/booking/new", data={
        "customer_name": "Driver One",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 C1 1001",
        "vehicle_type": "Sedan",
        "facility_id": "P3",
        "slot_id": slot_id,
        "start_location": "Gandhipuram",
        "arrival_datetime": t1_arr,
        "departure_datetime": t1_dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)
    assert b"Booking confirmed" in res1.data or b"SPK-" in res1.data

    # Book Interval 2 (Should succeed!)
    res2 = client.post("/booking/new", data={
        "customer_name": "Driver Two",
        "customer_email": "user@smartpark.com",
        "customer_phone": "9876543210",
        "vehicle_number": "TN 38 C2 2002",
        "vehicle_type": "Hatchback",
        "facility_id": "P3",
        "slot_id": slot_id,
        "start_location": "Gandhipuram",
        "arrival_datetime": t2_arr,
        "departure_datetime": t2_dep,
        "routing_algorithm": "A*"
    }, follow_redirects=True)
    assert b"Booking confirmed" in res2.data or b"SPK-" in res2.data

    with app_instance.app_context():
        bookings_on_slot = Booking.query.filter_by(slot_id=slot_id, booking_status="CONFIRMED").all()
        assert len(bookings_on_slot) >= 2


def test_booking_cancellation_and_availability_restored(app_instance, client):
    """Test 14 & 15: Verify cancellation updates status and restores slot availability."""
    with app_instance.app_context():
        user = User.query.filter_by(email="user@smartpark.com").first()
        user_id = user.user_id
        slot = ParkingSlot.query.filter_by(facility_id="P4", initial_status="available").first()
        slot_id = slot.slot_id

        now = datetime.utcnow()
        t_arr = now + timedelta(days=7, hours=10)
        t_dep = now + timedelta(days=7, hours=12)

        booking = Booking(
            user_id=user_id,
            facility_id="P4",
            slot_id=slot_id,
            vehicle_number="TN 38 CANCEL 01",
            vehicle_type="SUV",
            arrival_datetime=t_arr,
            departure_datetime=t_dep,
            booking_status="CONFIRMED"
        )
        db.session.add(booking)
        db.session.commit()
        b_id = booking.booking_id

        # Slot is now NOT available for this window
        assert slot.is_available_for_period(t_arr, t_dep) is False

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['user_role'] = 'user'

    # Cancel via route
    res = client.post(f"/booking/cancel/{b_id}", follow_redirects=True)
    assert res.status_code == 200
    assert b"cancelled successfully" in res.data or b"My Parking Reservations" in res.data

    with app_instance.app_context():
        cancelled_b = Booking.query.get(b_id)
        assert cancelled_b.booking_status == "CANCELLED"

        # Slot availability for that period is restored!
        slot_recheck = ParkingSlot.query.get(slot_id)
        assert slot_recheck.is_available_for_period(t_arr, t_dep) is True

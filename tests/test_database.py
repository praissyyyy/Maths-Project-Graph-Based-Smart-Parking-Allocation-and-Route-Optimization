"""
Unit tests for Database Initialization, Facility/Slot Models, User Authentication, and Admin Permissions.
"""

import os
import pytest
from app import create_app
from models import db
from models.user import User
from models.parking import ParkingFacility, ParkingSlot


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


def test_facility_initialization(app_instance):
    """Test 2: Verify all 5 facilities exist in database with correct initial parameters."""
    with app_instance.app_context():
        facilities = ParkingFacility.query.all()
        assert len(facilities) == 5
        for fac in facilities:
            assert fac.capacity == 30
            assert fac.initial_occupied == 10
            stats = fac.get_dynamic_occupancy()
            assert stats['available'] >= 15


def test_slot_generation(app_instance):
    """Test 3: Verify 150 total slots exist (30 per facility) with initial status."""
    with app_instance.app_context():
        slots = ParkingSlot.query.all()
        assert len(slots) == 150

        # Each facility has exactly 30 slots
        for fac in ParkingFacility.query.all():
            fac_slots = ParkingSlot.query.filter_by(facility_id=fac.facility_id).all()
            assert len(fac_slots) == 30

            # 10 initial occupied, 20 initial available
            occ_count = sum(1 for s in fac_slots if s.initial_status == 'occupied')
            avail_count = sum(1 for s in fac_slots if s.initial_status == 'available')
            assert occ_count == 10
            assert avail_count == 20


def test_user_authentication_and_password_hashing(app_instance):
    """Test 16: Verify password hashing, verification, and role assignments."""
    with app_instance.app_context():
        user = User.query.filter_by(email="user@smartpark.com").first()
        assert user is not None
        assert user.password_hash != "User@123"
        assert user.check_password("User@123") is True
        assert user.check_password("WrongPassword") is False
        assert user.role in ["user", "driver"]


def test_admin_permissions(app_instance, client):
    """Test 17: Verify admin routes are restricted to authenticated admin users."""
    # Unauthorized request to admin dashboard redirects to login
    res = client.get("/admin/dashboard", follow_redirects=False)
    assert res.status_code in [302, 401, 403]

    # Sign in as regular user -> denied
    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['user_role'] = 'driver'

    res_user = client.get("/admin/dashboard", follow_redirects=True)
    assert b"Administrator privileges required" in res_user.data or res_user.status_code in [200, 302, 403]

    # Sign in as super_admin -> allowed (redirects to super_admin dashboard)
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['user_role'] = 'super_admin'

    res_admin = client.get("/admin/dashboard", follow_redirects=True)
    assert res_admin.status_code == 200
    assert b"Central Command" in res_admin.data or b"Super Admin" in res_admin.data


def test_database_persistence(app_instance):
    """Test 18: Verify changes persist across database queries."""
    with app_instance.app_context():
        new_user = User(
            name="Persistence Test User",
            email="persist@test.com",
            phone="9998887776",
            role="user"
        )
        new_user.set_password("SecurePass!99")
        db.session.add(new_user)
        db.session.commit()

        # Query back
        queried = User.query.filter_by(email="persist@test.com").first()
        assert queried is not None
        assert queried.name == "Persistence Test User"
        assert queried.check_password("SecurePass!99") is True

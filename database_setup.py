"""
Database Seeding and Initialization Helper for SmartPark - Gandhipuram.
Populates facilities, slots, accounts for Driver, Staff (P1-P5), and Super Admin,
plus initial audit and vehicle logs.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask
from models import db
from models.user import User
from models.parking import ParkingFacility, ParkingSlot
from models.booking import Booking, RouteHistory
from models.vehicle_log import VehicleLog
from models.activity_log import AdminActivityLog
from models.maintenance import SlotMaintenanceRecord

logger = logging.getLogger(__name__)


def migrate_schema_if_needed():
    """
    Ensures that existing SQLite tables have newly added columns
    (SQLite's db.create_all() does not alter existing tables).
    """
    from sqlalchemy import text
    with db.engine.connect() as conn:
        # Check users table columns
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()]
        if cols:
            if 'facility_id' not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN facility_id VARCHAR(20) REFERENCES parking_facilities(facility_id)"))
            if 'is_active' not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            if 'last_login' not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login DATETIME"))

        # Check parking_facilities table columns
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(parking_facilities)")).fetchall()]
        if cols:
            if 'is_active' not in cols:
                conn.execute(text("ALTER TABLE parking_facilities ADD COLUMN is_active BOOLEAN DEFAULT 1"))

        # Check parking_slots table columns
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(parking_slots)")).fetchall()]
        if cols:
            if 'manual_status' not in cols:
                conn.execute(text("ALTER TABLE parking_slots ADD COLUMN manual_status VARCHAR(20) DEFAULT 'AUTO'"))
            if 'maintenance_reason' not in cols:
                conn.execute(text("ALTER TABLE parking_slots ADD COLUMN maintenance_reason VARCHAR(255)"))
            if 'maintenance_updated_at' not in cols:
                conn.execute(text("ALTER TABLE parking_slots ADD COLUMN maintenance_updated_at DATETIME"))

        # Check bookings table columns
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(bookings)")).fetchall()]
        if cols:
            if 'is_walkin' not in cols:
                conn.execute(text("ALTER TABLE bookings ADD COLUMN is_walkin BOOLEAN DEFAULT 0"))
            if 'check_in_time' not in cols:
                conn.execute(text("ALTER TABLE bookings ADD COLUMN check_in_time DATETIME"))
            if 'check_out_time' not in cols:
                conn.execute(text("ALTER TABLE bookings ADD COLUMN check_out_time DATETIME"))
            if 'checked_in_by' not in cols:
                conn.execute(text("ALTER TABLE bookings ADD COLUMN checked_in_by INTEGER"))
            if 'checked_out_by' not in cols:
                conn.execute(text("ALTER TABLE bookings ADD COLUMN checked_out_by INTEGER"))

        conn.commit()


def init_and_seed_database(app: Flask):
    """
    Initializes database schema and populates parking facilities, slots,
    RBAC accounts (Super Admin, Staff for P1-P5, Driver), and seed logs.
    """
    with app.app_context():
        db.create_all()
        migrate_schema_if_needed()

        # 1. Seed or update Super Admin
        admin_user = User.query.filter_by(email="admin@smartpark.com").first()
        if not admin_user:
            admin_user = User(
                name="Central Super Admin",
                email="admin@smartpark.com",
                phone="+91 98765 43210",
                role="super_admin",
                is_active=True
            )
            admin_user.set_password("Admin@123")
            db.session.add(admin_user)
            logger.info("Created Super Admin user: admin@smartpark.com")
        else:
            admin_user.role = "super_admin"
            admin_user.is_active = True

        # 2. Seed or update Demo Driver
        demo_user = User.query.filter_by(email="user@smartpark.com").first()
        if not demo_user:
            demo_user = User(
                name="Praisy D. (Driver)",
                email="user@smartpark.com",
                phone="+91 98421 12345",
                role="driver",
                is_active=True
            )
            demo_user.set_password("User@123")
            db.session.add(demo_user)
            logger.info("Created demo driver user: user@smartpark.com")
        else:
            if demo_user.role == 'user':
                demo_user.role = 'driver'
            demo_user.is_active = True

        db.session.commit()

        # 3. Seed Parking Facilities and Slots if not present
        if ParkingFacility.query.count() == 0:
            facilities_json_path = os.path.join(app.config.get("DATA_DIR", "data"), "parking_facilities.json")
            if os.path.exists(facilities_json_path):
                with open(facilities_json_path, "r", encoding="utf-8") as f:
                    facilities_data = json.load(f)

                for fac in facilities_data:
                    facility_obj = ParkingFacility(
                        facility_id=fac["facility_id"],
                        facility_name=fac["facility_name"],
                        node_id=str(fac["node_id"]),
                        latitude=fac["latitude"],
                        longitude=fac["longitude"],
                        capacity=fac["total_capacity"],
                        initial_occupied=fac["initial_occupied"],
                        description=fac.get("description", ""),
                        is_active=True
                    )
                    db.session.add(facility_obj)

                    for slot_info in fac.get("slots", []):
                        slot_obj = ParkingSlot(
                            slot_id=slot_info["slot_id"],
                            facility_id=fac["facility_id"],
                            slot_number=slot_info["slot_number"],
                            initial_status=slot_info.get("initial_status", "available"),
                            manual_status='AUTO'
                        )
                        db.session.add(slot_obj)

                db.session.commit()
                logger.info("Successfully seeded 5 parking facilities and 150 parking slots.")

        # 4. Seed Staff Accounts for each of the 5 facilities (P1 to P5)
        staff_accounts = [
            ("P1", "Cross Cut Staff - Ramesh", "staff.p1@smartpark.com", "+91 98421 11001"),
            ("P2", "100 Feet Staff - Suresh", "staff.p2@smartpark.com", "+91 98421 22002"),
            ("P3", "Bharathiar Staff - Priya", "staff.p3@smartpark.com", "+91 98421 33003"),
            ("P4", "Nanjappa Staff - Karthik", "staff.p4@smartpark.com", "+91 98421 44004"),
            ("P5", "Sathy Road Staff - Anitha", "staff.p5@smartpark.com", "+91 98421 55005"),
        ]

        for fac_id, name, email, phone in staff_accounts:
            existing_staff = User.query.filter_by(email=email).first()
            if not existing_staff:
                staff_user = User(
                    name=name,
                    email=email,
                    phone=phone,
                    role="staff",
                    facility_id=fac_id,
                    is_active=True
                )
                staff_user.set_password("Staff@123")
                db.session.add(staff_user)
                logger.info(f"Created staff account {email} assigned to {fac_id}")
            else:
                existing_staff.role = "staff"
                existing_staff.facility_id = fac_id
                existing_staff.is_active = True

        db.session.commit()

        # 5. Seed sample demonstration bookings & telemetry if needed
        if Booking.query.count() == 0 and demo_user:
            now = datetime.utcnow()
            b1 = Booking(
                booking_id="SPK-DEMO-001",
                user_id=demo_user.user_id,
                facility_id="P1",
                slot_id="P1_11",
                vehicle_number="TN 38 AB 1001",
                vehicle_type="Sedan",
                start_location="Cross Cut Road Junction",
                arrival_datetime=now + timedelta(hours=1),
                departure_datetime=now + timedelta(hours=3),
                booking_status="CONFIRMED"
            )
            db.session.add(b1)
            db.session.flush()

            rh1 = RouteHistory(
                booking_id=b1.booking_id,
                algorithm="A*",
                distance=1120.5,
                execution_time=0.0035
            )
            db.session.add(rh1)

            b2 = Booking(
                booking_id="SPK-DEMO-002",
                user_id=demo_user.user_id,
                facility_id="P2",
                slot_id="P2_12",
                vehicle_number="TN 38 CD 2002",
                vehicle_type="SUV",
                start_location="Gandhipuram 100 Feet Road",
                arrival_datetime=now + timedelta(days=1, hours=2),
                departure_datetime=now + timedelta(days=1, hours=5),
                booking_status="CONFIRMED"
            )
            db.session.add(b2)
            db.session.flush()

            rh2 = RouteHistory(
                booking_id=b2.booking_id,
                algorithm="Dijkstra",
                distance=850.2,
                execution_time=0.0042
            )
            db.session.add(rh2)
            db.session.commit()

        # 6. Seed sample VehicleLog and AdminActivityLog records if empty
        if AdminActivityLog.query.count() == 0:
            super_admin = User.query.filter_by(email="admin@smartpark.com").first()
            p1_staff = User.query.filter_by(email="staff.p1@smartpark.com").first()

            now = datetime.utcnow()
            if super_admin:
                AdminActivityLog.log_action(
                    user_id=super_admin.user_id,
                    action_type="SYSTEM_INITIALIZE",
                    description="Initialized SmartPark Gandhipuram RBAC and multi-facility parking network.",
                    facility_id=None
                )
            if p1_staff:
                AdminActivityLog.log_action(
                    user_id=p1_staff.user_id,
                    action_type="LOGIN",
                    description=f"{p1_staff.name} logged into Staff Portal for facility P1.",
                    facility_id="P1"
                )

        # 7. Seed one sample checked-in vehicle and walk-in log for testing
        if VehicleLog.query.count() == 0:
            p1_staff = User.query.filter_by(email="staff.p1@smartpark.com").first()
            now = datetime.utcnow()
            vlog = VehicleLog(
                facility_id="P1",
                slot_id="P1_15",
                vehicle_number="TN 38 WLK 9900",
                vehicle_type="Sedan",
                entry_time=now - timedelta(minutes=45),
                status="IN_PARKING",
                is_walkin=True,
                entry_by_user_id=p1_staff.user_id if p1_staff else None
            )
            db.session.add(vlog)
            db.session.commit()
            logger.info("Seeded initial vehicle logs and activity audit records.")

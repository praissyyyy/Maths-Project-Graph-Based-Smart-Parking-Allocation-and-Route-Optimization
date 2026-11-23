"""
Booking and Route History Models.
Handles reservation transactions, temporal constraints, status lifecycles, and routing telemetry.
Supports standard online bookings and staff-registered walk-in arrivals.
"""

from datetime import datetime
import uuid
from models import db


def generate_booking_id() -> str:
    """Generates unique human-readable booking reference e.g., SPK-202611-A1B2C3."""
    hex_str = uuid.uuid4().hex[:6].upper()
    now_str = datetime.utcnow().strftime("%Y%m%d")
    return f"SPK-{now_str}-{hex_str}"


class Booking(db.Model):
    __tablename__ = 'bookings'

    booking_id = db.Column(db.String(40), primary_key=True, default=generate_booking_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    facility_id = db.Column(db.String(20), db.ForeignKey('parking_facilities.facility_id'), nullable=False)
    slot_id = db.Column(db.String(30), db.ForeignKey('parking_slots.slot_id'), nullable=False)
    vehicle_number = db.Column(db.String(40), nullable=False)
    vehicle_type = db.Column(db.String(30), nullable=False)
    start_location = db.Column(db.String(150), nullable=True)
    arrival_datetime = db.Column(db.DateTime, nullable=False, index=True)
    departure_datetime = db.Column(db.DateTime, nullable=False, index=True)
    booking_status = db.Column(db.String(20), nullable=False, default='CONFIRMED')
    # Statuses: 'PENDING', 'CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED', 'NO_SHOW'

    is_walkin = db.Column(db.Boolean, default=False, nullable=False)
    check_in_time = db.Column(db.DateTime, nullable=True)
    check_out_time = db.Column(db.DateTime, nullable=True)
    checked_in_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    checked_out_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    route_history = db.relationship('RouteHistory', backref='booking', lazy=True, cascade='all, delete-orphan')

    def cancel(self):
        """Cancels booking safely without deleting audit record."""
        self.booking_status = 'CANCELLED'
        db.session.commit()

    def check_in(self, staff_id: int = None):
        """Marks vehicle as checked in and records entry timestamp."""
        self.booking_status = 'CHECKED_IN'
        self.check_in_time = datetime.utcnow()
        if staff_id:
            self.checked_in_by = staff_id
        db.session.commit()

    def check_out(self, staff_id: int = None):
        """Marks vehicle as completed and records exit timestamp."""
        self.booking_status = 'COMPLETED'
        self.check_out_time = datetime.utcnow()
        if staff_id:
            self.checked_out_by = staff_id
        db.session.commit()

    @classmethod
    def expire_past_bookings(cls):
        """
        Transitions confirmed/pending bookings whose departure time has elapsed
        without check-in to 'EXPIRED'. Releases the time interval.
        """
        now = datetime.utcnow()
        expired_bookings = cls.query.filter(
            cls.booking_status.in_(['CONFIRMED', 'PENDING']),
            cls.departure_datetime < now,
            cls.check_in_time.is_(None)
        ).all()

        if expired_bookings:
            for b in expired_bookings:
                b.booking_status = 'EXPIRED'
            db.session.commit()

    def to_dict(self):
        return {
            'booking_id': self.booking_id,
            'user_id': self.user_id,
            'customer_name': self.user.name if self.user else None,
            'customer_email': self.user.email if self.user else None,
            'customer_phone': self.user.phone if self.user else None,
            'facility_id': self.facility_id,
            'facility_name': self.facility.facility_name if self.facility else None,
            'slot_id': self.slot_id,
            'slot_number': self.slot.slot_number if self.slot else None,
            'vehicle_number': self.vehicle_number,
            'vehicle_type': self.vehicle_type,
            'start_location': self.start_location,
            'arrival_datetime': self.arrival_datetime.strftime('%Y-%m-%d %H:%M'),
            'departure_datetime': self.departure_datetime.strftime('%Y-%m-%d %H:%M'),
            'booking_status': self.booking_status,
            'is_walkin': self.is_walkin,
            'check_in_time': self.check_in_time.strftime('%Y-%m-%d %H:%M:%S') if self.check_in_time else None,
            'check_out_time': self.check_out_time.strftime('%Y-%m-%d %H:%M:%S') if self.check_out_time else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class RouteHistory(db.Model):
    __tablename__ = 'route_history'

    route_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_id = db.Column(db.String(40), db.ForeignKey('bookings.booking_id'), nullable=False)
    algorithm = db.Column(db.String(30), nullable=False)  # 'Dijkstra' or 'A*'
    distance = db.Column(db.Float, nullable=False)  # in meters
    execution_time = db.Column(db.Float, nullable=False)  # in seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'route_id': self.route_id,
            'booking_id': self.booking_id,
            'algorithm': self.algorithm,
            'distance_m': round(self.distance, 2),
            'execution_time_ms': round(self.execution_time * 1000.0, 3),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

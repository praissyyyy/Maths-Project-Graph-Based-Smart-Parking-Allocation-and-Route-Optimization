"""
User Model for Authentication and Role-Based Authorization.
Supports Driver, Parking Staff, and Super Admin roles.
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from models import db


class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='driver')  # 'driver', 'staff', 'super_admin' (also supports 'user', 'admin')
    facility_id = db.Column(db.String(20), db.ForeignKey('parking_facilities.facility_id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    bookings = db.relationship('Booking', backref='user', lazy=True, cascade='all, delete-orphan', foreign_keys='Booking.user_id')
    assigned_facility = db.relationship('ParkingFacility', backref='staff_members', foreign_keys=[facility_id])

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_super_admin(self) -> bool:
        return self.role in ['super_admin', 'admin']

    @property
    def is_staff(self) -> bool:
        return self.role == 'staff'

    @property
    def is_driver(self) -> bool:
        return self.role in ['driver', 'user']

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'facility_id': self.facility_id,
            'facility_name': self.assigned_facility.facility_name if self.assigned_facility else None,
            'is_active': self.is_active,
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M:%S') if self.last_login else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

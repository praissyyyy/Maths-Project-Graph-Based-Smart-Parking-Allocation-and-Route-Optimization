"""
Vehicle Entry and Exit Logs Model.
Records all physical vehicle movements, check-ins, check-outs, and walk-in arrivals.
"""

from datetime import datetime
from models import db


class VehicleLog(db.Model):
    __tablename__ = 'vehicle_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_id = db.Column(db.String(40), db.ForeignKey('bookings.booking_id'), nullable=True)
    facility_id = db.Column(db.String(20), db.ForeignKey('parking_facilities.facility_id'), nullable=False)
    slot_id = db.Column(db.String(30), db.ForeignKey('parking_slots.slot_id'), nullable=False)
    vehicle_number = db.Column(db.String(40), nullable=False)
    vehicle_type = db.Column(db.String(30), default='Sedan')
    entry_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    exit_time = db.Column(db.DateTime, nullable=True)
    entry_by_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    exit_by_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    status = db.Column(db.String(20), default='IN_PARKING', nullable=False)  # 'IN_PARKING', 'COMPLETED'
    is_walkin = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    booking = db.relationship('Booking', backref='vehicle_logs', lazy=True)
    facility = db.relationship('ParkingFacility', backref='vehicle_logs', lazy=True)
    slot = db.relationship('ParkingSlot', backref='vehicle_logs', lazy=True)
    entry_staff = db.relationship('User', foreign_keys=[entry_by_user_id], backref='entry_logs')
    exit_staff = db.relationship('User', foreign_keys=[exit_by_user_id], backref='exit_logs')

    def to_dict(self):
        return {
            'log_id': self.log_id,
            'booking_id': self.booking_id,
            'facility_id': self.facility_id,
            'facility_name': self.facility.facility_name if self.facility else None,
            'slot_id': self.slot_id,
            'slot_number': self.slot.slot_number if self.slot else None,
            'vehicle_number': self.vehicle_number,
            'vehicle_type': self.vehicle_type,
            'entry_time': self.entry_time.strftime('%Y-%m-%d %H:%M:%S') if self.entry_time else None,
            'exit_time': self.exit_time.strftime('%Y-%m-%d %H:%M:%S') if self.exit_time else None,
            'status': self.status,
            'is_walkin': self.is_walkin,
            'entry_staff_name': self.entry_staff.name if self.entry_staff else 'System',
            'exit_staff_name': self.exit_staff.name if self.exit_staff else None
        }

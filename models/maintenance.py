"""
Slot Maintenance Records Model.
Tracks temporary out-of-service intervals and engineering maintenance for parking slots.
"""

from datetime import datetime
from models import db


class SlotMaintenanceRecord(db.Model):
    __tablename__ = 'slot_maintenance_records'

    maintenance_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    facility_id = db.Column(db.String(20), db.ForeignKey('parking_facilities.facility_id'), nullable=False)
    slot_id = db.Column(db.String(30), db.ForeignKey('parking_slots.slot_id'), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='ACTIVE', nullable=False)  # 'ACTIVE', 'RESOLVED'
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)

    # Relationships
    facility = db.relationship('ParkingFacility', backref='maintenance_records', lazy=True)
    slot = db.relationship('ParkingSlot', backref='maintenance_records', lazy=True)
    recorded_by = db.relationship('User', backref='maintenance_logged', lazy=True)

    def to_dict(self):
        return {
            'maintenance_id': self.maintenance_id,
            'facility_id': self.facility_id,
            'facility_name': self.facility.facility_name if self.facility else None,
            'slot_id': self.slot_id,
            'slot_number': self.slot.slot_number if self.slot else None,
            'reason': self.reason,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,
            'status': self.status,
            'recorded_by': self.recorded_by.name if self.recorded_by else 'Staff'
        }

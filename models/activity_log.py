"""
Admin Activity Audit Log Model.
Permanently logs administrative actions across Staff and Super Admin portals.
"""

from datetime import datetime
from models import db


class AdminActivityLog(db.Model):
    __tablename__ = 'admin_activity_logs'

    activity_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    facility_id = db.Column(db.String(20), db.ForeignKey('parking_facilities.facility_id'), nullable=True)
    action_type = db.Column(db.String(50), nullable=False)
    # Examples: 'LOGIN', 'LOGOUT', 'CHECK_IN', 'CHECK_OUT', 'WALKIN_REGISTER',
    # 'SLOT_STATUS_CHANGE', 'MAINTENANCE_BLOCK', 'MAINTENANCE_RESTORE',
    # 'BOOKING_CONFIRM', 'BOOKING_CANCEL', 'CAPACITY_UPDATE', 'STAFF_CREATE', 'STAFF_EDIT'

    description = db.Column(db.Text, nullable=False)
    target_id = db.Column(db.String(50), nullable=True)  # relevant booking_id, slot_id, or staff_id
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = db.relationship('User', backref='activity_logs', lazy=True)
    facility = db.relationship('ParkingFacility', backref='activity_logs', lazy=True)

    @staticmethod
    def log_action(user_id: int, action_type: str, description: str, facility_id: str = None, target_id: str = None):
        """Helper to append an immutable activity log record."""
        log = AdminActivityLog(
            user_id=user_id,
            facility_id=facility_id,
            action_type=action_type,
            description=description,
            target_id=target_id
        )
        db.session.add(log)
        db.session.commit()
        return log

    def to_dict(self):
        return {
            'activity_id': self.activity_id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else 'Unknown',
            'user_role': self.user.role if self.user else 'Unknown',
            'facility_id': self.facility_id,
            'facility_name': self.facility.facility_name if self.facility else 'System-Wide',
            'action_type': self.action_type,
            'description': self.description,
            'target_id': self.target_id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None
        }

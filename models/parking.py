"""
Parking Facility and Parking Slot Models.
Manages spatial coordinates, capacity, slot layouts, and temporal availability.
Supports automated status evaluation and staff maintenance overrides.
"""

from datetime import datetime
from models import db


class ParkingFacility(db.Model):
    __tablename__ = 'parking_facilities'

    facility_id = db.Column(db.String(20), primary_key=True)
    facility_name = db.Column(db.String(150), nullable=False)
    node_id = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=30)
    initial_occupied = db.Column(db.Integer, nullable=False, default=10)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    slots = db.relationship('ParkingSlot', backref='facility', lazy=True, cascade='all, delete-orphan')
    bookings = db.relationship('Booking', backref='facility', lazy=True)

    def get_dynamic_occupancy(self, start_dt: datetime = None, end_dt: datetime = None) -> dict:
        """
        Calculates occupancy and availability for the facility.
        Ensures the 4 categories (Occupied, Reserved, Maintenance, Available)
        are mutually exclusive and add up exactly to total capacity.
        Utilisation Percentage = (Currently Occupied Slots / Total Capacity) * 100
        """
        from models.booking import Booking
        try:
            Booking.expire_past_bookings()
        except Exception:
            pass

        slots = self.slots
        total_capacity = len(slots) if slots else self.capacity

        occupied_count = 0
        reserved_count = 0
        maintenance_count = 0
        available_count = 0

        for slot in slots:
            status = slot.get_status_for_period(start_dt, end_dt)
            if status == 'occupied':
                occupied_count += 1
            elif status == 'reserved':
                reserved_count += 1
            elif status == 'maintenance':
                maintenance_count += 1
            else:
                available_count += 1

        if not slots:
            occupied_count = min(total_capacity, self.initial_occupied)
            available_count = max(0, total_capacity - occupied_count)

        util_pct = (occupied_count / total_capacity * 100.0) if total_capacity > 0 else 0.0

        return {
            'facility_id': self.facility_id,
            'facility_name': self.facility_name,
            'node_id': self.node_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'capacity': total_capacity,
            'total_capacity': total_capacity,
            'occupied': occupied_count,
            'occupied_count': occupied_count,
            'reserved': reserved_count,
            'reserved_count': reserved_count,
            'maintenance': maintenance_count,
            'maintenance_count': maintenance_count,
            'available': available_count,
            'available_count': available_count,
            'is_active': self.is_active,
            'utilization_pct': round(util_pct, 1)
        }

    def to_dict(self, start_dt: datetime = None, end_dt: datetime = None):
        dynamic_stats = self.get_dynamic_occupancy(start_dt, end_dt)
        return {
            'facility_id': self.facility_id,
            'facility_name': self.facility_name,
            'node_id': self.node_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'capacity': self.capacity,
            'initial_occupied': self.initial_occupied,
            'description': self.description,
            'is_active': self.is_active,
            'current_occupied': dynamic_stats['occupied'],
            'reserved_spaces': dynamic_stats['reserved'],
            'maintenance_spaces': dynamic_stats['maintenance'],
            'available_spaces': dynamic_stats['available'],
            'utilization_pct': dynamic_stats['utilization_pct']
        }


class ParkingSlot(db.Model):
    __tablename__ = 'parking_slots'

    slot_id = db.Column(db.String(30), primary_key=True)
    facility_id = db.Column(db.String(20), db.ForeignKey('parking_facilities.facility_id'), nullable=False)
    slot_number = db.Column(db.String(30), nullable=False)
    initial_status = db.Column(db.String(20), default='available')  # 'occupied' or 'available'
    manual_status = db.Column(db.String(30), default='AUTO')  # 'AUTO', 'OCCUPIED', 'AVAILABLE', 'RESERVED', 'MAINTENANCE'
    maintenance_reason = db.Column(db.String(255), nullable=True)
    maintenance_updated_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    bookings = db.relationship('Booking', backref='slot', lazy=True)

    def is_available_for_period(self, start_dt: datetime, end_dt: datetime) -> bool:
        """
        Rigorously checks if this slot is free during [start_dt, end_dt].
        A slot is NOT available if:
        1. It is currently blocked for maintenance.
        2. It is manually marked occupied or reserved.
        3. It is permanently occupied by initial baseline vehicles (slots 1..10 in simulation).
        4. Any active ('CONFIRMED', 'CHECKED_IN', 'PENDING') booking overlaps: (arr < end_dt and dep > start_dt).
        """
        if self.manual_status in ['MAINTENANCE', 'OCCUPIED', 'RESERVED']:
            return False

        if self.initial_status == 'occupied':
            return False

        from models.booking import Booking

        # Check for overlapping active reservations or checked-in bookings
        overlapping_booking = Booking.query.filter(
            Booking.slot_id == self.slot_id,
            Booking.booking_status.in_(['CONFIRMED', 'CHECKED_IN', 'PENDING']),
            Booking.arrival_datetime < end_dt,
            Booking.departure_datetime > start_dt
        ).first()

        return overlapping_booking is None

    def get_status_for_period(self, start_dt: datetime = None, end_dt: datetime = None) -> str:
        """
        Returns exactly one of the 4 mutually exclusive states:
        - 'maintenance': Temporarily Unavailable / Maintenance
        - 'occupied': Physically occupied by vehicle (checked-in or baseline)
        - 'reserved': Reserved for confirmed/pending booking
        - 'available': Free to park/book
        """
        if self.manual_status == 'MAINTENANCE':
            return 'maintenance'

        if self.manual_status == 'OCCUPIED':
            return 'occupied'

        if self.initial_status == 'occupied':
            return 'occupied'

        from models.booking import Booking

        # 1. First check if there is an actively checked-in vehicle
        checked_in = Booking.query.filter(
            Booking.slot_id == self.slot_id,
            Booking.booking_status == 'CHECKED_IN'
        ).first()
        if checked_in:
            return 'occupied'

        if self.manual_status == 'RESERVED':
            return 'reserved'

        now = datetime.utcnow()

        if start_dt is not None and end_dt is not None:
            # Check confirmed/pending reservations overlapping the specific requested window
            overlap = Booking.query.filter(
                Booking.slot_id == self.slot_id,
                Booking.booking_status.in_(['CONFIRMED', 'PENDING']),
                Booking.arrival_datetime < end_dt,
                Booking.departure_datetime > start_dt
            ).first()
            if overlap:
                return 'reserved'
        else:
            # Snapshot mode (now / upcoming active reservations):
            # Check if active right now
            active_now = Booking.query.filter(
                Booking.slot_id == self.slot_id,
                Booking.booking_status.in_(['CONFIRMED', 'PENDING']),
                Booking.arrival_datetime <= now,
                Booking.departure_datetime >= now
            ).first()
            if active_now:
                return 'reserved'

            # Check if a future reservation exists for this slot (upcoming today or later)
            future_res = Booking.query.filter(
                Booking.slot_id == self.slot_id,
                Booking.booking_status.in_(['CONFIRMED', 'PENDING']),
                Booking.departure_datetime >= now
            ).order_by(Booking.arrival_datetime.asc()).first()
            if future_res:
                return 'reserved'

        return 'available'

    def get_active_or_upcoming_booking(self, start_dt: datetime = None, end_dt: datetime = None):
        """Returns the active or upcoming booking for this slot if any."""
        from models.booking import Booking
        now = datetime.utcnow()
        query = Booking.query.filter(
            Booking.slot_id == self.slot_id,
            Booking.booking_status.in_(['CONFIRMED', 'CHECKED_IN', 'PENDING'])
        )
        if start_dt is not None and end_dt is not None:
            query = query.filter(
                Booking.arrival_datetime < end_dt,
                Booking.departure_datetime > start_dt
            )
        else:
            query = query.filter(Booking.departure_datetime >= now)
        return query.order_by(Booking.arrival_datetime.asc()).first()

    def get_active_booking(self):
        """Returns the currently active booking for this slot if any."""
        return self.get_active_or_upcoming_booking()

    def to_dict(self, start_dt: datetime = None, end_dt: datetime = None):
        return {
            'slot_id': self.slot_id,
            'facility_id': self.facility_id,
            'slot_number': self.slot_number,
            'initial_status': self.initial_status,
            'manual_status': self.manual_status,
            'maintenance_reason': self.maintenance_reason,
            'current_status': self.get_status_for_period(start_dt, end_dt)
        }

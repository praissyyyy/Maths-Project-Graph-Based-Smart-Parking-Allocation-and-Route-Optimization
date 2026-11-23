"""
Database initialization and shared extensions.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import models to ensure registration with SQLAlchemy metadata
from models.user import User
from models.parking import ParkingFacility, ParkingSlot
from models.booking import Booking, RouteHistory
from models.vehicle_log import VehicleLog
from models.activity_log import AdminActivityLog
from models.maintenance import SlotMaintenanceRecord

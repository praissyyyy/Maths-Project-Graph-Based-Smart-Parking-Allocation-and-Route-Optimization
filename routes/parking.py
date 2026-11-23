"""
Parking Facility Views and Information Routes.
Renders home, facility lists, interactive slot grids, and About Project page.
"""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify
from models.parking import ParkingFacility, ParkingSlot
from models.booking import Booking

parking_bp = Blueprint('parking', __name__)


@parking_bp.route('/')
def index():
    """Home landing page with live system capacity statistics."""
    facilities = ParkingFacility.query.all()
    facility_stats = [f.get_dynamic_occupancy() for f in facilities]

    total_facilities = len(facilities)
    total_capacity = sum(f.capacity for f in facilities)
    total_occupied = sum(s['occupied'] for s in facility_stats)
    total_reserved = sum(s['reserved'] for s in facility_stats)
    total_maintenance = sum(s['maintenance'] for s in facility_stats)
    total_available = sum(s['available'] for s in facility_stats)
    system_utilization = round((total_occupied / total_capacity * 100.0), 1) if total_capacity > 0 else 0.0

    return render_template(
        'index.html',
        total_facilities=total_facilities,
        total_capacity=total_capacity,
        total_occupied=total_occupied,
        total_reserved=total_reserved,
        total_maintenance=total_maintenance,
        total_available=total_available,
        system_utilization=system_utilization,
        facilities=facilities,
        facility_stats=facility_stats
    )


@parking_bp.route('/parking')
def list_facilities():
    """Find Parking directory with search and availability filter."""
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all')

    query = ParkingFacility.query
    if search_query:
        query = query.filter(
            ParkingFacility.facility_name.ilike(f'%{search_query}%') |
            ParkingFacility.description.ilike(f'%{search_query}%')
        )

    facilities = query.all()
    facilities_data = []

    for f in facilities:
        stats = f.get_dynamic_occupancy()
        fac_dict = f.to_dict()
        fac_dict.update(stats)
        
        # Apply availability filter if specified
        if status_filter == 'available' and stats['available'] == 0:
            continue
        elif status_filter == 'full' and stats['available'] > 0:
            continue

        facilities_data.append(fac_dict)

    return render_template(
        'parking.html',
        facilities=facilities_data,
        search_query=search_query,
        status_filter=status_filter
    )


@parking_bp.route('/parking/<facility_id>')
def facility_details(facility_id):
    """Detailed view of a single facility including its 30-slot spatial layout with temporal availability filtering."""
    facility = ParkingFacility.query.get_or_404(facility_id)

    # Optional temporal filter from query parameters
    arr_str = request.args.get('arrival')
    dep_str = request.args.get('departure')

    arr_dt = None
    dep_dt = None
    if arr_str and dep_str:
        for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"]:
            try:
                arr_dt = datetime.strptime(arr_str, fmt)
                break
            except ValueError:
                pass
        for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"]:
            try:
                dep_dt = datetime.strptime(dep_str, fmt)
                break
            except ValueError:
                pass

    # Calculate dynamic stats for this window (or now)
    stats = facility.get_dynamic_occupancy(start_dt=arr_dt, end_dt=dep_dt)

    # Slot availability evaluation
    slots = ParkingSlot.query.filter_by(facility_id=facility_id).all()
    slots_data = []
    for s in slots:
        status = s.get_status_for_period(arr_dt, dep_dt)
        active_b = s.get_active_or_upcoming_booking(arr_dt, dep_dt)
        slots_data.append({
            'slot_id': s.slot_id,
            'slot_number': s.slot_number,
            'status': status,
            'selectable': (status == 'available'),
            'maintenance_reason': s.maintenance_reason if status == 'maintenance' else None,
            'reservation_window': {
                'arrival': active_b.arrival_datetime.strftime('%d-%b %I:%M %p'),
                'departure': active_b.departure_datetime.strftime('%d-%b %I:%M %p'),
                'booking_id': active_b.booking_id
            } if active_b else None
        })

    now = datetime.now()
    filter_arrival = arr_str or (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    filter_departure = dep_str or (now + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")

    return render_template(
        'facility_details.html',
        facility=facility,
        stats=stats,
        slots=slots_data,
        is_filtered=(arr_dt is not None and dep_dt is not None),
        filter_arrival=filter_arrival,
        filter_departure=filter_departure
    )


@parking_bp.route('/about')
def about():
    """Comprehensive academic documentation and project methodology."""
    return render_template('about.html')


# ---------------- API Endpoints ---------------- #

@parking_bp.route('/api/facilities')
def api_facilities():
    facilities = ParkingFacility.query.all()
    return jsonify([f.to_dict() for f in facilities])


@parking_bp.route('/api/facility/<facility_id>/slots')
@parking_bp.route('/parking/<facility_id>/slots')
def api_facility_slots(facility_id):
    facility = ParkingFacility.query.get_or_404(facility_id)
    arr_str = request.args.get('arrival')
    dep_str = request.args.get('departure')

    arr_dt = None
    dep_dt = None
    if arr_str and dep_str:
        for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"]:
            try:
                arr_dt = datetime.strptime(arr_str, fmt)
                break
            except ValueError:
                pass
        for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"]:
            try:
                dep_dt = datetime.strptime(dep_str, fmt)
                break
            except ValueError:
                pass

    stats = facility.get_dynamic_occupancy(start_dt=arr_dt, end_dt=dep_dt)

    slots = ParkingSlot.query.filter_by(facility_id=facility_id).all()
    slots_data = []
    for s in slots:
        status = s.get_status_for_period(arr_dt, dep_dt)
        active_b = s.get_active_or_upcoming_booking(arr_dt, dep_dt)
        slots_data.append({
            'slot_id': s.slot_id,
            'slot_number': s.slot_number,
            'status': status,
            'selectable': (status == 'available'),
            'maintenance_reason': s.maintenance_reason if status == 'maintenance' else None,
            'reservation_window': {
                'arrival': active_b.arrival_datetime.strftime('%d-%b %I:%M %p'),
                'departure': active_b.departure_datetime.strftime('%d-%b %I:%M %p'),
                'booking_id': active_b.booking_id
            } if active_b else None
        })

    return jsonify({
        'facility_id': facility_id,
        'facility_name': facility.facility_name,
        'capacity': facility.capacity,
        'stats': stats,
        'slots': slots_data
    })

"""
Parking Reservation and Slot Booking Routes.
Implements temporal concurrency validation, double-booking prevention,
shortest-path calculation, and cancellation workflows.
"""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from models import db
from models.user import User
from models.parking import ParkingFacility, ParkingSlot
from models.booking import Booking, RouteHistory, generate_booking_id
from algorithms.dijkstra import dijkstra_shortest_path
from algorithms.astar import astar_shortest_path

booking_bp = Blueprint('booking', __name__)


@booking_bp.route('/booking', methods=['GET', 'POST'])
@booking_bp.route('/booking/new', methods=['GET', 'POST'])
def new_booking():
    facilities = ParkingFacility.query.all()
    selected_facility_id = request.args.get('facility_id', 'P1')
    selected_slot_id = request.args.get('slot_id', '')

    if request.method == 'POST':
        # 1. Retrieve and sanitize form inputs
        customer_name = request.form.get('customer_name', '').strip()
        customer_email = request.form.get('customer_email', '').strip().lower()
        customer_phone = request.form.get('customer_phone', '').strip()
        vehicle_number = request.form.get('vehicle_number', '').strip().upper()
        vehicle_type = request.form.get('vehicle_type', 'Sedan').strip()
        facility_id = request.form.get('facility_id', '').strip()
        slot_id = request.form.get('slot_id', '').strip()
        start_location = request.form.get('start_location', 'Gandhipuram North Junction').strip()
        arrival_str = request.form.get('arrival_datetime', '').strip()
        departure_str = request.form.get('departure_datetime', '').strip()
        routing_algo = request.form.get('routing_algorithm', 'A*').strip()

        # 2. Basic field presence validation
        if not (customer_name and customer_email and vehicle_number and facility_id and slot_id and arrival_str and departure_str):
            flash("All fields marked with an asterisk are required.", "danger")
            return redirect(url_for('booking.new_booking', facility_id=facility_id, slot_id=slot_id))

        # 3. Parse and validate timestamps
        try:
            arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%dT%H:%M")
            departure_dt = datetime.strptime(departure_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            try:
                arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d %H:%M")
                departure_dt = datetime.strptime(departure_str, "%Y-%m-%d %H:%M")
            except ValueError:
                flash("Invalid date/time format. Please select valid arrival and departure times.", "danger")
                return redirect(url_for('booking.new_booking', facility_id=facility_id, slot_id=slot_id))

        if arrival_dt >= departure_dt:
            flash("Departure time must be strictly after arrival time.", "danger")
            return redirect(url_for('booking.new_booking', facility_id=facility_id, slot_id=slot_id))

        if (departure_dt - arrival_dt) < timedelta(minutes=15):
            flash("Minimum parking reservation duration is 15 minutes.", "danger")
            return redirect(url_for('booking.new_booking', facility_id=facility_id, slot_id=slot_id))

        # 4. Validate facility and slot existence
        facility = db.session.get(ParkingFacility, facility_id)
        slot = db.session.get(ParkingSlot, slot_id)

        if not facility or not slot or slot.facility_id != facility_id:
            flash("Invalid parking facility or slot selected.", "danger")
            return redirect(url_for('booking.new_booking', facility_id=facility_id))

        # 5. Temporal Concurrency and Double-Booking Prevention Rule
        # Check if slot is baseline occupied
        if slot.initial_status == 'occupied':
            flash(f"Slot {slot.slot_number} is reserved for baseline vehicles. Please select an available slot.", "danger")
            return redirect(url_for('booking.new_booking', facility_id=facility_id))

        # Check if slot is under maintenance
        if slot.manual_status == 'MAINTENANCE':
            flash(f"Slot {slot.slot_number} is temporarily unavailable due to maintenance ({slot.maintenance_reason or 'scheduled maintenance'}). Please select another slot.", "danger")
            return redirect(url_for('booking.new_booking', facility_id=facility_id))

        if slot.manual_status in ['OCCUPIED', 'RESERVED']:
            flash(f"Slot {slot.slot_number} is currently marked as {slot.manual_status.lower()}. Please select an available slot.", "danger")
            return redirect(url_for('booking.new_booking', facility_id=facility_id))

        # Expire past bookings before evaluating overlaps
        Booking.expire_past_bookings()

        # Check overlapping active bookings: (arr < dep_new AND dep > arr_new)
        overlapping_booking = Booking.query.filter(
            Booking.slot_id == slot_id,
            Booking.booking_status.in_(['CONFIRMED', 'CHECKED_IN', 'PENDING']),
            Booking.arrival_datetime < departure_dt,
            Booking.departure_datetime > arrival_dt
        ).first()

        if overlapping_booking:
            flash(
                f"Slot {slot.slot_number} is already booked from "
                f"{overlapping_booking.arrival_datetime.strftime('%d-%b %I:%M %p')} to "
                f"{overlapping_booking.departure_datetime.strftime('%d-%b %I:%M %p')}. "
                "Please choose another slot or time period.",
                "danger"
            )
            return redirect(url_for('booking.new_booking', facility_id=facility_id, slot_id=slot_id, arrival=arrival_str, departure=departure_str))

        # 6. Authenticate or create user record
        user_id = session.get('user_id')
        if not user_id:
            user = User.query.filter_by(email=customer_email).first()
            if not user:
                user = User(
                    name=customer_name,
                    email=customer_email,
                    phone=customer_phone,
                    role='user'
                )
                user.set_password("SmartPark@Guest2026")
                db.session.add(user)
                db.session.flush()
            user_id = user.user_id

        # 7. Shortest-path route calculation using road network backend
        route_dist = 1200.0  # reasonable fallback
        exec_time = 0.003
        di_g = current_app.config.get('ROAD_GRAPH')

        if di_g is not None and facility.node_id in di_g:
            # Pick a starting node (either facility.node_id neighbor or first SCC node)
            start_node = str(list(di_g.nodes())[10])
            dest_node = str(facility.node_id)
            if routing_algo == "Dijkstra":
                p, d, _, t = dijkstra_shortest_path(di_g, start_node, dest_node)
            else:
                p, d, _, t = astar_shortest_path(di_g, start_node, dest_node)

            if p and d < 1e6:
                route_dist = d
                exec_time = t

        # 8. Create and persist reservation in database
        b_id = generate_booking_id()
        booking = Booking(
            booking_id=b_id,
            user_id=user_id,
            facility_id=facility_id,
            slot_id=slot_id,
            vehicle_number=vehicle_number,
            vehicle_type=vehicle_type,
            start_location=start_location,
            arrival_datetime=arrival_dt,
            departure_datetime=departure_dt,
            booking_status='CONFIRMED'
        )
        db.session.add(booking)
        db.session.flush()

        # Telemetry record
        rh = RouteHistory(
            booking_id=b_id,
            algorithm=routing_algo,
            distance=route_dist,
            execution_time=exec_time
        )
        db.session.add(rh)
        db.session.commit()

        flash(f"Booking confirmed successfully! Your booking reference is {b_id}", "success")
        return redirect(url_for('booking.confirmation', booking_id=b_id))

    # GET request: render booking form
    now = datetime.now()
    req_arrival = request.args.get('arrival')
    req_departure = request.args.get('departure')

    default_arrival = req_arrival or (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    default_departure = req_departure or (now + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")

    return render_template(
        'booking.html',
        facilities=facilities,
        selected_facility_id=selected_facility_id,
        selected_slot_id=selected_slot_id,
        default_arrival=default_arrival,
        default_departure=default_departure
    )


@booking_bp.route('/booking/confirmation/<booking_id>')
def confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    route_info = RouteHistory.query.filter_by(booking_id=booking_id).first()

    return render_template(
        'booking_confirmation.html',
        booking=booking,
        route_info=route_info
    )


@booking_bp.route('/my-bookings')
def my_bookings():
    Booking.expire_past_bookings()
    user_id = session.get('user_id')
    search_ref = request.args.get('search_ref', '').strip()

    if user_id:
        bookings = Booking.query.filter_by(user_id=user_id).order_by(Booking.created_at.desc()).all()
    elif search_ref:
        bookings = Booking.query.filter(
            (Booking.booking_id == search_ref) |
            (Booking.vehicle_number == search_ref.upper())
        ).order_by(Booking.created_at.desc()).all()
    else:
        bookings = []

    return render_template(
        'my_bookings.html',
        bookings=bookings,
        search_ref=search_ref
    )


@booking_bp.route('/booking/cancel/<booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        flash("Booking record not found.", "danger")
        return redirect(url_for('booking.my_bookings'))

    user_id = session.get('user_id')
    user_role = session.get('user_role')

    # Allow cancellation by owner or authorized staff/admin
    is_owner = (user_id and user_id == booking.user_id)
    is_admin = (user_role in ['admin', 'super_admin', 'staff'])

    if not (is_owner or is_admin):
        flash("You are not authorized to cancel this booking.", "danger")
        return redirect(url_for('booking.my_bookings'))

    if booking.booking_status == 'CANCELLED':
        flash("This booking has already been cancelled.", "info")
    elif booking.booking_status == 'CHECKED_IN':
        flash("Cannot cancel a booking that has actively checked in. Please process vehicle exit at the gate.", "danger")
    elif booking.booking_status in ['COMPLETED', 'EXPIRED']:
        flash(f"Cannot cancel a booking that is already {booking.booking_status.lower()}.", "warning")
    else:
        slot_number = booking.slot.slot_number if booking.slot else booking.slot_id
        facility_name = booking.facility.facility_name if booking.facility else booking.facility_id
        booking.cancel()
        flash(f"Reservation {booking.booking_id} for slot {slot_number} at {facility_name} has been cancelled successfully. The slot is now released.", "success")

    return redirect(url_for('booking.my_bookings'))

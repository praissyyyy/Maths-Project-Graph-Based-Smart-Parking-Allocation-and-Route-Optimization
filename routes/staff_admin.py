"""
Parking Lot Staff Admin Portal Routes.
Provides facility-scoped management for authorized parking lot staff:
Dashboard, Slot Management, Booking Workflow, Vehicle Entry/Exit,
Walk-in Registration, Occupancy Analytics, Reports (with CSV export),
Audit Logs, and Profile.
"""

import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, Response
from models import db
from models.user import User
from models.parking import ParkingFacility, ParkingSlot
from models.booking import Booking, generate_booking_id
from models.vehicle_log import VehicleLog
from models.activity_log import AdminActivityLog
from models.maintenance import SlotMaintenanceRecord
from routes.auth import staff_required

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')


def get_current_facility():
    """Retrieve and validate the facility assigned to the currently logged in staff member."""
    facility_id = session.get('facility_id')
    if not facility_id:
        return None
    return db.session.get(ParkingFacility, facility_id)


# =========================================================================
# A. STAFF DASHBOARD
# =========================================================================
@staff_bp.route('/')
@staff_bp.route('/dashboard')
@staff_required
def dashboard():
    facility = get_current_facility()
    if not facility:
        flash("Assigned parking facility not found.", "danger")
        return redirect(url_for('parking.index'))

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_end = today_start + timedelta(days=1)

    # Calculate live facility statistics
    stats = facility.get_dynamic_occupancy()

    # Active bookings right now
    active_bookings = Booking.query.filter(
        Booking.facility_id == facility.facility_id,
        Booking.booking_status.in_(['CHECKED_IN', 'CONFIRMED']),
        Booking.arrival_datetime <= now,
        Booking.departure_datetime >= now
    ).order_by(Booking.arrival_datetime.asc()).all()

    # Upcoming bookings in next 24 hours
    upcoming_bookings = Booking.query.filter(
        Booking.facility_id == facility.facility_id,
        Booking.booking_status.in_(['CONFIRMED', 'PENDING']),
        Booking.arrival_datetime > now,
        Booking.arrival_datetime <= now + timedelta(hours=24)
    ).order_by(Booking.arrival_datetime.asc()).limit(10).all()

    # Today's vehicle entries and exits
    today_entries = VehicleLog.query.filter(
        VehicleLog.facility_id == facility.facility_id,
        VehicleLog.entry_time >= today_start,
        VehicleLog.entry_time < today_end
    ).count()

    today_exits = VehicleLog.query.filter(
        VehicleLog.facility_id == facility.facility_id,
        VehicleLog.exit_time >= today_start,
        VehicleLog.exit_time < today_end
    ).count()

    # Recent activities for this facility
    recent_activities = AdminActivityLog.query.filter(
        AdminActivityLog.facility_id == facility.facility_id
    ).order_by(AdminActivityLog.timestamp.desc()).limit(10).all()

    return render_template(
        'staff/dashboard.html',
        facility=facility,
        stats=stats,
        active_bookings=active_bookings,
        upcoming_bookings=upcoming_bookings,
        today_entries=today_entries,
        today_exits=today_exits,
        recent_activities=recent_activities
    )


# =========================================================================
# B. PARKING SLOT MANAGEMENT
# =========================================================================
@staff_bp.route('/slots')
@staff_required
def slots_management():
    facility = get_current_facility()
    search_slot = request.args.get('search_slot', '').strip().upper()
    status_filter = request.args.get('status_filter', 'ALL')

    slots_query = ParkingSlot.query.filter_by(facility_id=facility.facility_id)
    if search_slot:
        slots_query = slots_query.filter(ParkingSlot.slot_number.ilike(f'%{search_slot}%'))

    slots = slots_query.all()
    slots_data = []

    for s in slots:
        status = s.get_status_for_period()
        if status_filter != 'ALL' and status.upper() != status_filter.upper():
            continue

        active_b = s.get_active_booking()
        slots_data.append({
            'slot_id': s.slot_id,
            'slot_number': s.slot_number,
            'status': status,  # available, occupied, reserved, maintenance
            'manual_status': s.manual_status,
            'maintenance_reason': s.maintenance_reason,
            'active_booking': active_b
        })

    stats = facility.get_dynamic_occupancy()

    return render_template(
        'staff/slots.html',
        facility=facility,
        slots=slots_data,
        stats=stats,
        search_slot=search_slot,
        status_filter=status_filter
    )


@staff_bp.route('/slot/update-status', methods=['POST'])
@staff_required
def update_slot_status():
    facility = get_current_facility()
    slot_id = request.form.get('slot_id')
    new_status = request.form.get('new_status')  # 'AUTO', 'OCCUPIED', 'AVAILABLE', 'RESERVED', 'MAINTENANCE'
    reason = request.form.get('reason', '').strip()

    slot = db.session.get(ParkingSlot, slot_id)
    if not slot or slot.facility_id != facility.facility_id:
        flash("Invalid parking slot selected.", "danger")
        return redirect(url_for('staff.slots_management'))

    now = datetime.utcnow()

    # Rule: Prevent staff from marking available if active vehicle or reservation exists!
    if new_status == 'AVAILABLE':
        active_b = slot.get_active_booking()
        if active_b and active_b.booking_status == 'CHECKED_IN':
            flash(f"Cannot mark slot {slot.slot_number} as available: Vehicle {active_b.vehicle_number} is actively checked in.", "danger")
            return redirect(url_for('staff.slots_management'))
        if active_b and active_b.booking_status == 'CONFIRMED' and active_b.arrival_datetime <= now <= active_b.departure_datetime:
            flash(f"Cannot mark slot {slot.slot_number} as available: Active reservation {active_b.booking_id} currently holds this slot.", "danger")
            return redirect(url_for('staff.slots_management'))

    old_status = slot.manual_status
    slot.manual_status = new_status

    if new_status == 'MAINTENANCE':
        slot.maintenance_reason = reason or "Scheduled engineering inspection"
        slot.maintenance_updated_at = now

        # Add maintenance record
        m_rec = SlotMaintenanceRecord(
            facility_id=facility.facility_id,
            slot_id=slot.slot_id,
            reason=slot.maintenance_reason,
            start_time=now,
            status='ACTIVE',
            recorded_by_user_id=session['user_id']
        )
        db.session.add(m_rec)
        action_type = "MAINTENANCE_BLOCK"
        log_desc = f"Slot {slot.slot_number} marked under maintenance: {slot.maintenance_reason}"
    else:
        # Check if resolving an active maintenance record
        active_m = SlotMaintenanceRecord.query.filter_by(
            slot_id=slot.slot_id, status='ACTIVE'
        ).first()
        if active_m:
            active_m.status = 'RESOLVED'
            active_m.end_time = now

        slot.maintenance_reason = None
        action_type = "SLOT_STATUS_CHANGE"
        log_desc = f"Slot {slot.slot_number} status updated from {old_status} to {new_status}."

    db.session.commit()

    # Audit log
    AdminActivityLog.log_action(
        user_id=session['user_id'],
        action_type=action_type,
        description=log_desc,
        facility_id=facility.facility_id,
        target_id=slot.slot_id
    )

    flash(f"Slot {slot.slot_number} updated successfully.", "success")
    return redirect(url_for('staff.slots_management'))


# =========================================================================
# C. BOOKING MANAGEMENT
# =========================================================================
@staff_bp.route('/bookings')
@staff_required
def bookings_management():
    facility = get_current_facility()
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'ALL')
    date_filter = request.args.get('date', '')

    query = Booking.query.filter_by(facility_id=facility.facility_id)

    if search_query:
        query = query.filter(
            (Booking.booking_id.ilike(f'%{search_query}%')) |
            (Booking.vehicle_number.ilike(f'%{search_query}%')) |
            (Booking.user.has(User.name.ilike(f'%{search_query}%')))
        )

    if status_filter != 'ALL':
        query = query.filter(Booking.booking_status == status_filter)

    if date_filter:
        try:
            target_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            start_of_day = datetime(target_date.year, target_date.month, target_date.day)
            end_of_day = start_of_day + timedelta(days=1)
            query = query.filter(Booking.arrival_datetime >= start_of_day, Booking.arrival_datetime < end_of_day)
        except ValueError:
            pass

    bookings = query.order_by(Booking.created_at.desc()).limit(100).all()

    return render_template(
        'staff/bookings.html',
        facility=facility,
        bookings=bookings,
        search_query=search_query,
        status_filter=status_filter,
        date_filter=date_filter
    )


@staff_bp.route('/booking/action', methods=['POST'])
@staff_required
def booking_action():
    facility = get_current_facility()
    booking_id = request.form.get('booking_id')
    action = request.form.get('action')  # 'CONFIRM', 'CHECK_IN', 'CHECK_OUT', 'CANCEL', 'NO_SHOW'

    booking = db.session.get(Booking, booking_id)
    if not booking or booking.facility_id != facility.facility_id:
        flash("Booking not found or does not belong to your facility.", "danger")
        return redirect(url_for('staff.bookings_management'))

    now = datetime.utcnow()
    staff_id = session['user_id']

    if action == 'CHECK_IN':
        booking.check_in(staff_id)
        # Log vehicle entry
        v_log = VehicleLog(
            booking_id=booking.booking_id,
            facility_id=facility.facility_id,
            slot_id=booking.slot_id,
            vehicle_number=booking.vehicle_number,
            vehicle_type=booking.vehicle_type,
            entry_time=now,
            status='IN_PARKING',
            entry_by_user_id=staff_id
        )
        db.session.add(v_log)
        db.session.commit()
        AdminActivityLog.log_action(
            user_id=staff_id,
            action_type="CHECK_IN",
            description=f"Vehicle {booking.vehicle_number} checked in for booking {booking.booking_id}.",
            facility_id=facility.facility_id,
            target_id=booking.booking_id
        )
        flash(f"Vehicle {booking.vehicle_number} checked in to slot {booking.slot.slot_number}.", "success")

    elif action == 'CHECK_OUT':
        booking.check_out(staff_id)
        # Find active vehicle log
        v_log = VehicleLog.query.filter_by(
            booking_id=booking.booking_id, status='IN_PARKING'
        ).first()
        if v_log:
            v_log.status = 'COMPLETED'
            v_log.exit_time = now
            v_log.exit_by_user_id = staff_id

        db.session.commit()
        AdminActivityLog.log_action(
            user_id=staff_id,
            action_type="CHECK_OUT",
            description=f"Vehicle {booking.vehicle_number} checked out. Slot {booking.slot.slot_number} freed.",
            facility_id=facility.facility_id,
            target_id=booking.booking_id
        )
        flash(f"Vehicle {booking.vehicle_number} checked out successfully.", "success")

    elif action == 'CANCEL':
        booking.cancel()
        AdminActivityLog.log_action(
            user_id=staff_id,
            action_type="BOOKING_CANCEL",
            description=f"Booking {booking.booking_id} cancelled by staff.",
            facility_id=facility.facility_id,
            target_id=booking.booking_id
        )
        flash(f"Booking {booking.booking_id} cancelled.", "warning")

    elif action == 'NO_SHOW':
        booking.booking_status = 'NO_SHOW'
        db.session.commit()
        AdminActivityLog.log_action(
            user_id=staff_id,
            action_type="BOOKING_NO_SHOW",
            description=f"Booking {booking.booking_id} marked as No Show.",
            facility_id=facility.facility_id,
            target_id=booking.booking_id
        )
        flash(f"Booking {booking.booking_id} marked as No Show.", "info")

    return redirect(request.referrer or url_for('staff.bookings_management'))


# =========================================================================
# D. VEHICLE ENTRY AND EXIT MANAGEMENT
# =========================================================================
@staff_bp.route('/entry-exit')
@staff_required
def entry_exit():
    facility = get_current_facility()
    search_term = request.args.get('search_term', '').strip()

    search_result_booking = None
    search_result_active_log = None

    if search_term:
        # Search by booking ID or vehicle registration
        search_result_booking = Booking.query.filter(
            Booking.facility_id == facility.facility_id,
            (Booking.booking_id == search_term) | (Booking.vehicle_number == search_term.upper()),
            Booking.booking_status.in_(['CONFIRMED', 'CHECKED_IN'])
        ).order_by(Booking.arrival_datetime.desc()).first()

        search_result_active_log = VehicleLog.query.filter(
            VehicleLog.facility_id == facility.facility_id,
            VehicleLog.vehicle_number == search_term.upper(),
            VehicleLog.status == 'IN_PARKING'
        ).first()

    # Active vehicles currently in parking lot
    currently_parked = VehicleLog.query.filter_by(
        facility_id=facility.facility_id,
        status='IN_PARKING'
    ).order_by(VehicleLog.entry_time.desc()).all()

    # Available slots for walk-in assignment
    all_slots = ParkingSlot.query.filter_by(facility_id=facility.facility_id).all()
    available_slots = [s for s in all_slots if s.get_status_for_period() == 'available']

    stats = facility.get_dynamic_occupancy()

    return render_template(
        'staff/entry_exit.html',
        facility=facility,
        search_term=search_term,
        booking=search_result_booking,
        active_log=search_result_active_log,
        currently_parked=currently_parked,
        available_slots=available_slots,
        stats=stats
    )


@staff_bp.route('/walk-in', methods=['POST'])
@staff_required
def walkin_entry():
    facility = get_current_facility()
    vehicle_number = request.form.get('vehicle_number', '').strip().upper()
    vehicle_type = request.form.get('vehicle_type', 'Sedan')
    slot_id = request.form.get('slot_id')
    driver_name = request.form.get('driver_name', 'Walk-in Driver').strip()
    driver_phone = request.form.get('driver_phone', '').strip()
    hours = request.form.get('duration_hours', type=int) or 2

    if not vehicle_number or not slot_id:
        flash("Vehicle registration number and slot selection are required.", "danger")
        return redirect(url_for('staff.entry_exit'))

    # Check facility capacity
    stats = facility.get_dynamic_occupancy()
    if stats['available'] <= 0:
        flash("Facility is at maximum capacity. Cannot admit walk-in vehicle.", "danger")
        return redirect(url_for('staff.entry_exit'))

    slot = db.session.get(ParkingSlot, slot_id)
    if not slot or slot.facility_id != facility.facility_id:
        flash("Invalid parking slot selected.", "danger")
        return redirect(url_for('staff.entry_exit'))

    now = datetime.utcnow()
    dep_time = now + timedelta(hours=hours)

    # Check slot availability
    if not slot.is_available_for_period(now, dep_time):
        flash(f"Slot {slot.slot_number} is already occupied or reserved during this window. Choose another slot.", "danger")
        return redirect(url_for('staff.entry_exit'))

    # Register guest driver or find existing
    guest_email = f"walkin_{vehicle_number.replace(' ', '')}@smartpark.local"
    user = User.query.filter_by(email=guest_email).first()
    if not user:
        user = User(
            name=driver_name,
            email=guest_email,
            phone=driver_phone,
            role='driver',
            is_active=True
        )
        user.set_password("WalkIn@2026")
        db.session.add(user)
        db.session.flush()

    staff_id = session['user_id']
    b_id = generate_booking_id()

    booking = Booking(
        booking_id=b_id,
        user_id=user.user_id,
        facility_id=facility.facility_id,
        slot_id=slot.slot_id,
        vehicle_number=vehicle_number,
        vehicle_type=vehicle_type,
        start_location="Walk-in Facility Entrance",
        arrival_datetime=now,
        departure_datetime=dep_time,
        booking_status='CHECKED_IN',
        is_walkin=True,
        check_in_time=now,
        checked_in_by=staff_id
    )
    db.session.add(booking)
    db.session.flush()

    # Create vehicle log
    v_log = VehicleLog(
        booking_id=b_id,
        facility_id=facility.facility_id,
        slot_id=slot.slot_id,
        vehicle_number=vehicle_number,
        vehicle_type=vehicle_type,
        entry_time=now,
        status='IN_PARKING',
        entry_by_user_id=staff_id,
        is_walkin=True
    )
    db.session.add(v_log)
    db.session.commit()

    AdminActivityLog.log_action(
        user_id=staff_id,
        action_type="WALKIN_REGISTER",
        description=f"Walk-in vehicle {vehicle_number} registered and checked in to slot {slot.slot_number}.",
        facility_id=facility.facility_id,
        target_id=b_id
    )

    flash(f"Walk-in vehicle {vehicle_number} successfully registered and assigned to slot {slot.slot_number}.", "success")
    return redirect(url_for('staff.entry_exit'))


# =========================================================================
# E. OCCUPANCY MONITORING
# =========================================================================
@staff_bp.route('/occupancy')
@staff_required
def occupancy_monitoring():
    facility = get_current_facility()
    range_filter = request.args.get('range', 'week')  # today, week, month

    now = datetime.utcnow()
    if range_filter == 'today':
        start_date = datetime(now.year, now.month, now.day)
    elif range_filter == 'month':
        start_date = now - timedelta(days=30)
    else:  # week default
        start_date = now - timedelta(days=7)

    stats = facility.get_dynamic_occupancy()

    # Daily entries and exits over past 7 days for Chart.js
    daily_labels = []
    daily_entries_data = []
    daily_exits_data = []

    for i in range(6, -1, -1):
        day_start = datetime(now.year, now.month, now.day) - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        daily_labels.append(day_start.strftime("%a (%d-%b)"))

        e_cnt = VehicleLog.query.filter(
            VehicleLog.facility_id == facility.facility_id,
            VehicleLog.entry_time >= day_start,
            VehicleLog.entry_time < day_end
        ).count()
        daily_entries_data.append(e_cnt)

        x_cnt = VehicleLog.query.filter(
            VehicleLog.facility_id == facility.facility_id,
            VehicleLog.exit_time >= day_start,
            VehicleLog.exit_time < day_end
        ).count()
        daily_exits_data.append(x_cnt)

    return render_template(
        'staff/occupancy.html',
        facility=facility,
        stats=stats,
        range_filter=range_filter,
        chart_data={
            'labels': daily_labels,
            'entries': daily_entries_data,
            'exits': daily_exits_data,
            'occupied': stats['occupied'],
            'reserved': stats['reserved'],
            'available': stats['available'],
            'maintenance': stats['maintenance']
        }
    )


# =========================================================================
# F. REPORTS AND ACTIVITY LOGS
# =========================================================================
@staff_bp.route('/reports')
@staff_required
def reports():
    facility = get_current_facility()
    report_type = request.args.get('type', 'daily')  # daily, weekly, monthly, completed, cancelled, entries
    export_csv = request.args.get('export', 'false').lower() == 'true'

    now = datetime.utcnow()
    query = Booking.query.filter_by(facility_id=facility.facility_id)

    if report_type == 'daily':
        start_dt = datetime(now.year, now.month, now.day)
        query = query.filter(Booking.created_at >= start_dt)
        title = "Today's Booking Report"
    elif report_type == 'weekly':
        start_dt = now - timedelta(days=7)
        query = query.filter(Booking.created_at >= start_dt)
        title = "Weekly Booking Report"
    elif report_type == 'monthly':
        start_dt = now - timedelta(days=30)
        query = query.filter(Booking.created_at >= start_dt)
        title = "Monthly Booking Report"
    elif report_type == 'completed':
        query = query.filter(Booking.booking_status == 'COMPLETED')
        title = "Completed Bookings Report"
    elif report_type == 'cancelled':
        query = query.filter(Booking.booking_status == 'CANCELLED')
        title = "Cancelled Bookings Report"
    elif report_type == 'no_show':
        query = query.filter(Booking.booking_status == 'NO_SHOW')
        title = "No-Show Bookings Report"
    else:
        title = "All Bookings Report"

    records = query.order_by(Booking.created_at.desc()).all()

    # CSV Export
    if export_csv:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Booking ID', 'Customer Name', 'Phone', 'Vehicle Number', 'Slot', 'Arrival', 'Departure', 'Status', 'Walk-in', 'Created At'])
        for r in records:
            writer.writerow([
                r.booking_id,
                r.user.name if r.user else 'Guest',
                r.user.phone if r.user else '',
                r.vehicle_number,
                r.slot.slot_number if r.slot else '',
                r.arrival_datetime.strftime('%Y-%m-%d %H:%M'),
                r.departure_datetime.strftime('%Y-%m-%d %H:%M'),
                r.booking_status,
                'Yes' if r.is_walkin else 'No',
                r.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=staff_{facility.facility_id}_{report_type}_report.csv"}
        )

    return render_template(
        'staff/reports.html',
        facility=facility,
        title=title,
        report_type=report_type,
        records=records
    )


@staff_bp.route('/activity-logs')
@staff_required
def activity_logs():
    facility = get_current_facility()
    action_filter = request.args.get('action', 'ALL')

    query = AdminActivityLog.query.filter_by(facility_id=facility.facility_id)
    if action_filter != 'ALL':
        query = query.filter(AdminActivityLog.action_type == action_filter)

    logs = query.order_by(AdminActivityLog.timestamp.desc()).limit(100).all()

    return render_template(
        'staff/activity_logs.html',
        facility=facility,
        logs=logs,
        action_filter=action_filter
    )


# =========================================================================
# G. STAFF PROFILE
# =========================================================================
@staff_bp.route('/profile', methods=['GET', 'POST'])
@staff_required
def profile():
    facility = get_current_facility()
    user = db.session.get(User, session['user_id'])

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if phone:
            user.phone = phone

        if new_password:
            if not user.check_password(current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for('staff.profile'))
            if new_password != confirm_password:
                flash("New passwords do not match.", "danger")
                return redirect(url_for('staff.profile'))
            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "danger")
                return redirect(url_for('staff.profile'))

            user.set_password(new_password)
            AdminActivityLog.log_action(
                user_id=user.user_id,
                action_type="PASSWORD_CHANGE",
                description=f"Staff {user.name} changed their account password.",
                facility_id=facility.facility_id
            )
            flash("Password updated successfully.", "success")

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for('staff.profile'))

    recent_logins = AdminActivityLog.query.filter_by(
        user_id=user.user_id,
        action_type="LOGIN"
    ).order_by(AdminActivityLog.timestamp.desc()).limit(5).all()

    return render_template(
        'staff/profile.html',
        facility=facility,
        user=user,
        recent_logins=recent_logins
    )

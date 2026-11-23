"""
Central Super Admin Portal Routes.
Provides system-wide administrative control:
System Overview, Multi-Facility Management, Staff Account Administration,
Global Bookings Audit, Vehicle Movement Logs, Cross-Facility Reports (with CSV export),
System Activity Logs, and Infrastructure Settings.
"""

import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, Response
from models import db
from models.user import User
from models.parking import ParkingFacility, ParkingSlot
from models.booking import Booking
from models.vehicle_log import VehicleLog
from models.activity_log import AdminActivityLog
from models.maintenance import SlotMaintenanceRecord
from routes.auth import super_admin_required

super_admin_bp = Blueprint('super_admin', __name__, url_prefix='/super-admin')


# =========================================================================
# A. SUPER ADMIN OVERVIEW
# =========================================================================
@super_admin_bp.route('/')
@super_admin_bp.route('/dashboard')
@super_admin_required
def dashboard():
    facilities = ParkingFacility.query.all()
    facility_stats = [f.get_dynamic_occupancy() for f in facilities]

    total_facilities = len(facilities)
    total_capacity = sum(f.capacity for f in facilities)
    total_occupied = sum(s['occupied'] for s in facility_stats)
    total_reserved = sum(s['reserved'] for s in facility_stats)
    total_maintenance = sum(s['maintenance'] for s in facility_stats)
    total_available = sum(s['available'] for s in facility_stats)
    system_utilization = round(total_occupied / total_capacity * 100.0, 1) if total_capacity > 0 else 0.0

    # User & Staff Counts
    total_users = User.query.filter(User.role.in_(['driver', 'user'])).count()
    total_staff = User.query.filter_by(role='staff').count()

    # Booking metrics
    total_bookings = Booking.query.count()
    active_bookings = Booking.query.filter(Booking.booking_status.in_(['CONFIRMED', 'CHECKED_IN'])).count()

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_end = today_start + timedelta(days=1)

    today_bookings = Booking.query.filter(Booking.created_at >= today_start, Booking.created_at < today_end).count()
    today_entries = VehicleLog.query.filter(VehicleLog.entry_time >= today_start, VehicleLog.entry_time < today_end).count()
    today_exits = VehicleLog.query.filter(VehicleLog.exit_time >= today_start, VehicleLog.exit_time < today_end).count()

    # Chart Data Preparation
    facility_labels = [f.facility_name.split(' - ')[0] for f in facilities]
    facility_utilizations = [s['utilization_pct'] for s in facility_stats]
    facility_occupancies = [s['occupied'] for s in facility_stats]
    facility_availabilities = [s['available'] for s in facility_stats]

    recent_activities = AdminActivityLog.query.order_by(
        AdminActivityLog.timestamp.desc()
    ).limit(10).all()

    return render_template(
        'super_admin/dashboard.html',
        total_facilities=total_facilities,
        total_capacity=total_capacity,
        total_occupied=total_occupied,
        total_reserved=total_reserved,
        total_maintenance=total_maintenance,
        total_available=total_available,
        system_utilization=system_utilization,
        total_users=total_users,
        total_staff=total_staff,
        total_bookings=total_bookings,
        active_bookings=active_bookings,
        today_bookings=today_bookings,
        today_entries=today_entries,
        today_exits=today_exits,
        facilities=facilities,
        facility_stats=facility_stats,
        recent_activities=recent_activities,
        chart_data={
            'labels': facility_labels,
            'utilizations': facility_utilizations,
            'occupancies': facility_occupancies,
            'availabilities': facility_availabilities,
            'occupied_total': total_occupied,
            'reserved_total': total_reserved,
            'available_total': total_available,
            'maintenance_total': total_maintenance
        }
    )


# =========================================================================
# B. PARKING FACILITY MANAGEMENT
# =========================================================================
@super_admin_bp.route('/facilities')
@super_admin_required
def facilities_list():
    facilities = ParkingFacility.query.all()
    facility_data = []

    for f in facilities:
        stats = f.get_dynamic_occupancy()
        assigned_staff_list = User.query.filter_by(facility_id=f.facility_id, role='staff').all()
        facility_data.append({
            'facility': f,
            'stats': stats,
            'staff': assigned_staff_list,
            'slot_count': len(f.slots)
        })

    return render_template(
        'super_admin/facilities.html',
        facilities_data=facility_data
    )


@super_admin_bp.route('/facility/add', methods=['POST'])
@super_admin_required
def add_facility():
    fac_id = request.form.get('facility_id', '').strip().upper()
    name = request.form.get('facility_name', '').strip()
    node_id = request.form.get('node_id', '').strip()
    lat = request.form.get('latitude', type=float)
    lon = request.form.get('longitude', type=float)
    capacity = request.form.get('capacity', type=int) or 30
    desc = request.form.get('description', '').strip()

    if not fac_id or not name or lat is None or lon is None:
        flash("Facility ID, Name, Latitude, and Longitude are required.", "danger")
        return redirect(url_for('super_admin.facilities_list'))

    existing = db.session.get(ParkingFacility, fac_id)
    if existing:
        flash(f"Facility with ID {fac_id} already exists.", "danger")
        return redirect(url_for('super_admin.facilities_list'))

    new_fac = ParkingFacility(
        facility_id=fac_id,
        facility_name=name,
        node_id=node_id or f"NODE_{fac_id}",
        latitude=lat,
        longitude=lon,
        capacity=capacity,
        initial_occupied=0,
        description=desc,
        is_active=True
    )
    db.session.add(new_fac)
    db.session.flush()

    # Automatically generate parking slots
    for i in range(1, capacity + 1):
        slot = ParkingSlot(
            slot_id=f"{fac_id}_{i:02d}",
            facility_id=fac_id,
            slot_number=f"{fac_id}-S{i:02d}",
            initial_status='available',
            manual_status='AUTO'
        )
        db.session.add(slot)

    db.session.commit()

    AdminActivityLog.log_action(
        user_id=session['user_id'],
        action_type="FACILITY_ADD",
        description=f"Added new parking facility {name} ({fac_id}) with {capacity} slots.",
        facility_id=fac_id
    )

    flash(f"Facility {name} ({fac_id}) and its {capacity} slots were created successfully.", "success")
    return redirect(url_for('super_admin.facilities_list'))


@super_admin_bp.route('/facility/edit/<facility_id>', methods=['POST'])
@super_admin_required
def edit_facility(facility_id):
    facility = db.session.get(ParkingFacility, facility_id)
    if not facility:
        flash("Facility not found.", "danger")
        return redirect(url_for('super_admin.facilities_list'))

    name = request.form.get('facility_name', '').strip()
    new_capacity = request.form.get('capacity', type=int)
    desc = request.form.get('description', '').strip()

    if name:
        facility.facility_name = name
    if desc:
        facility.description = desc

    # Capacity update with safety checks (does not invalidate active bookings)
    if new_capacity and new_capacity != facility.capacity and new_capacity >= 5:
        old_cap = facility.capacity
        facility.capacity = new_capacity

        # If increasing capacity, auto-create additional slots
        if new_capacity > old_cap:
            for i in range(old_cap + 1, new_capacity + 1):
                slot_id = f"{facility.facility_id}_{i:02d}"
                existing_slot = db.session.get(ParkingSlot, slot_id)
                if not existing_slot:
                    new_slot = ParkingSlot(
                        slot_id=slot_id,
                        facility_id=facility.facility_id,
                        slot_number=f"{facility.facility_id}-S{i:02d}",
                        initial_status='available',
                        manual_status='AUTO'
                    )
                    db.session.add(new_slot)

        AdminActivityLog.log_action(
            user_id=session['user_id'],
            action_type="CAPACITY_UPDATE",
            description=f"Updated capacity of {facility.facility_id} from {old_cap} to {new_capacity}.",
            facility_id=facility.facility_id
        )

    db.session.commit()
    flash(f"Facility {facility.facility_name} updated successfully.", "success")
    return redirect(url_for('super_admin.facilities_list'))


@super_admin_bp.route('/facility/toggle-status/<facility_id>', methods=['POST'])
@super_admin_required
def toggle_facility_status(facility_id):
    facility = db.session.get(ParkingFacility, facility_id)
    if not facility:
        flash("Facility not found.", "danger")
        return redirect(url_for('super_admin.facilities_list'))

    facility.is_active = not facility.is_active
    db.session.commit()

    status_str = "activated" if facility.is_active else "deactivated"
    AdminActivityLog.log_action(
        user_id=session['user_id'],
        action_type="FACILITY_STATUS_TOGGLE",
        description=f"Facility {facility.facility_id} {status_str}.",
        facility_id=facility.facility_id
    )

    flash(f"Facility {facility.facility_name} is now {status_str}.", "info")
    return redirect(url_for('super_admin.facilities_list'))


# =========================================================================
# C. STAFF ACCOUNT MANAGEMENT
# =========================================================================
@super_admin_bp.route('/staff')
@super_admin_required
def staff_management():
    staff_members = User.query.filter_by(role='staff').order_by(User.created_at.desc()).all()
    facilities = ParkingFacility.query.all()

    return render_template(
        'super_admin/staff.html',
        staff_members=staff_members,
        facilities=facilities
    )


@super_admin_bp.route('/staff/create', methods=['POST'])
@super_admin_required
def create_staff():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    facility_id = request.form.get('facility_id', '').strip()
    password = request.form.get('password', '').strip()

    if not name or not email or not password or not facility_id:
        flash("Name, Email, Assigned Facility, and Password are required.", "danger")
        return redirect(url_for('super_admin.staff_management'))

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash("An account with this email address already exists.", "danger")
        return redirect(url_for('super_admin.staff_management'))

    fac = db.session.get(ParkingFacility, facility_id)
    if not fac:
        flash("Invalid facility selected.", "danger")
        return redirect(url_for('super_admin.staff_management'))

    staff = User(
        name=name,
        email=email,
        phone=phone,
        role='staff',
        facility_id=facility_id,
        is_active=True
    )
    staff.set_password(password)
    db.session.add(staff)
    db.session.commit()

    AdminActivityLog.log_action(
        user_id=session['user_id'],
        action_type="STAFF_CREATE",
        description=f"Created staff account {email} assigned to {facility_id}.",
        facility_id=facility_id,
        target_id=str(staff.user_id)
    )

    flash(f"Staff account for {name} ({email}) created and assigned to {fac.facility_name}.", "success")
    return redirect(url_for('super_admin.staff_management'))


@super_admin_bp.route('/staff/edit/<int:staff_id>', methods=['POST'])
@super_admin_required
def edit_staff(staff_id):
    staff = db.session.get(User, staff_id)
    if not staff or staff.role != 'staff':
        flash("Staff account not found.", "danger")
        return redirect(url_for('super_admin.staff_management'))

    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    new_facility_id = request.form.get('facility_id', '').strip()
    new_password = request.form.get('new_password', '').strip()

    if name:
        staff.name = name
    if phone:
        staff.phone = phone
    if new_facility_id:
        old_fac = staff.facility_id
        staff.facility_id = new_facility_id
        if old_fac != new_facility_id:
            AdminActivityLog.log_action(
                user_id=session['user_id'],
                action_type="STAFF_REASSIGN",
                description=f"Reassigned staff {staff.name} from {old_fac} to {new_facility_id}.",
                facility_id=new_facility_id,
                target_id=str(staff.user_id)
            )

    if new_password:
        staff.set_password(new_password)
        flash("Password updated for staff member.", "info")

    db.session.commit()
    flash(f"Staff account {staff.name} updated successfully.", "success")
    return redirect(url_for('super_admin.staff_management'))


@super_admin_bp.route('/staff/toggle-status/<int:staff_id>', methods=['POST'])
@super_admin_required
def toggle_staff_status(staff_id):
    staff = db.session.get(User, staff_id)
    if not staff or staff.role != 'staff':
        flash("Staff account not found.", "danger")
        return redirect(url_for('super_admin.staff_management'))

    staff.is_active = not staff.is_active
    db.session.commit()

    status_str = "activated" if staff.is_active else "deactivated"
    AdminActivityLog.log_action(
        user_id=session['user_id'],
        action_type="STAFF_STATUS_TOGGLE",
        description=f"Staff account {staff.email} {status_str}.",
        facility_id=staff.facility_id,
        target_id=str(staff.user_id)
    )

    flash(f"Staff account {staff.name} is now {status_str}.", "info")
    return redirect(url_for('super_admin.staff_management'))


# =========================================================================
# D. SYSTEM-WIDE BOOKINGS MANAGEMENT
# =========================================================================
@super_admin_bp.route('/bookings')
@super_admin_required
def bookings_management():
    facilities = ParkingFacility.query.all()
    facility_filter = request.args.get('facility', 'ALL')
    status_filter = request.args.get('status', 'ALL')
    search_query = request.args.get('q', '').strip()
    export_csv = request.args.get('export', 'false').lower() == 'true'

    query = Booking.query

    if facility_filter != 'ALL':
        query = query.filter(Booking.facility_id == facility_filter)

    if status_filter != 'ALL':
        query = query.filter(Booking.booking_status == status_filter)

    if search_query:
        query = query.filter(
            (Booking.booking_id.ilike(f'%{search_query}%')) |
            (Booking.vehicle_number.ilike(f'%{search_query}%')) |
            (Booking.user.has(User.name.ilike(f'%{search_query}%')))
        )

    bookings = query.order_by(Booking.created_at.desc()).limit(200).all()

    # CSV Export
    if export_csv:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Booking ID', 'Facility ID', 'Customer Name', 'Phone', 'Vehicle Number', 'Type', 'Slot', 'Arrival', 'Departure', 'Status', 'Walk-in', 'Created At'])
        for b in bookings:
            writer.writerow([
                b.booking_id,
                b.facility_id,
                b.user.name if b.user else 'Guest',
                b.user.phone if b.user else '',
                b.vehicle_number,
                b.vehicle_type,
                b.slot.slot_number if b.slot else '',
                b.arrival_datetime.strftime('%Y-%m-%d %H:%M'),
                b.departure_datetime.strftime('%Y-%m-%d %H:%M'),
                b.booking_status,
                'Yes' if b.is_walkin else 'No',
                b.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=smartpark_all_bookings_report.csv"}
        )

    return render_template(
        'super_admin/bookings.html',
        bookings=bookings,
        facilities=facilities,
        facility_filter=facility_filter,
        status_filter=status_filter,
        search_query=search_query
    )


@super_admin_bp.route('/booking/cancel/<booking_id>', methods=['POST'])
@super_admin_required
def admin_cancel_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for('super_admin.bookings_management'))

    booking.cancel()
    AdminActivityLog.log_action(
        user_id=session['user_id'],
        action_type="BOOKING_CANCEL",
        description=f"Super Admin cancelled booking {booking.booking_id} at {booking.facility_id}.",
        facility_id=booking.facility_id,
        target_id=booking.booking_id
    )

    flash(f"Booking {booking.booking_id} cancelled by Super Administrator.", "success")
    return redirect(request.referrer or url_for('super_admin.bookings_management'))


# =========================================================================
# E. SYSTEM-WIDE OCCUPANCY MONITORING
# =========================================================================
@super_admin_bp.route('/occupancy')
@super_admin_required
def occupancy_monitoring():
    facilities = ParkingFacility.query.all()
    facility_stats = [f.get_dynamic_occupancy() for f in facilities]

    total_capacity = sum(f.capacity for f in facilities)
    total_occupied = sum(s['occupied'] for s in facility_stats)
    total_reserved = sum(s['reserved'] for s in facility_stats)
    total_available = sum(s['available'] for s in facility_stats)

    return render_template(
        'super_admin/occupancy.html',
        facilities=facilities,
        facility_stats=facility_stats,
        total_capacity=total_capacity,
        total_occupied=total_occupied,
        total_reserved=total_reserved,
        total_available=total_available
    )


# =========================================================================
# F. VEHICLE LOGS
# =========================================================================
@super_admin_bp.route('/vehicle-logs')
@super_admin_required
def vehicle_logs():
    facilities = ParkingFacility.query.all()
    facility_filter = request.args.get('facility', 'ALL')
    status_filter = request.args.get('status', 'ALL')
    search_query = request.args.get('q', '').strip()
    export_csv = request.args.get('export', 'false').lower() == 'true'

    query = VehicleLog.query

    if facility_filter != 'ALL':
        query = query.filter(VehicleLog.facility_id == facility_filter)

    if status_filter != 'ALL':
        query = query.filter(VehicleLog.status == status_filter)

    if search_query:
        query = query.filter(VehicleLog.vehicle_number.ilike(f'%{search_query}%'))

    logs = query.order_by(VehicleLog.entry_time.desc()).limit(200).all()

    if export_csv:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Log ID', 'Facility', 'Slot', 'Vehicle Number', 'Type', 'Entry Time', 'Exit Time', 'Status', 'Walk-in'])
        for l in logs:
            writer.writerow([
                l.log_id,
                l.facility_id,
                l.slot.slot_number if l.slot else '',
                l.vehicle_number,
                l.vehicle_type,
                l.entry_time.strftime('%Y-%m-%d %H:%M:%S') if l.entry_time else '',
                l.exit_time.strftime('%Y-%m-%d %H:%M:%S') if l.exit_time else '',
                l.status,
                'Yes' if l.is_walkin else 'No'
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=smartpark_vehicle_movement_logs.csv"}
        )

    return render_template(
        'super_admin/vehicle_logs.html',
        logs=logs,
        facilities=facilities,
        facility_filter=facility_filter,
        status_filter=status_filter,
        search_query=search_query
    )


# =========================================================================
# G. SYSTEM-WIDE REPORTS
# =========================================================================
@super_admin_bp.route('/reports')
@super_admin_required
def reports():
    report_type = request.args.get('type', 'facility_performance')
    export_csv = request.args.get('export', 'false').lower() == 'true'

    facilities = ParkingFacility.query.all()
    facility_stats = [f.get_dynamic_occupancy() for f in facilities]

    if export_csv:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Facility ID', 'Facility Name', 'Capacity', 'Occupied', 'Reserved', 'Maintenance', 'Available', 'Utilization %'])
        for s in facility_stats:
            writer.writerow([
                s['facility_id'],
                s['facility_name'],
                s['capacity'],
                s['occupied'],
                s['reserved'],
                s['maintenance'],
                s['available'],
                f"{s['utilization_pct']}%"
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=smartpark_facility_performance_report.csv"}
        )

    return render_template(
        'super_admin/reports.html',
        facilities=facilities,
        facility_stats=facility_stats,
        report_type=report_type
    )


# =========================================================================
# H. SYSTEM ACTIVITY LOGS
# =========================================================================
@super_admin_bp.route('/activity-logs')
@super_admin_required
def activity_logs():
    facilities = ParkingFacility.query.all()
    facility_filter = request.args.get('facility', 'ALL')
    action_filter = request.args.get('action', 'ALL')

    query = AdminActivityLog.query

    if facility_filter != 'ALL':
        query = query.filter(AdminActivityLog.facility_id == facility_filter)

    if action_filter != 'ALL':
        query = query.filter(AdminActivityLog.action_type == action_filter)

    logs = query.order_by(AdminActivityLog.timestamp.desc()).limit(200).all()

    return render_template(
        'super_admin/activity_logs.html',
        logs=logs,
        facilities=facilities,
        facility_filter=facility_filter,
        action_filter=action_filter
    )


# =========================================================================
# I. SETTINGS & SYSTEM CONFIGURATION
# =========================================================================
@super_admin_bp.route('/settings')
@super_admin_required
def settings():
    return render_template('super_admin/settings.html')

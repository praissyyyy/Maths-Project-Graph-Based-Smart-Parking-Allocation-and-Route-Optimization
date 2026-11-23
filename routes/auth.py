"""
Authentication and Authorization Routes.
Handles user registration, login, logout, and multi-tier Role-Based Access Control (RBAC).
Supports Driver, Parking Lot Staff, and Central Super Admin roles.
"""

from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from models import db
from models.user import User
from models.activity_log import AdminActivityLog

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Parking Staff credentials required.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        role = session.get('user_role')
        if role != 'staff':
            flash("Access denied: Parking Staff portal is restricted to authorized facility staff.", "danger")
            return redirect(url_for('parking.index'))
        if not session.get('facility_id'):
            flash("No assigned facility found for this staff account.", "danger")
            return redirect(url_for('parking.index'))
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Central Super Administrator credentials required.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        role = session.get('user_role')
        if role not in ['super_admin', 'admin']:
            flash("Access denied: Central Super Administrator privileges required.", "danger")
            return redirect(url_for('parking.index'))
        return f(*args, **kwargs)
    return decorated_function


# Backward compatibility alias for existing tests
admin_required = super_admin_required


@auth_bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = db.session.get(User, user_id)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        next_url = request.args.get('next')

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template('login.html', email=email)

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash("Your account has been deactivated. Please contact the Super Administrator.", "danger")
                return render_template('login.html', email=email)

            session.clear()
            session['user_id'] = user.user_id
            session['user_name'] = user.name
            session['user_email'] = user.email
            session['user_role'] = user.role
            session['facility_id'] = user.facility_id

            # Update last login timestamp
            user.last_login = datetime.utcnow()
            db.session.commit()

            # Record login activity for staff and super admin
            if user.role in ['staff', 'super_admin', 'admin']:
                AdminActivityLog.log_action(
                    user_id=user.user_id,
                    action_type="LOGIN",
                    description=f"{user.name} ({user.role}) logged in.",
                    facility_id=user.facility_id
                )

            flash(f"Welcome back, {user.name}!", "success")

            if next_url:
                return redirect(next_url)

            # Role-specific dashboard redirection
            if user.is_super_admin:
                return redirect(url_for('super_admin.dashboard'))
            elif user.is_staff:
                return redirect(url_for('staff.dashboard'))
            else:
                return redirect(url_for('parking.index'))
        else:
            flash("Invalid email or password. Please verify your credentials.", "danger")

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not name or not email or not password:
            flash("Name, email, and password are required.", "danger")
            return render_template('register.html', name=name, email=email, phone=phone)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('register.html', name=name, email=email, phone=phone)

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template('register.html', name=name, email=email, phone=phone)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for('auth.login'))

        new_user = User(name=name, email=email, phone=phone, role='driver', is_active=True)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        session.clear()
        session['user_id'] = new_user.user_id
        session['user_name'] = new_user.name
        session['user_email'] = new_user.email
        session['user_role'] = new_user.role
        session['facility_id'] = None

        flash("Account created successfully! You are now logged in as a driver.", "success")
        return redirect(url_for('parking.index'))

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    user_role = session.get('user_role')
    facility_id = session.get('facility_id')
    user_name = session.get('user_name', 'User')

    if user_id and user_role in ['staff', 'super_admin', 'admin']:
        AdminActivityLog.log_action(
            user_id=user_id,
            action_type="LOGOUT",
            description=f"{user_name} ({user_role}) logged out.",
            facility_id=facility_id
        )

    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for('parking.index'))

"""
Admin Compatibility Blueprint.
Redirects legacy /admin requests to the Central Super Admin Portal.
"""

from flask import Blueprint, redirect, url_for
from routes.auth import super_admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@super_admin_required
def dashboard():
    return redirect(url_for('super_admin.dashboard'))

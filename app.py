"""
SmartPark – Gandhipuram: Main Flask Application.
Combines Graph-Based Optimization and Web Parking Reservation.
"""

import os
import logging
from flask import Flask, render_template
from config import Config
from models import db
from database_setup import init_and_seed_database
from algorithms.graph_loader import load_or_fetch_road_network

# Import blueprints
from routes.auth import auth_bp
from routes.parking import parking_bp
from routes.booking import booking_bp
from routes.map import map_bp
from routes.admin import admin_bp
from routes.staff_admin import staff_bp
from routes.super_admin import super_admin_bp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure instance and data folders exist
    os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)
    os.makedirs(app.config.get('DATA_DIR', 'data'), exist_ok=True)

    # Initialize extensions
    db.init_app(app)

    # Register application blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(parking_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(super_admin_bp)

    # Load directed road graph into application context
    try:
        graphml_path = app.config.get('GRAPHML_PATH')
        _, di_g = load_or_fetch_road_network(filepath=graphml_path)
        app.config['ROAD_GRAPH'] = di_g
        logger.info(f"Loaded road graph into app: {di_g.number_of_nodes()} nodes, {di_g.number_of_edges()} edges.")
    except Exception as e:
        logger.warning(f"Could not initialize road network in app: {e}")
        app.config['ROAD_GRAPH'] = None

    # Seed database with initial facilities, slots, and demo accounts
    init_and_seed_database(app)

    # Custom Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', content="<div class='container py-5 text-center'><h2>404 - Page Not Found</h2><p>The requested page could not be located.</p><a href='/' class='btn btn-primary'>Return Home</a></div>"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('base.html', content="<div class='container py-5 text-center'><h2>500 - Internal Server Error</h2><p>An unexpected error occurred.</p><a href='/' class='btn btn-primary'>Return Home</a></div>"), 500

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"\n========================================================")
    print(f" SmartPark Gandhipuram Server Running Successfully!")
    print(f" Open your browser: http://127.0.0.1:{port}")
    print(f"========================================================\n")
    app.run(host='0.0.0.0', port=port, debug=True)

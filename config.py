# SmartPark - Gandhipuram Configuration
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smartpark-gandhipuram-super-secure-key-2026')
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'smartpark.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Study Area Information
    STUDY_AREA = {
        'name': 'Gandhipuram, Coimbatore, Tamil Nadu, India',
        'latitude': 11.0182714,
        'longitude': 76.9677744,
        'radius_meters': 1400
    }
    
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    RESULTS_DIR = os.path.join(BASE_DIR, 'results')
    GRAPHML_PATH = os.path.join(DATA_DIR, 'gandhipuram_road_network.graphml')

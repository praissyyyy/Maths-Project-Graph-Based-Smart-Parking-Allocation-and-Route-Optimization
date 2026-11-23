import os
import pytest
from app import create_app
from database_setup import init_and_seed_database


@pytest.fixture(scope="session")
def app_instance():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    class TestConfig:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SECRET_KEY = "test-secret-key"
        DATA_DIR = os.path.join(base_dir, "data")
        GRAPHML_PATH = os.path.join(DATA_DIR, "gandhipuram_road_network.graphml")

    app = create_app(TestConfig)
    return app


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()

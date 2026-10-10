"""Shared Flask extensions.

Kept separate from the app factory so blueprints can import them without
circular imports.
"""
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()

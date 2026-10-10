"""Flask application factory (blueprint §15)."""
import os

from flask import Flask, jsonify

from config import Config

from .extensions import db, migrate


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so metadata is registered before create_all/migrate
    from . import models  # noqa: F401

    from .admin.routes import bp as admin_bp
    from .api.routes import bp as api_bp
    from .attendance.routes import bp as attendance_bp
    from .auth.routes import bp as auth_bp
    from .leave.routes import bp as leave_bp
    from .reports.routes import bp as reports_bp
    from .student.routes import bp as student_bp
    from .teacher.routes import bp as teacher_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(api_bp)

    _register_error_handlers(app)
    _register_web_assets(app)

    return app


def _register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "not_found", "message": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"error": "method_not_allowed",
                        "message": "Method not allowed"}), 405

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "message": str(e)}), 400

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return jsonify({"error": "server_error",
                        "message": "Internal server error"}), 500


def _register_web_assets(app):
    """Serve the PC dashboard (§15) and public launch page (§19)."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dashboard_dir = os.path.join(base, "dashboard")
    launch_dir = os.path.join(base, "launch")

    if os.path.isdir(dashboard_dir):
        app.static_folder = dashboard_dir  # /static/* -> dashboard assets

        @app.get("/dashboard")
        def dashboard_index():
            from flask import send_from_directory
            return send_from_directory(dashboard_dir, "index.html")

    if os.path.isdir(launch_dir):
        from flask import send_from_directory

        @app.get("/")
        def launch_index():
            return send_from_directory(launch_dir, "index.html")

        @app.get("/privacy")
        def launch_privacy():
            return send_from_directory(launch_dir, "privacy.html")

        @app.get("/terms")
        def launch_terms():
            return send_from_directory(launch_dir, "terms.html")

"""
app.py  —  MAIN ENTRY POINT (All Members)
==========================================
Creates and configures the Flask application.

The Application Factory Pattern (create_app function) is used here.
WHY? It avoids circular imports and makes the app testable:
  - Routes import `db` from models
  - models import nothing from routes
  - app.py ties everything together

STARTUP SEQUENCE:
  1. Create Flask app
  2. Load config (DB URI, secret key, upload folder)
  3. Initialise SQLAlchemy with the app
  4. Register all Blueprint routes
  5. Create DB tables if they don't exist
  6. Add seed data for demo purposes
  7. Start the server
"""

import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, g, session
from flask_cors import CORS
from models import db
from config import active_config

# ── Import Blueprints ─────────────────────────────────────────────────────────
from routes.auth_routes    import auth_bp
from routes.employee_routes  import employee_bp
from routes.leave_routes     import leave_bp
from routes.chatbot_routes   import chatbot_bp
from routes.analytics_routes import analytics_bp
from routes.report_routes    import report_bp
from routes.nlp_routes       import nlp_bp
from routes.auth_utils       import get_current_user, admin_required

DAILY_QUOTES = [
    {"quote": "Small improvements every day create strong systems.", "author": "SmartHR"},
    {"quote": "People-first design is still the best automation strategy.", "author": "SmartHR"},
    {"quote": "Good software makes the next action obvious.", "author": "SmartHR"},
    {"quote": "Clear workflows reduce friction for everyone.", "author": "SmartHR"},
    {"quote": "A calm interface is part of good engineering.", "author": "SmartHR"},
]


def create_app():
    app = Flask(__name__)

    # Load all settings from config.py
    app.config.from_object(active_config)

    # Enable Cross-Origin Resource Sharing (for frontend JS fetch calls)
    CORS(app)

    # Ensure upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ── Bind SQLAlchemy to this app instance ──────────────────────────────────
    db.init_app(app)

    # ── Register Blueprints ───────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(nlp_bp)

    @app.before_request
    def enforce_authentication():
        g.current_user = get_current_user()

        endpoint = request.endpoint or ""

        if endpoint == "auth.login" and g.current_user is not None:
            return redirect(url_for("dashboard"))

        # Truly public — no session needed at all
        always_public = {"auth.login", "auth.logout", "auth.guest_mode", "static"}
        if endpoint in always_public:
            return None

        # All page routes require at least a guest session
        # API routes have their own whitelist below
        if not request.path.startswith("/api/") and not session.get("role"):
            return redirect(url_for("auth.login"))

        if request.path.startswith("/api/analytics/"):
            return None

        if request.path.startswith("/api/chatbot/"):
            return None

        if request.path.startswith("/api/leaves"):
            return None

        if request.path.startswith("/api/quotes/"):
            return None

        if g.current_user is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login"))

    # ── Page Routes (serve HTML templates) ───────────────────────────────────
    @app.route("/")
    def dashboard():
        if not session.get("role"):
            return redirect(url_for("auth.login"))
        return render_template("dashboard.html")

    @app.route("/employees")
    def employees_page():
        return render_template("employees.html")

    @app.route("/leaves")
    def leaves_page():
        return render_template("leave.html")

    @app.route("/chatbot")
    def chatbot_page():
        return render_template("chatbot.html")

    @app.route("/feedback")
    def feedback_page():
        return render_template("feedback.html")

    @app.route("/payroll")

    def payroll_page():
        return render_template("payroll.html")

    @app.route("/reports")
    def reports_page():
        return render_template("reports.html")


    @app.route("/api/quotes/daily")
    def daily_quote():
        index = datetime.utcnow().timetuple().tm_yday % len(DAILY_QUOTES)
        payload = DAILY_QUOTES[index]
        payload = {
            **payload,
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        return jsonify(payload)

    # ── Create tables if they do not exist ────────────────────────────────────
    with app.app_context():
        # Import all models to register with SQLAlchemy metadata
        from models.employee import Employee
        from models.user import User
        from models.leave import Leave
        from models.feedback import Feedback
        from models.attendance import Attendance
        from models.performance import Performance
        from models.leave_balance import LeaveBalance
        
        db.create_all()

    return app

# Seed logic has been moved to a dedicated seed.py script.


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    print("\n" + "="*50)
    print("  SmartHR — AI-Powered Employee Management")
    print("  Running at: http://127.0.0.1:5000")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)

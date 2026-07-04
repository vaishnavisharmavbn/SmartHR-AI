"""
routes/employee_routes.py  —  MEMBER 1 + MEMBER 3
===================================================
REST API endpoints for Employee CRUD + Resume Upload.

REST CONVENTION used here:
  GET    /api/employees          → list all
  POST   /api/employees          → create new
  GET    /api/employees/<id>     → get one
  PUT    /api/employees/<id>     → update
  DELETE /api/employees/<id>     → soft-delete (set is_active=False)
  POST   /api/employees/parse-resume → NLP resume parsing
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from models import db
from models.employee import Employee
from nlp.resume_parser import resume_parser
from routes.auth_utils import admin_required

# Blueprint = Flask's way to group related routes into a module.
# url_prefix means all routes here start with /api/employees
employee_bp = Blueprint("employees", __name__, url_prefix="/api/employees")


def allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


# ── GET all employees ─────────────────────────────────────────────────────────
@employee_bp.route("", methods=["GET"])

def get_employees():
    """
    Query parameters:
      ?department=Engineering   → filter by dept
      ?active=true              → only active employees
      ?search=john              → name/email search
    """
    query = Employee.query

    dept = request.args.get("department")
    if dept:
        query = query.filter_by(department=dept)

    active = request.args.get("active")
    if active:
        query = query.filter_by(is_active=(active.lower() == "true"))

    search = request.args.get("search")
    if search:
        # SQL LIKE query: % = wildcard
        query = query.filter(
            (Employee.name.ilike(f"%{search}%")) |
            (Employee.email.ilike(f"%{search}%"))
        )

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 15, type=int)

    pagination = query.order_by(Employee.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "employees": [e.to_dict() for e in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev
    })


# ── POST create employee ──────────────────────────────────────────────────────
@employee_bp.route("", methods=["POST"])

def create_employee():
    data = request.get_json()

    # Validation — required fields
    required = ["name", "email", "department", "designation"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"'{field}' is required"}), 400

    # Check duplicate email
    if Employee.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already exists"}), 409

    emp = Employee(
        name        = data["name"],
        email       = data["email"],
        phone       = data.get("phone", ""),
        address     = data.get("address", ""),
        department  = data["department"],
        designation = data["designation"],
        salary      = float(data.get("salary", 0)),
        skills      = data.get("skills", ""),
        join_date   = datetime.strptime(data["join_date"], "%Y-%m-%d").date()
                      if data.get("join_date") else datetime.utcnow().date(),
    )

    db.session.add(emp)
    db.session.commit()
    return jsonify(emp.to_dict()), 201


# ── GET single employee ───────────────────────────────────────────────────────
@employee_bp.route("/<int:emp_id>", methods=["GET"])
def get_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    return jsonify(emp.to_dict())


# ── PUT update employee ───────────────────────────────────────────────────────
@employee_bp.route("/<int:emp_id>", methods=["PUT"])
def update_employee(emp_id):
    emp  = Employee.query.get_or_404(emp_id)
    data = request.get_json()

    # Only update fields that are sent (partial update)
    updatable = ["name", "phone", "address", "department", "designation", "salary", "skills", "is_active"]
    for field in updatable:
        if field in data:
            setattr(emp, field, data[field])

    db.session.commit()
    return jsonify(emp.to_dict())


# ── DELETE employee (soft delete) ─────────────────────────────────────────────
@employee_bp.route("/<int:emp_id>", methods=["DELETE"])

def delete_employee(emp_id):
    """
    SOFT DELETE: We don't remove the row from DB.
    We set is_active=False. This preserves historical data
    (leaves, feedback) for audit trails. A hard DELETE would
    cascade-delete all related records.
    """
    emp = Employee.query.get_or_404(emp_id)
    emp.is_active = False
    db.session.commit()
    return jsonify({"message": f"Employee {emp.name} deactivated."})

# ── POST parse resume (NLP) ───────────────────────────────────────────────────
@employee_bp.route("/parse-resume", methods=["POST"])
def parse_resume():
    """
    MEMBER 3's endpoint.
    Accepts a resume file upload, runs the NLP parser, returns structured data.
    The frontend pre-fills the 'Add Employee' form with the extracted data.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Use PDF, DOCX, or TXT."}), 400

    # Save file temporarily
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    filepath   = os.path.join(upload_dir, file.filename)
    file.save(filepath)

    # Run NLP parser
    result = resume_parser.parse(filepath)

    # Clean up the temp file
    os.remove(filepath)

    return jsonify(result)

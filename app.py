from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename

import os
import re
import sqlite3
import uuid
from datetime import datetime, date, timedelta
from io import BytesIO

import fitz
import pandas as pd
from docx import Document

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from finance_engine import (
    analyze_file,
    ai_transactions_to_dataframe,
    analyze_dataframe,
    categorize,
)

from ai_extractor import (
    extract_from_image,
    extract_from_text,
)

from database import (
    DATABASE,
    create_user,
    get_user_by_id,
    get_user_by_email,
    verify_user_password,
    update_user_profile,
    update_user_password,
    add_transactions as db_add_transactions,
    get_transactions as db_get_transactions,
    add_transaction as db_add_transaction,
    get_transaction as db_get_transaction,
    update_transaction as db_update_transaction,
    delete_transaction as db_delete_transaction,
    get_budgets as db_get_budgets,
    set_budget as db_set_budget,
    delete_budget as db_delete_budget,
    get_goals as db_get_goals,
    add_goal as db_add_goal,
    get_goal as db_get_goal,
    update_goal as db_update_goal,
    delete_goal as db_delete_goal,
)


# ============================================================
# APP CONFIG
# ============================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATA_FOLDER = os.path.join(BASE_DIR, "data")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

PRODUCTION = os.environ.get("FLASK_ENV", "").lower() == "production"
SECRET_KEY = os.environ.get("SECRET_KEY")

if PRODUCTION and not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in production.")

app.config["SECRET_KEY"] = SECRET_KEY or "finpilot-dev-secret-change-me"

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SESSION_COOKIE_SECURE"] = (
    PRODUCTION
    or
    os.environ.get(
        "SESSION_COOKIE_SECURE",
        ""
    ).lower() == "true"
)

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

app.config["MAX_CONTENT_LENGTH"] = (
    16 * 1024 * 1024
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


ALLOWED_EXTENSIONS = {
    "csv",
    "xlsx",
    "xls",
    "pdf",
    "docx",
    "png",
    "jpg",
    "jpeg",
}


PUBLIC_PATHS = {
    "/",
    "/login",
    "/signup",
    "/logout",
    "/api/health",
}


# ============================================================
# AUTH / USER SCOPING
# ============================================================

def get_user_count():

    conn = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    try:

        row = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()

        return int(
            row[0] or 0
        )

    finally:

        conn.close()


def current_user_id():

    return session.get(
        "user_id"
    )


def current_user():

    user_id = current_user_id()

    if not user_id:
        return None

    return get_user_by_id(
        user_id
    )


def claim_legacy_data(
    user_id
):

    conn = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    try:

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE transactions
            SET user_id = ?
            WHERE user_id IS NULL
            """,
            (
                user_id,
            )
        )

        cur.execute(
            """
            UPDATE budgets
            SET user_id = ?
            WHERE user_id IS NULL
            """,
            (
                user_id,
            )
        )

        cur.execute(
            """
            UPDATE goals
            SET user_id = ?
            WHERE user_id IS NULL
            """,
            (
                user_id,
            )
        )

        conn.commit()

    finally:

        conn.close()


# ============================================================
# USER-SCOPED DATABASE WRAPPERS
# ============================================================

def get_transactions(
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_get_transactions(
        *args,
        **kwargs
    )


def get_transaction(
    transaction_id,
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_get_transaction(
        transaction_id,
        *args,
        **kwargs
    )


def add_transaction(
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_add_transaction(
        *args,
        **kwargs
    )


def add_transactions(
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_add_transactions(
        *args,
        **kwargs
    )


def update_transaction(
    transaction_id,
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_update_transaction(
        transaction_id,
        *args,
        **kwargs
    )


def delete_transaction(
    transaction_id,
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_delete_transaction(
        transaction_id,
        *args,
        **kwargs
    )


def get_budgets(
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_get_budgets(
        *args,
        **kwargs
    )


def set_budget(
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_set_budget(
        *args,
        **kwargs
    )


def delete_budget(
    budget_id,
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_delete_budget(
        budget_id,
        *args,
        **kwargs
    )


def get_goals(
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_get_goals(
        *args,
        **kwargs
    )


def add_goal(
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_add_goal(
        *args,
        **kwargs
    )


def get_goal(
    goal_id,
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_get_goal(
        goal_id,
        *args,
        **kwargs
    )


def update_goal(
    goal_id,
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_update_goal(
        goal_id,
        *args,
        **kwargs
    )


def delete_goal(
    goal_id,
    *args,
    **kwargs
):

    kwargs.setdefault(
        "user_id",
        current_user_id()
    )

    return db_delete_goal(
        goal_id,
        *args,
        **kwargs
    )


# ============================================================
# AUTHENTICATION GUARD
# ============================================================

@app.before_request
def authentication_guard():

    path = request.path

    if (
        path.startswith("/static/")
        or
        path in PUBLIC_PATHS
    ):

        return None

    if current_user_id():

        if current_user():

            return None

        session.clear()

    if (
        path.startswith("/api/")
        or
        path.startswith("/agent/")
    ):

        return jsonify({

            "success":
                False,

            "error":
                "Authentication required.",

            "redirect":
                "/login"

        }), 401

    return redirect(
        url_for("login")
    )


# ============================================================
# AUTH ROUTES
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "GET":

        if current_user_id():

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html"
        )

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            request.form.to_dict()
        )

        email = str(
            data.get(
                "email",
                ""
            )
        ).strip().lower()

        password = str(
            data.get(
                "password",
                ""
            )
        )

        if not email or not password:

            return jsonify({

                "success":
                    False,

                "error":
                    "Email and password are required."

            }), 400

        user = verify_user_password(
            email,
            password
        )

        if not user:

            return jsonify({

                "success":
                    False,

                "error":
                    "Invalid email or password."

            }), 401

        session.clear()

        session.permanent = True

        session["user_id"] = (
            user["id"]
        )

        session["user_name"] = (
            user["name"]
        )

        session["user_email"] = (
            user["email"]
        )

        return jsonify({

            "success":
                True,

            "message":
                "Login successful.",

            "user": {

                "id":
                    user["id"],

                "name":
                    user["name"],

                "email":
                    user["email"]

            },

            "redirect":
                "/dashboard"

        })

    except Exception as exc:

        print(
            "LOGIN ERROR:",
            repr(exc)
        )

        return jsonify({

            "success":
                False,

            "error":
                "Login failed."

        }), 500


# ============================================================

@app.route(
    "/signup",
    methods=["GET", "POST"]
)
def signup():

    if request.method == "GET":

        if current_user_id():

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "signup.html"
        )

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            request.form.to_dict()
        )

        name = str(
            data.get(
                "name",
                ""
            )
        ).strip()

        email = str(
            data.get(
                "email",
                ""
            )
        ).strip().lower()

        password = str(
            data.get(
                "password",
                ""
            )
        )

        confirm_password = str(

            data.get(

                "confirm_password",

                data.get(
                    "confirmPassword",
                    ""
                )

            )

        )

        if (
            not name
            or
            not email
            or
            not password
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Name, email and password are required."

            }), 400

        if len(password) < 6:

            return jsonify({

                "success":
                    False,

                "error":
                    "Password must contain at least 6 characters."

            }), 400

        if (
            confirm_password
            and
            password != confirm_password
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Passwords do not match."

            }), 400

        if get_user_by_email(email):

            return jsonify({

                "success":
                    False,

                "error":
                    "An account with this email already exists."

            }), 409

        user_id = create_user(

            name=name,

            email=email,

            password=password

        )

        if not user_id:

            return jsonify({

                "success":
                    False,

                "error":
                    "Could not create the account."

            }), 400

        if get_user_count() == 1:

            claim_legacy_data(
                user_id
            )

        session.clear()

        session.permanent = True

        session["user_id"] = (
            user_id
        )

        session["user_name"] = (
            name
        )

        session["user_email"] = (
            email
        )

        return jsonify({

            "success":
                True,

            "message":
                "Account created successfully.",

            "user": {

                "id":
                    user_id,

                "name":
                    name,

                "email":
                    email

            },

            "redirect":
                "/dashboard"

        })

    except Exception as exc:

        print(
            "SIGNUP ERROR:",
            repr(exc)
        )

        return jsonify({

            "success":
                False,

            "error":
                "Could not create the account."

        }), 500


# ============================================================

@app.route(
    "/logout",
    methods=["GET", "POST"]
)
def logout():

    session.clear()

    if request.is_json:

        return jsonify({

            "success":
                True,

            "redirect":
                "/login"

        })

    return redirect(
        url_for("login")
    )


# ============================================================

@app.route(
    "/profile",
    methods=["GET"]
)
def profile_page():

    return render_template(

        "profile.html",

        user=current_user()

    )


# ============================================================

@app.route(
    "/api/profile",
    methods=["GET", "PUT"]
)
def profile_api():

    try:

        user_id = current_user_id()

        user = get_user_by_id(
            user_id
        )

        if not user:

            return jsonify({

                "success":
                    False,

                "error":
                    "User not found."

            }), 404

        if request.method == "GET":

            return jsonify({

                "success":
                    True,

                "user":
                    user

            })

        data = request.get_json(
            silent=True
        ) or {}

        if not update_user_profile(

            user_id,

            name=data.get("name"),

            email=data.get("email")

        ):

            return jsonify({

                "success":
                    False,

                "error":
                    (
                        "Could not update profile. "
                        "Email may already be in use."
                    )

            }), 400

        updated = get_user_by_id(
            user_id
        )

        session["user_name"] = (
            updated["name"]
        )

        session["user_email"] = (
            updated["email"]
        )

        return jsonify({

            "success":
                True,

            "message":
                "Profile updated successfully.",

            "user":
                updated

        })

    except Exception as exc:

        print(
            "PROFILE ERROR:",
            repr(exc)
        )

        return jsonify({

            "success":
                False,

            "error":
                "Profile update failed."

        }), 500


# ============================================================

@app.route(
    "/api/profile/password",
    methods=["PUT"]
)
def change_password():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        current_password = str(
            data.get(
                "current_password",
                ""
            )
        )

        new_password = str(
            data.get(
                "new_password",
                ""
            )
        )

        if (
            not current_password
            or
            not new_password
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    (
                        "Current and new password "
                        "are required."
                    )

            }), 400

        if len(new_password) < 6:

            return jsonify({

                "success":
                    False,

                "error":
                    (
                        "New password must contain "
                        "at least 6 characters."
                    )

            }), 400

        user = current_user()

        if not user:

            return jsonify({

                "success":
                    False,

                "error":
                    "User not found."

            }), 404

        if not verify_user_password(

            user["email"],

            current_password

        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Current password is incorrect."

            }), 401

        if not update_user_password(

            user["id"],

            new_password

        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Could not update password."

            }), 400

        return jsonify({

            "success":
                True,

            "message":
                "Password changed successfully."

        })

    except Exception as exc:

        print(
            "PASSWORD CHANGE ERROR:",
            repr(exc)
        )

        return jsonify({

            "success":
                False,

            "error":
                "Password change failed."

        }), 500


# ============================================================
# HELPERS
# ============================================================

def allowed_file(
    filename
):

    return (

        "."
        in
        filename

        and

        filename.rsplit(
            ".",
            1
        )[1].lower()
        in
        ALLOWED_EXTENSIONS

    )


def clean_amount(
    value
):

    if value is None:

        return 0.0

    try:

        cleaned = (

            str(value)

            .replace(
                "₹",
                ""
            )

            .replace(
                "Rs.",
                ""
            )

            .replace(
                "Rs",
                ""
            )

            .replace(
                "INR",
                ""
            )

            .replace(
                ",",
                ""
            )

            .strip()

        )

        return float(
            cleaned
        )

    except Exception:

        return 0.0


def transaction_amount(
    transaction
):

    try:

        return float(
            transaction.get(
                "amount",
                0
            )
            or
            0
        )

    except Exception:

        return 0.0


def get_transaction_type(
    transaction
):

    return str(

        transaction.get(

            "transaction_type",

            transaction.get(
                "type",
                ""
            )

        )

        or
        ""

    ).lower()


def is_income(
    transaction
):

    tx_type = get_transaction_type(
        transaction
    )

    amount = transaction_amount(
        transaction
    )

    return (

        tx_type == "income"

        or

        amount > 0

    )


def is_expense(
    transaction
):

    return not is_income(
        transaction
    )


def parse_date_from_text(
    text
):

    text = str(
        text
    ).lower()

    today = date.today()

    if "today" in text:

        return today.isoformat()

    if "yesterday" in text:

        return (

            today
            -
            timedelta(
                days=1
            )

        ).isoformat()

    patterns = [

        (
            r"\b\d{4}-\d{2}-\d{2}\b",
            "%Y-%m-%d"
        ),

        (
            r"\b\d{2}/\d{2}/\d{4}\b",
            "%d/%m/%Y"
        ),

        (
            r"\b\d{2}-\d{2}-\d{4}\b",
            "%d-%m-%Y"
        ),

    ]

    for pattern, fmt in patterns:

        match = re.search(
            pattern,
            text
        )

        if not match:

            continue

        try:

            parsed = datetime.strptime(

                match.group(0),

                fmt

            )

            return parsed.date().isoformat()

        except ValueError:

            pass

    return today.isoformat()


def extract_pdf_text(
    filepath
):

    document = fitz.open(
        filepath
    )

    try:

        return "\n".join(

            page.get_text()

            for page
            in document

        )

    finally:

        document.close()


def extract_docx_text(
    filepath
):

    document = Document(
        filepath
    )

    return "\n".join(

        paragraph.text

        for paragraph
        in document.paragraphs

        if paragraph.text.strip()

    )


def transaction_dataframe(
    transactions
):

    rows = []

    for transaction in transactions:

        amount = transaction_amount(
            transaction
        )

        rows.append({

            "Date":
                transaction.get(
                    "date",
                    ""
                ),

            "Description":
                transaction.get(
                    "description",
                    ""
                ),

            "Amount":

                (
                    -abs(amount)

                    if is_expense(
                        transaction
                    )

                    else

                    abs(amount)
                ),

            "Category":
                transaction.get(
                    "category",
                    "Other"
                ),

        })

    return pd.DataFrame(
        rows
    )


def analyze_transactions(
    transactions
):

    if not transactions:

        return {

            "income":
                0,

            "expenses":
                0,

            "savings":
                0,

            "savings_rate":
                0,

            "transaction_count":
                0,

            "category_spending":
                {},

            "recurring":
                [],

            "unusual":
                [],

            "monthly_spending":
                {},

            "transactions":
                [],

        }

    result = analyze_dataframe(

        transaction_dataframe(
            transactions
        )

    ) or {}

    result["transactions"] = (
        transactions
    )

    result["transaction_count"] = (
        len(transactions)
    )

    result["income"] = float(

        result.get(
            "income",
            0
        )
        or
        0

    )

    result["expenses"] = float(

        result.get(
            "expenses",
            0
        )
        or
        0

    )

    result["savings"] = float(

        result.get(
            "savings",
            0
        )
        or
        0

    )

    result["savings_rate"] = float(

        result.get(
            "savings_rate",
            0
        )
        or
        0

    )

    result["category_spending"] = (

        result.get(
            "category_spending",
            {}
        )

        or

        {}

    )

    result["recurring"] = (

        result.get(
            "recurring",
            []
        )

        or

        []

    )

    result["unusual"] = (

        result.get(
            "unusual",
            []
        )

        or

        []

    )

    result["monthly_spending"] = (

        result.get(
            "monthly_spending",
            {}
        )

        or

        {}

    )

    return result


def normalize_records(
    rows,
    source="upload"
):

    records = []

    for row in rows or []:

        amount = clean_amount(

            row.get(

                "Amount",

                row.get(
                    "amount",
                    0
                )

            )

        )

        description = str(

            row.get(

                "Description",

                row.get(
                    "description",
                    ""
                )

            )

        ).strip()

        if not description:

            continue

        records.append({

            "date":

                str(

                    row.get(

                        "Date",

                        row.get(

                            "date",

                            date.today().isoformat()

                        )

                    )

                ),

            "description":
                description,

            "amount":
                abs(amount),

            "category":

                (
                    row.get(
                        "Category",
                        row.get(
                            "category",
                            "Other"
                        )
                    )

                    or

                    "Other"
                ),

            "type":

                (
                    "income"

                    if amount > 0

                    else

                    "expense"
                ),

            "source":

                row.get(
                    "source",
                    source
                ),

        })

    return records


# ============================================================
# PAGE ROUTES
# ============================================================

@app.route("/")
def index():

    if current_user_id():

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "index.html"
    )


@app.route("/dashboard")
def dashboard():

    return render_template(
        "dashboard.html"
    )


@app.route("/transactions")
def transactions_page():

    return render_template(
        "transactions.html"
    )


@app.route("/budgets")
def budgets_page():

    return render_template(
        "budgets.html"
    )


@app.route("/dashboard/budgets")
def dashboard_budgets_page():

    return render_template(
        "budgets.html"
    )


@app.route("/goals")
def goals_page():

    return render_template(
        "goals.html"
    )


@app.route("/dashboard/goals")
def dashboard_goals_page():

    return render_template(
        "goals.html"
    )


@app.route("/monthly-report")
def monthly_report_page():

    return render_template(
        "monthly_report.html"
    )


# ============================================================
# UPLOAD
# ============================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload_file():

    try:

        if "file" not in request.files:

            return jsonify({

                "success":
                    False,

                "error":
                    "No file uploaded."

            }), 400

        file = request.files[
            "file"
        ]

        if (
            not file
            or
            not file.filename
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "No file selected."

            }), 400

        if not allowed_file(
            file.filename
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Unsupported file format."

            }), 400

        original_name = secure_filename(
            file.filename
        )

        if not original_name:

            return jsonify({

                "success":
                    False,

                "error":
                    "Invalid file name."

            }), 400

        filename = (

            uuid.uuid4().hex[:10]
            +
            "_"
            +
            original_name

        )

        filepath = os.path.join(

            app.config[
                "UPLOAD_FOLDER"
            ],

            filename

        )

        file.save(
            filepath
        )

        extension = (

            filename.rsplit(
                ".",
                1
            )[1]
            .lower()

        )

        analysis = None

        extracted_transactions = []

        storage_rows = []


        # ----------------------------------------------------
        # CSV / EXCEL
        # ----------------------------------------------------

        if extension in {
            "csv",
            "xlsx",
            "xls"
        }:

            analysis = (
                analyze_file(
                    filepath
                )
                or
                {}
            )

            extracted_transactions = (

                analysis.get(
                    "transactions",
                    []
                )

            )

            storage_rows = (
                extracted_transactions
            )


        # ----------------------------------------------------
        # PDF
        # ----------------------------------------------------

        elif extension == "pdf":

            text = extract_pdf_text(
                filepath
            )

            extracted = (
                extract_from_text(
                    text
                )
                or
                {}
            )

            extracted_transactions = (

                extracted.get(
                    "transactions",
                    []
                )

            )

            if extracted_transactions:

                dataframe = (
                    ai_transactions_to_dataframe(
                        extracted_transactions
                    )
                )

                storage_rows = dataframe.to_dict(
                    orient="records"
                )

                if storage_rows:

                    analysis = (
                        analyze_dataframe(
                            dataframe
                        )
                        or
                        {}
                    )


        # ----------------------------------------------------
        # DOCX
        # ----------------------------------------------------

        elif extension == "docx":

            text = extract_docx_text(
                filepath
            )

            extracted = (
                extract_from_text(
                    text
                )
                or
                {}
            )

            extracted_transactions = (

                extracted.get(
                    "transactions",
                    []
                )

            )

            if extracted_transactions:

                dataframe = (
                    ai_transactions_to_dataframe(
                        extracted_transactions
                    )
                )

                storage_rows = dataframe.to_dict(
                    orient="records"
                )

                if storage_rows:

                    analysis = (
                        analyze_dataframe(
                            dataframe
                        )
                        or
                        {}
                    )


        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

        else:

            extracted = (
                extract_from_image(
                    filepath
                )
                or
                {}
            )

            extracted_transactions = (

                extracted.get(
                    "transactions",
                    []
                )

            )

            if extracted_transactions:

                dataframe = (
                    ai_transactions_to_dataframe(
                        extracted_transactions
                    )
                )

                storage_rows = dataframe.to_dict(
                    orient="records"
                )

                if storage_rows:

                    analysis = (
                        analyze_dataframe(
                            dataframe
                        )
                        or
                        {}
                    )


        # ----------------------------------------------------
        # NORMALIZE
        # ----------------------------------------------------

        records = normalize_records(

            storage_rows,

            source="upload"

        )


        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        if records:

            save_result = add_transactions(
                records
            )

        else:

            save_result = {

                "added":
                    0,

                "skipped":
                    0

            }


        if not isinstance(
            save_result,
            dict
        ):

            save_result = {

                "added":
                    0,

                "skipped":
                    0

            }


        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        if analysis is None:

            analysis = analyze_transactions(
                []
            )


        analysis["transactions"] = (
            extracted_transactions
        )

        analysis["transaction_count"] = (
            len(records)
        )


        return jsonify({

            "success":
                True,

            "message":

                (
                    "Successfully analyzed "
                    f"{len(extracted_transactions)} "
                    "transaction(s)."
                ),

            "filename":
                original_name,

            "added":
                int(
                    save_result.get(
                        "added",
                        0
                    )
                ),

            "skipped":
                int(
                    save_result.get(
                        "skipped",
                        0
                    )
                ),

            "analysis":
                analysis,

        })


    except Exception as exc:

        print(
            "UPLOAD ERROR:",
            repr(exc)
        )

        return jsonify({

            "success":
                False,

            "error":
                str(exc)

        }), 500


# ============================================================
# DASHBOARD API
# ============================================================

@app.route(
    "/api/dashboard",
    methods=["GET"]
)
def dashboard_api():

    try:

        transactions = get_transactions()

        analysis = analyze_transactions(
            transactions
        )

        income = (
            analysis["income"]
        )

        expenses = (
            analysis["expenses"]
        )

        savings = (
            analysis["savings"]
        )

        insights = []


        if income > 0:

            rate = (
                savings /
                income
            ) * 100

            if rate >= 30:

                insights.append(
                    "Your recorded savings rate is above 30% this month."
                )

            elif rate >= 15:

                insights.append(
                    "You maintained a positive savings rate."
                )

            else:

                insights.append(
                    "Your savings rate is relatively low."
                )


        if expenses > 0:

            insights.append(

                f"You have recorded "
                f"₹{expenses:,.0f} "
                f"in expenses."

            )


        if savings > 0:

            insights.append(

                f"Your recorded savings are "
                f"₹{savings:,.0f}."

            )

        elif (
            income > 0
            and
            savings < 0
        ):

            insights.append(
                "Your recorded expenses are higher than your income."
            )


        categories = (

            analysis.get(
                "category_spending",
                {}
            )

            or

            {}

        )


        if categories:

            highest_category = max(

                categories,

                key=categories.get

            )

            insights.append(

                (
                    f"{highest_category} is your highest "
                    f"spending category at "
                    f"₹{categories[highest_category]:,.0f}."
                )

            )


        analysis["insights"] = (
            insights
        )


        return jsonify(
            analysis
        )


    except Exception as exc:

        print(
            "DASHBOARD ERROR:",
            repr(exc)
        )

        return jsonify({

            "success":
                False,

            "error":
                str(exc)

        }), 500


# ============================================================
# TRANSACTIONS API
# ============================================================

@app.route(
    "/api/transactions",
    methods=["GET"]
)
def transactions_api():

    try:

        return jsonify({

            "transactions":
                get_transactions()

        })

    except Exception as exc:

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/transactions",
    methods=["POST"]
)
def create_transaction():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )

        description = str(

            data.get(
                "description",
                ""
            )

        ).strip()

        amount = clean_amount(

            data.get(
                "amount",
                0
            )

        )

        tx_type = str(

            data.get(

                "transaction_type",

                data.get(
                    "type",
                    "expense"
                )

            )

        ).lower()


        if not description:

            return jsonify({

                "error":
                    "Description is required."

            }), 400


        if amount <= 0:

            return jsonify({

                "error":
                    "Amount must be greater than zero."

            }), 400


        if tx_type not in {
            "income",
            "expense"
        }:

            tx_type = "expense"


        tx_date = (

            data.get(
                "date"
            )

            or

            date.today().isoformat()

        )


        category = (

            data.get(
                "category"
            )

            or

            categorize(
                description
            )

        )


        tx_id = add_transaction(

            date=tx_date,

            description=description,

            amount=amount,

            category=category,

            transaction_type=tx_type,

            source=data.get(
                "source",
                "manual"
            )

        )


        return jsonify({

            "success":
                True,

            "message":
                "Transaction added successfully.",

            "id":
                tx_id

        })


    except Exception as exc:

        print(
            "CREATE TRANSACTION ERROR:",
            repr(exc)
        )

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["GET"]
)
def get_single_transaction(
    transaction_id
):

    try:

        transaction = get_transaction(
            transaction_id
        )


        if not transaction:

            return jsonify({

                "error":
                    "Transaction not found."

            }), 404


        return jsonify({

            "transaction":
                transaction

        })


    except Exception as exc:

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["PUT"]
)
def edit_transaction(
    transaction_id
):

    try:

        existing = get_transaction(
            transaction_id
        )


        if not existing:

            return jsonify({

                "error":
                    "Transaction not found."

            }), 404


        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )


        tx_date = data.get(

            "date",

            existing.get(
                "date"
            )

        )


        description = str(

            data.get(

                "description",

                existing.get(
                    "description",
                    ""
                )

            )

        ).strip()


        amount = clean_amount(

            data.get(

                "amount",

                existing.get(
                    "amount",
                    0
                )

            )

        )


        category = data.get(

            "category",

            existing.get(
                "category",
                "Other"
            )

        )


        tx_type = str(

            data.get(

                "transaction_type",

                data.get(

                    "type",

                    existing.get(
                        "type",
                        "expense"
                    )

                )

            )

        ).lower()


        if not description:

            return jsonify({

                "error":
                    "Description is required."

            }), 400


        if amount <= 0:

            return jsonify({

                "error":
                    "Amount must be greater than zero."

            }), 400


        if tx_type not in {
            "income",
            "expense"
        }:

            tx_type = "expense"


        update_transaction(

            transaction_id,

            date=tx_date,

            description=description,

            amount=amount,

            category=category,

            transaction_type=tx_type

        )


        return jsonify({

            "success":
                True,

            "message":
                "Transaction updated successfully.",

            "transaction":
                get_transaction(
                    transaction_id
                )

        })


    except Exception as exc:

        print(
            "UPDATE TRANSACTION ERROR:",
            repr(exc)
        )

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["DELETE"]
)
def remove_transaction(
    transaction_id
):

    try:

        if not get_transaction(
            transaction_id
        ):

            return jsonify({

                "error":
                    "Transaction not found."

            }), 404


        delete_transaction(
            transaction_id
        )


        return jsonify({

            "success":
                True,

            "message":
                "Transaction deleted successfully."

        })


    except Exception as exc:

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================
# BUDGET API
# ============================================================

@app.route(
    "/api/budgets",
    methods=["GET"]
)
def budgets_api():

    try:

        return jsonify({

            "budgets":
                get_budgets()

        })


    except Exception as exc:

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/budgets",
    methods=["POST"]
)
def create_budget():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )

        category = str(

            data.get(
                "category",
                ""
            )

        ).strip()


        amount = clean_amount(

            data.get(
                "amount",
                0
            )

        )


        month = str(

            data.get(
                "month"
            )

            or

            date.today().strftime(
                "%Y-%m"
            )

        )


        if not category:

            return jsonify({

                "error":
                    "Category is required."

            }), 400


        if amount <= 0:

            return jsonify({

                "error":
                    "Budget amount must be greater than zero."

            }), 400


        if not re.fullmatch(
            r"\d{4}-\d{2}",
            month
        ):

            return jsonify({

                "error":
                    "Month must be in YYYY-MM format."

            }), 400


        budget_id = set_budget(

            category=category,

            amount=amount,

            month=month

        )


        return jsonify({

            "success":
                True,

            "message":
                "Budget saved successfully.",

            "id":
                budget_id

        })


    except Exception as exc:

        print(
            "BUDGET ERROR:",
            repr(exc)
        )

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/budgets/<int:budget_id>",
    methods=["DELETE"]
)
def remove_budget(
    budget_id
):

    try:

        exists = any(

            int(
                budget.get(
                    "id",
                    -1
                )
            )

            ==
            budget_id

            for budget
            in get_budgets()

        )


        if not exists:

            return jsonify({

                "error":
                    "Budget not found."

            }), 404


        delete_budget(
            budget_id
        )


        return jsonify({

            "success":
                True,

            "message":
                "Budget deleted successfully."

        })


    except Exception as exc:

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================
# BUDGET ANALYSIS
# ============================================================

@app.route(
    "/api/budget-analysis",
    methods=["GET"]
)
def budget_analysis():

    try:

        budgets = get_budgets()

        transactions = get_transactions()

        actuals = {}


        for tx in transactions:

            if not is_expense(
                tx
            ):

                continue


            category = str(

                tx.get(
                    "category",
                    "Other"
                )

            )


            actuals[category] = (

                actuals.get(
                    category,
                    0
                )

                +

                abs(
                    transaction_amount(
                        tx
                    )
                )

            )


        results = []


        for budget
        in budgets:

            category = str(

                budget.get(
                    "category",
                    "Other"
                )

            )


            budget_amount = float(

                budget.get(
                    "amount",
                    0
                )

                or

                0

            )


            actual = float(

                actuals.get(
                    category,
                    0
                )

                or

                0

            )


            used = (

                actual /
                budget_amount *
                100

                if budget_amount > 0

                else

                0

            )


            if used >= 100:

                status = "over"

            elif used >= 80:

                status = "warning"

            else:

                status = "healthy"


            results.append({

                "id":
                    budget.get(
                        "id"
                    ),

                "category":
                    category,

                "budget":
                    round(
                        budget_amount,
                        2
                    ),

                "actual":
                    round(
                        actual,
                        2
                    ),

                "remaining":
                    round(
                        budget_amount -
                        actual,
                        2
                    ),

                "used_percent":
                    round(
                        used,
                        1
                    ),

                "status":
                    status

            })


        return jsonify({

            "budgets":
                results

        })


    except Exception as exc:

        print(
            "BUDGET ANALYSIS ERROR:",
            repr(exc)
        )

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================
# GOAL API
# ============================================================

@app.route(
    "/api/goals",
    methods=["GET"]
)
def goals_api():

    try:

        return jsonify({

            "goals":
                get_goals()

        })

    except Exception as exc:

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/goals",
    methods=["POST"]
)
def create_goal():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )


        name = str(

            data.get(
                "name",
                ""
            )

        ).strip()


        target = clean_amount(

            data.get(
                "target_amount",
                0
            )

        )


        current = clean_amount(

            data.get(
                "current_amount",
                0
            )

        )


        deadline = data.get(
            "deadline"
        )


        if not name:

            return jsonify({

                "error":
                    "Goal name is required."

            }), 400


        if target <= 0:

            return jsonify({

                "error":
                    "Target amount must be greater than zero."

            }), 400


        if (
            current < 0
            or
            current > target
        ):

            return jsonify({

                "error":
                    (
                        "Saved amount must be "
                        "between 0 and the target."
                    )

            }), 400


        goal_id = add_goal(

            name=name,

            target_amount=target,

            current_amount=current,

            deadline=deadline

        )


        return jsonify({

            "success":
                True,

            "message":
                "Goal created successfully.",

            "id":
                goal_id

        })


    except Exception as exc:

        print(
            "CREATE GOAL ERROR:",
            repr(exc)
        )

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/goals/<int:goal_id>",
    methods=["GET"]
)
def get_single_goal(
    goal_id
):

    try:

        goal = get_goal(
            goal_id
        )


        if not goal:

            return jsonify({

                "error":
                    "Goal not found."

            }), 404


        return jsonify({

            "goal":
                goal

        })


    except Exception as exc:

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/goals/<int:goal_id>",
    methods=["PUT"]
)
def edit_goal(
    goal_id
):

    try:

        existing = get_goal(
            goal_id
        )


        if not existing:

            return jsonify({

                "error":
                    "Goal not found."

            }), 404


        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )


        name = str(

            data.get(

                "name",

                existing.get(
                    "name",
                    ""
                )

            )

        ).strip()


        target = clean_amount(

            data.get(

                "target_amount",

                existing.get(
                    "target_amount",
                    0
                )

            )

        )


        current = clean_amount(

            data.get(

                "current_amount",

                existing.get(
                    "current_amount",
                    0
                )

            )

        )


        deadline = data.get(

            "deadline",

            existing.get(
                "deadline"
            )

        )


        if not name:

            return jsonify({

                "error":
                    "Goal name is required."

            }), 400


        if target <= 0:

            return jsonify({

                "error":
                    "Target amount must be greater than zero."

            }), 400


        if (
            current < 0
            or
            current > target
        ):

            return jsonify({

                "error":
                    (
                        "Saved amount must be "
                        "between 0 and the target."
                    )

            }), 400


        update_goal(

            goal_id,

            name=name,

            target_amount=target,

            current_amount=current,

            deadline=deadline

        )


        return jsonify({

            "success":
                True,

            "message":
                "Goal updated successfully.",

            "goal":
                get_goal(
                    goal_id
                )

        })


    except Exception as exc:

        print(
            "UPDATE GOAL ERROR:",
            repr(exc)
        )

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================

@app.route(
    "/api/goals/<int:goal_id>",
    methods=["DELETE"]
)
def remove_goal(
    goal_id
):

    try:

        if not get_goal(
            goal_id
        ):

            return jsonify({

                "error":
                    "Goal not found."

            }), 404


        delete_goal(
            goal_id
        )


        return jsonify({

            "success":
                True,

            "message":
                "Goal deleted successfully."

        })


    except Exception as exc:

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================
# GOAL IMPACT
# ============================================================

@app.route(
    "/api/goal-impact",
    methods=["GET"]
)
def goal_impact():

    try:

        goals = get_goals()

        transactions = get_transactions()


        income = sum(

            abs(
                transaction_amount(
                    tx
                )
            )

            for tx
            in transactions

            if is_income(
                tx
            )

        )


        expenses = sum(

            abs(
                transaction_amount(
                    tx
                )
            )

            for tx
            in transactions

            if is_expense(
                tx
            )

        )


        monthly_savings = max(

            income -
            expenses,

            0

        )


        results = []


        for goal
        in goals:

            target = float(

                goal.get(
                    "target_amount",
                    0
                )

                or

                0

            )


            current = float(

                goal.get(
                    "current_amount",
                    0
                )

                or

                0

            )


            remaining = max(

                target -
                current,

                0

            )


            progress = (

                min(

                    current /
                    target *
                    100,

                    100

                )

                if target > 0

                else

                0

            )


            months_needed = (

                remaining /
                monthly_savings

                if (

                    remaining > 0

                    and

                    monthly_savings > 0

                )

                else

                None

            )


            results.append({

                "id":
                    goal.get(
                        "id"
                    ),

                "name":
                    goal.get(
                        "name",
                        "Financial Goal"
                    ),

                "target_amount":
                    target,

                "current_amount":
                    current,

                "remaining_amount":
                    remaining,

                "progress":
                    round(
                        progress,
                        1
                    ),

                "monthly_savings":
                    round(
                        monthly_savings,
                        2
                    ),

                "months_needed":

                    (

                        round(
                            months_needed,
                            1
                        )

                        if months_needed
                        is not None

                        else

                        None

                    ),

                "deadline":
                    goal.get(
                        "deadline"
                    )

            })


        return jsonify({

            "goals":
                results,

            "monthly_income":
                round(
                    income,
                    2
                ),

            "monthly_expenses":
                round(
                    expenses,
                    2
                ),

            "monthly_savings":
                round(
                    monthly_savings,
                    2
                )

        })


    except Exception as exc:

        print(
            "GOAL IMPACT ERROR:",
            repr(exc)
        )

        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================
# FINPILOT AGENT
# ============================================================

def parse_add_transaction(
    message
):

    pattern = re.compile(

        r"(?:add|record|log)\s+"
        r"(?:₹|rs\.?|inr)?\s*"
        r"([\d,]+(?:\.\d+)?)\s+"
        r"(.+?)\s+"
        r"(expense|income)"
        r"(?:\s+(today|yesterday|\d{4}-\d{2}-\d{2}))?$",

        re.IGNORECASE

    )


    match = pattern.search(
        message.strip()
    )


    if not match:

        return None


    amount = clean_amount(
        match.group(1)
    )


    if amount <= 0:

        return None


    description = match.group(
        2
    ).strip()


    tx_type = match.group(
        3
    ).lower()


    when = (

        match.group(
            4
        )

        or

        "today"

    )


    return {

        "date":
            parse_date_from_text(
                when
            ),

        "description":
            description,

        "amount":
            amount,

        "category":
            categorize(
                description
            ),

        "transaction_type":
            tx_type

    }


def agent_query(
    message
):

    query = (
        message
        .lower()
        .strip()
    )


    transactions = get_transactions()


    # --------------------------------------------------------
    # SPENDING
    # --------------------------------------------------------

    if any(

        text in query

        for text in [

            "how much did i spend",

            "total spending",

            "total expenses",

            "how much have i spent"

        ]

    ):

        total = sum(

            abs(
                transaction_amount(
                    tx
                )
            )

            for tx
            in transactions

            if is_expense(
                tx
            )

        )


        return {

            "message":

                (
                    f"You have spent "
                    f"₹{total:,.2f} "
                    "in total."
                ),

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # INCOME
    # --------------------------------------------------------

    if any(

        text in query

        for text in [

            "income",

            "salary",

            "earned"

        ]

    ):

        total = sum(

            abs(
                transaction_amount(
                    tx
                )
            )

            for tx
            in transactions

            if is_income(
                tx
            )

        )


        return {

            "message":

                (
                    f"Your recorded income "
                    f"is ₹{total:,.2f}."
                ),

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # SAVINGS
    # --------------------------------------------------------

    if "saving" in query:

        income = sum(

            abs(
                transaction_amount(
                    tx
                )
            )

            for tx
            in transactions

            if is_income(
                tx
            )

        )


        expenses = sum(

            abs(
                transaction_amount(
                    tx
                )
            )

            for tx
            in transactions

            if is_expense(
                tx
            )

        )


        return {

            "message":

                (
                    f"Your current recorded "
                    f"savings are "
                    f"₹{income - expenses:,.2f}."
                ),

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # HIGHEST CATEGORY
    # --------------------------------------------------------

    if any(

        text in query

        for text in [

            "highest category",

            "biggest expense category",

            "most spending"

        ]

    ):

        categories = {}


        for tx
        in transactions:

            if is_expense(
                tx
            ):

                category = str(

                    tx.get(
                        "category",
                        "Other"
                    )

                )


                categories[category] = (

                    categories.get(
                        category,
                        0
                    )

                    +

                    abs(
                        transaction_amount(
                            tx
                        )
                    )

                )


        if categories:

            category = max(

                categories,

                key=categories.get

            )


            return {

                "message":

                    (
                        f"Your highest spending "
                        f"category is {category} "
                        f"at ₹{categories[category]:,.2f}."
                    ),

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }


    # --------------------------------------------------------
    # RECURRING
    # --------------------------------------------------------

    if any(

        text in query

        for text in [

            "recurring",

            "subscription",

            "subscriptions"

        ]

    ):

        analysis = analyze_transactions(
            transactions
        )


        recurring = (

            analysis.get(
                "recurring",
                []
            )

            or

            []

        )


        if recurring:

            return {

                "message":

                    (
                        "I detected "
                        f"{len(recurring)} "
                        "recurring payment pattern(s)."
                    ),

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }


        return {

            "message":
                (
                    "I couldn't confidently "
                    "detect recurring payments."
                ),

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # UNUSUAL
    # --------------------------------------------------------

    if any(

        text in query

        for text in [

            "unusual",

            "abnormal",

            "suspicious spending"

        ]

    ):

        analysis = analyze_transactions(
            transactions
        )


        unusual = (

            analysis.get(
                "unusual",
                []
            )

            or

            []

        )


        if unusual:

            return {

                "message":

                    (
                        "I detected "
                        f"{len(unusual)} "
                        "unusual spending pattern(s)."
                    ),

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }


        return {

            "message":
                "No unusual spending was detected.",

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # MERCHANT SEARCH
    # --------------------------------------------------------

    merchant_words = [

        "amazon",

        "swiggy",

        "zomato",

        "netflix",

        "spotify",

        "uber",

        "rent",

        "electricity"

    ]


    for word
    in merchant_words:

        if word not in query:

            continue


        matches = [

            tx

            for tx
            in transactions

            if word
            in
            str(

                tx.get(
                    "description",
                    ""
                )

            ).lower()

        ]


        if matches:

            total = sum(

                abs(
                    transaction_amount(
                        tx
                    )
                )

                for tx
                in matches

            )


            return {

                "message":

                    (
                        f"I found "
                        f"{len(matches)} "
                        f"{word} transaction(s) "
                        f"totaling "
                        f"₹{total:,.2f}."
                    ),

                "action":
                    "NONE",

                "requires_confirmation":
                    False,

                "transactions":
                    matches

            }


    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    return {

        "message":

            (
                "I can help with spending, "
                "income, savings, categories, "
                "recurring payments, unusual "
                "spending, transactions, budgets "
                "and goals."
            ),

        "action":
            "NONE",

        "requires_confirmation":
            False

    }


def build_agent_report():

    transactions = get_transactions()

    budgets = get_budgets()

    goals = get_goals()


    analysis = analyze_transactions(
        transactions
    )


    income = analysis[
        "income"
    ]


    expenses = analysis[
        "expenses"
    ]


    savings = analysis[
        "savings"
    ]


    savings_rate = analysis[
        "savings_rate"
    ]


    categories = (

        analysis.get(
            "category_spending",
            {}
        )

        or

        {}

    )


    recurring = (

        analysis.get(
            "recurring",
            []
        )

        or

        []

    )


    unusual = (

        analysis.get(
            "unusual",
            []
        )

        or

        []

    )


    key_insights = []

    spending_risks = []

    savings_opportunities = []

    recommendations = []


    if income > 0:

        if savings_rate >= 30:

            key_insights.append(
                "Your recorded savings rate is above 30%."
            )

        elif savings_rate >= 15:

            key_insights.append(
                "You maintained a positive savings rate."
            )

        else:

            spending_risks.append(
                "Your recorded savings rate is relatively low."
            )


    if (
        expenses > income
        and
        income > 0
    ):

        spending_risks.append(
            "Recorded expenses are higher than recorded income."
        )


    if categories:

        highest = max(

            categories,

            key=categories.get

        )


        key_insights.append(

            (
                f"{highest} is the highest "
                "spending category at "
                f"₹{categories[highest]:,.0f}."
            )

        )


        savings_opportunities.append(

            (
                f"Review {highest} spending "
                "and identify avoidable transactions."
            )

        )


    if recurring:

        recommendations.append(

            (
                "Review recurring payments and "
                "subscriptions that you no longer need."
            )

        )


    if unusual:

        spending_risks.append(

            (
                f"{len(unusual)} unusual spending "
                "pattern(s) were detected."
            )

        )


    for budget
    in budgets:

        category = str(

            budget.get(
                "category",
                "Other"
            )

        )


        budget_amount = float(

            budget.get(
                "amount",
                0
            )

            or

            0

        )


        actual = sum(

            abs(
                transaction_amount(
                    tx
                )
            )

            for tx
            in transactions

            if (

                is_expense(
                    tx
                )

                and

                str(

                    tx.get(
                        "category",
                        "Other"
                    )

                )

                ==

                category

            )

        )


        if (
            budget_amount
            and
            actual > budget_amount
        ):

            spending_risks.append(

                (
                    f"{category} spending "
                    "is above its monthly budget."
                )

            )

        elif (
            budget_amount
            and
            actual >= budget_amount * 0.8
        ):

            recommendations.append(

                (
                    f"{category} spending "
                    "is near its monthly budget limit."
                )

            )


    for goal
    in goals:

        target = float(

            goal.get(
                "target_amount",
                0
            )

            or

            0

        )


        current = float(

            goal.get(
                "current_amount",
                0
            )

            or

            0

        )


        if target > current:

            recommendations.append(

                (
                    f"Your goal "
                    f"'{goal.get('name', 'Financial Goal')}' "
                    f"still needs "
                    f"₹{target - current:,.0f}."
                )

            )


    if not key_insights:

        key_insights.append(

            (
                "More recorded transactions will "
                "improve the quality of analysis."
            )

        )


    if not recommendations:

        recommendations.append(

            (
                "Continue recording transactions "
                "to improve the quality of analysis."
            )

        )


    return {

        "headline":
            "Your FinPilot financial analysis is ready.",

        "summary":

            (
                f"You recorded "
                f"₹{income:,.0f} income, "
                f"₹{expenses:,.0f} expenses and "
                f"₹{savings:,.0f} savings."
            ),

        "key_insights":
            key_insights,

        "spending_risks":
            spending_risks,

        "savings_opportunities":
            savings_opportunities,

        "recommendations":
            recommendations,

        "transaction_count":
            len(transactions),

        "income":
            income,

        "expenses":
            expenses,

        "savings":
            savings,

        "savings_rate":
            savings_rate,

        "tools_used": [

            "Transaction analysis",

            "Recurring-spending detection",

            "Unusual-spending detection",

            "Budget analysis",

            "Goal analysis"

        ],

        "agent_insight":

            (
                "This analysis uses recorded transactions, "
                "budgets and goals for decision support, "
                "not investment advice."
            )

    }


# ============================================================
# AGENT CHAT
# ============================================================

@app.route(
    "/agent/chat",
    methods=["POST"]
)
def agent_chat():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )


        message = str(

            data.get(
                "message",
                ""
            )

        ).strip()


        if not message:

            return jsonify({

                "success":
                    False,

                "answer":
                    (
                        "Please enter a financial "
                        "question or command."
                    )

            }), 400


        result = agent_query(
            message
        )


        return jsonify({

            "success":
                True,

            "answer":
                result.get(
                    "message",
                    ""
                ),

            **result

        })


    except Exception as exc:

        print(
            "AGENT CHAT ERROR:",
            repr(exc)
        )


        return jsonify({

            "success":
                False,

            "error":
                str(exc)

        }), 500


# ============================================================
# AGENT ANALYZE
# ============================================================

@app.route(
    "/agent/analyze",
    methods=["POST"]
)
def agent_analyze():

    try:

        report = build_agent_report()


        return jsonify({

            "success":
                True,

            "report":
                report,

            "tools_used":
                report[
                    "tools_used"
                ]

        })


    except Exception as exc:

        print(
            "AGENT ANALYZE ERROR:",
            repr(exc)
        )


        return jsonify({

            "success":
                False,

            "error":
                str(exc)

        }), 500


# ============================================================
# LEGACY AGENT API
# ============================================================

@app.route(
    "/api/agent",
    methods=["POST"]
)
def api_agent():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or
            {}
        )


        message = str(

            data.get(
                "message",
                ""
            )

        ).strip()


        if not message:

            return jsonify({

                "message":
                    (
                        "Please enter a financial "
                        "question or command."
                    ),

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }), 400


        add_data = parse_add_transaction(
            message
        )


        if add_data:

            tx_id = add_transaction(

                date=add_data[
                    "date"
                ],

                description=add_data[
                    "description"
                ],

                amount=add_data[
                    "amount"
                ],

                category=add_data[
                    "category"
                ],

                transaction_type=add_data[
                    "transaction_type"
                ],

                source="agent"

            )


            return jsonify({

                "message":

                    (
                        f"Done. Added "
                        f"₹{add_data['amount']:,.2f} "
                        f"{add_data['transaction_type']} "
                        f"for "
                        f"{add_data['description']}."
                    ),

                "action":
                    "ADD_TRANSACTION",

                "requires_confirmation":
                    False,

                "data": {

                    **add_data,

                    "id":
                        tx_id

                }

            })


        return jsonify(
            agent_query(
                message
            )
        )


    except Exception as exc:

        print(
            "AGENT ERROR:",
            repr(exc)
        )


        return jsonify({

            "message":
                (
                    "Something went wrong "
                    "while processing your request."
                ),

            "error":
                str(exc),

            "action":
                "ERROR",

            "requires_confirmation":
                False

        }), 500


# ============================================================
# MONTHLY REPORT
# ============================================================

def get_monthly_report_data(
    requested_month
):

    transactions = get_transactions()


    month_transactions = [

        tx

        for tx
        in transactions

        if str(

            tx.get(
                "date",
                ""
            )

        ).startswith(
            requested_month
        )

    ]


    income = sum(

        abs(
            transaction_amount(
                tx
            )
        )

        for tx
        in month_transactions

        if is_income(
            tx
        )

    )


    expenses = sum(

        abs(
            transaction_amount(
                tx
            )
        )

        for tx
        in month_transactions

        if is_expense(
            tx
        )

    )


    savings = (

        income -
        expenses

    )


    savings_rate = (

        savings /
        income *
        100

        if income > 0

        else 0

    )


    categories = {}


    for tx
    in month_transactions:

        if not is_expense(
            tx
        ):

            continue


        category = str(

            tx.get(
                "category",
                "Other"
            )

        )


        categories[category] = (

            categories.get(
                category,
                0
            )

            +

            abs(
                transaction_amount(
                    tx
                )
            )

        )


    highest_category = (

        max(
            categories,
            key=categories.get
        )

        if categories

        else

        None

    )


    highest_amount = (

        categories.get(
            highest_category,
            0
        )

        if highest_category

        else

        0

    )


    budgets = []


    for budget
    in get_budgets():

        if (

            str(
                budget.get(
                    "month",
                    requested_month
                )
            )

            !=

            requested_month

        ):

            continue


        category = str(

            budget.get(
                "category",
                "Other"
            )

        )


        amount = float(

            budget.get(
                "amount",
                0
            )

            or

            0

        )


        actual = float(

            categories.get(
                category,
                0
            )

            or

            0

        )


        used = (

            actual /
            amount *
            100

            if amount > 0

            else

            0

        )


        budgets.append({

            "category":
                category,

            "budget":
                amount,

            "amount":
                amount,

            "actual":
                actual,

            "used_percent":
                round(
                    used,
                    1
                )

        })


    goals = []


    for goal
    in get_goals():

        target = float(

            goal.get(
                "target_amount",
                0
            )

            or

            0

        )


        current = float(

            goal.get(
                "current_amount",
                0
            )

            or

            0

        )


        progress = (

            min(

                current /
                target *
                100,

                100

            )

            if target > 0

            else

            0

        )


        goals.append({

            "name":
                goal.get(
                    "name",
                    "Goal"
                ),

            "target_amount":
                target,

            "current_amount":
                current,

            "progress":
                round(
                    progress,
                    1
                ),

            "deadline":
                goal.get(
                    "deadline"
                )

        })


    insights = []


    if income > 0:

        if savings_rate >= 30:

            insights.append(
                "Your recorded savings rate is above 30% this month."
            )

        elif savings_rate >= 15:

            insights.append(
                "You maintained a positive savings rate this month."
            )

        else:

            insights.append(
                "Your recorded savings rate is relatively low this month."
            )


    if highest_category:

        insights.append(

            (
                f"{highest_category} was your highest "
                f"spending category at "
                f"₹{highest_amount:,.0f}."
            )

        )


    if (
        income > 0
        and
        expenses > income
    ):

        insights.append(

            (
                "Your recorded expenses were higher "
                "than your income this month."
            )

        )


    recurring = (

        analyze_transactions(
            month_transactions
        )

        .get(
            "recurring",
            []
        )

    )


    recurring_total = 0


    for item
    in recurring:

        if isinstance(
            item,
            dict
        ):

            recurring_total += abs(

                clean_amount(

                    item.get(
                        "amount",
                        0
                    )

                )

            )


    return {

        "month":
            requested_month,

        "transaction_count":
            len(month_transactions),

        "income":
            round(
                income,
                2
            ),

        "expenses":
            round(
                expenses,
                2
            ),

        "savings":
            round(
                savings,
                2
            ),

        "savings_rate":
            round(
                savings_rate,
                1
            ),

        "categories":
            categories,

        "category_spending":
            categories,

        "highest_category":
            highest_category,

        "highest_category_amount":
            round(
                highest_amount,
                2
            ),

        "recurring_total":
            round(
                recurring_total,
                2
            ),

        "budgets":
            budgets,

        "goals":
            goals,

        "insights":
            insights

    }


@app.route(
    "/api/monthly-report",
    methods=["GET"]
)
def monthly_report():

    try:

        month = request.args.get(

            "month",

            date.today().strftime(
                "%Y-%m"
            )

        )


        if not re.fullmatch(
            r"\d{4}-\d{2}",
            month
        ):

            return jsonify({

                "error":
                    "Month must be in YYYY-MM format."

            }), 400


        return jsonify(

            get_monthly_report_data(
                month
            )

        )


    except Exception as exc:

        print(
            "MONTHLY REPORT ERROR:",
            repr(exc)
        )


        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================
# PDF REPORT
# ============================================================

@app.route(
    "/api/monthly-report/pdf",
    methods=["GET"]
)
def monthly_report_pdf():

    try:

        month = request.args.get(

            "month",

            date.today().strftime(
                "%Y-%m"
            )

        )


        if not re.fullmatch(
            r"\d{4}-\d{2}",
            month
        ):

            return jsonify({

                "error":
                    "Month must be in YYYY-MM format."

            }), 400


        report = get_monthly_report_data(
            month
        )


        buffer = BytesIO()


        document = SimpleDocTemplate(

            buffer,

            pagesize=A4,

            rightMargin=40,

            leftMargin=40,

            topMargin=40,

            bottomMargin=40

        )


        styles = getSampleStyleSheet()


        title_style = ParagraphStyle(

            "FinPilotTitle",

            parent=styles[
                "Title"
            ],

            fontSize=24,

            alignment=TA_CENTER,

            spaceAfter=8

        )


        subtitle_style = ParagraphStyle(

            "FinPilotSubtitle",

            parent=styles[
                "Normal"
            ],

            fontSize=11,

            alignment=TA_CENTER,

            textColor=colors.grey,

            spaceAfter=20

        )


        heading_style = ParagraphStyle(

            "FinPilotHeading",

            parent=styles[
                "Heading2"
            ],

            fontSize=15,

            spaceBefore=15,

            spaceAfter=10

        )


        normal_style = ParagraphStyle(

            "FinPilotNormal",

            parent=styles[
                "Normal"
            ],

            fontSize=10,

            leading=14

        )


        story = []


        story.append(

            Paragraph(

                "FinPilot",

                title_style

            )

        )


        story.append(

            Paragraph(

                "Personal Finance Monthly Report",

                subtitle_style

            )

        )


        story.append(

            Paragraph(

                f"Report Period: {month}",

                normal_style

            )

        )


        story.append(
            Spacer(
                1,
                15
            )
        )


        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        summary = Table(

            [

                [
                    "Income",
                    "Expenses",
                    "Savings",
                    "Savings Rate"
                ],

                [

                    f"Rs. {report['income']:,.2f}",

                    f"Rs. {report['expenses']:,.2f}",

                    f"Rs. {report['savings']:,.2f}",

                    f"{report['savings_rate']:.1f}%"

                ]

            ],

            colWidths=[

                125,
                125,
                125,
                125

            ]

        )


        summary.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#111827"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.lightgrey
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    10
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    10
                )

            ])

        )


        story.append(
            summary
        )


        # ----------------------------------------------------
        # CATEGORY BREAKDOWN
        # ----------------------------------------------------

        story.append(

            Paragraph(

                "Spending Breakdown",

                heading_style

            )

        )


        total = sum(

            report[
                "categories"
            ].values()

        )


        category_data = [

            [
                "Category",
                "Amount",
                "Percentage"
            ]

        ]


        for category, amount
        in sorted(

            report[
                "categories"
            ].items(),

            key=lambda x:
                x[1],

            reverse=True

        ):

            pct = (

                amount /
                total *
                100

                if total > 0

                else

                0

            )


            category_data.append([

                str(
                    category
                ),

                f"Rs. {amount:,.2f}",

                f"{pct:.1f}%"

            ])


        if len(
            category_data
        ) == 1:

            category_data.append([

                "No spending recorded",

                "Rs. 0.00",

                "0%"

            ])


        category_table = Table(

            category_data,

            colWidths=[

                250,
                150,
                100

            ]

        )


        category_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#111827"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.lightgrey
                ),

                (
                    "ALIGN",
                    (1, 1),
                    (-1, -1),
                    "RIGHT"
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )

            ])

        )


        story.append(
            category_table
        )


        # ----------------------------------------------------
        # INSIGHTS
        # ----------------------------------------------------

        story.append(

            Paragraph(

                "FinPilot Insights",

                heading_style

            )

        )


        report_insights = (

            report["insights"]

            or

            [
                "No major insights detected for this month."
            ]

        )


        for insight
        in report_insights:

            story.append(

                Paragraph(

                    f"• {insight}",

                    normal_style

                )

            )


            story.append(

                Spacer(
                    1,
                    5
                )

            )


        story.append(
            Spacer(
                1,
                10
            )
        )


        story.append(

            Paragraph(

                (
                    "Total transactions recorded: "
                    f"{report['transaction_count']}"
                ),

                normal_style

            )

        )


        story.append(
            Spacer(
                1,
                15
            )
        )


        story.append(

            Paragraph(

                (
                    "Generated by FinPilot "
                    "Personal Finance Decision Support Agent."
                ),

                subtitle_style

            )

        )


        document.build(
            story
        )


        buffer.seek(
            0
        )


        return send_file(

            buffer,

            mimetype="application/pdf",

            as_attachment=True,

            download_name=(

                f"FinPilot_Report_"
                f"{month}.pdf"

            )

        )


    except Exception as exc:

        print(
            "PDF EXPORT ERROR:",
            repr(exc)
        )


        return jsonify({

            "error":
                str(exc)

        }), 500


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/api/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "status":
            "ok",

        "message":
            "FinPilot backend is running.",

        "timestamp":
            datetime.now().isoformat()

    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def request_too_large(
    error
):

    if (

        request.path.startswith(
            "/api/"
        )

        or

        request.path.startswith(
            "/agent/"
        )

    ):

        return jsonify({

            "success":
                False,

            "error":
                (
                    "Uploaded file is too large. "
                    "Maximum size is 16 MB."
                )

        }), 413


    return (
        "Uploaded file is too large.",
        413
    )


@app.errorhandler(404)
def not_found(
    error
):

    if (

        request.path.startswith(
            "/api/"
        )

        or

        request.path.startswith(
            "/agent/"
        )

    ):

        return jsonify({

            "success":
                False,

            "error":
                "Route not found."

        }), 404


    return (
        "Page not found.",
        404
    )


@app.errorhandler(500)
def internal_error(
    error
):

    if (

        request.path.startswith(
            "/api/"
        )

        or

        request.path.startswith(
            "/agent/"
        )

    ):

        return jsonify({

            "success":
                False,

            "error":
                "Internal server error."

        }), 500


    return (
        "Internal server error.",
        500
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(

            os.environ.get(
                "PORT",
                "5000"
            )

        ),

        debug=False

    )

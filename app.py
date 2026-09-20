from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file
)
from werkzeug.utils import secure_filename

from finance_engine import (
    analyze_file,
    ai_transactions_to_dataframe,
    analyze_dataframe,
    categorize
)

from ai_extractor import (
    extract_from_image,
    extract_from_text
)

from database import (
    add_transactions,
    get_transactions,
    add_transaction,
    get_transaction,
    update_transaction,
    delete_transaction,
    get_budgets,
    set_budget,
    delete_budget,
    get_goals,
    add_goal,
    get_goal,
    update_goal,
    delete_goal
)

import os
import re
from datetime import datetime, date, timedelta
from io import BytesIO

import fitz
import pandas as pd
from docx import Document

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

# Always resolve runtime paths from the project directory.
# Render runs Linux and its working directory should never be assumed.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATA_FOLDER = os.path.join(BASE_DIR, "data")
DEMO_FILE = os.path.join(DATA_FOLDER, "demo_transactions.csv")

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
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
    "jpeg"
}


def seed_demo_data():
    """Seed the bundled demo statement on a fresh Render instance."""

    try:
        existing = get_transactions()

        if existing:
            return

        if not os.path.exists(DEMO_FILE):
            print("DEMO SEED: demo_transactions.csv not found.")
            return

        df = pd.read_csv(DEMO_FILE)
        added = 0

        for _, row in df.iterrows():
            raw_amount = row.get("Amount", 0)

            try:
                amount = float(raw_amount)
            except Exception:
                continue

            if amount == 0:
                continue

            description = str(
                row.get("Description", "Unknown transaction")
            ).strip()

            transaction_date = str(
                row.get("Date", date.today().isoformat())
            ).strip()

            transaction_type = (
                "income" if amount > 0 else "expense"
            )

            transaction_id = add_transaction(
                date=transaction_date,
                description=description,
                amount=abs(amount),
                category=categorize(description),
                transaction_type=transaction_type,
                source="demo-seed"
            )

            if transaction_id:
                added += 1

        print(
            f"DEMO SEED: added {added} transaction(s)."
        )

    except Exception as exc:
        print(
            "DEMO SEED ERROR:",
            repr(exc)
        )


# Initialize the database module first, then seed only when empty.
try:
    seed_demo_data()
except Exception as exc:
    print("STARTUP ERROR:", repr(exc))


# ============================================================
# GENERAL HELPERS
# ============================================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower() in ALLOWED_EXTENSIONS
    )


def clean_amount(value):

    if value is None:
        return 0.0

    value = str(value)

    value = (
        value
        .replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("INR", "")
        .replace(",", "")
        .strip()
    )

    try:
        return float(value)

    except Exception:
        return 0.0


def transaction_amount(transaction):

    try:

        return float(
            transaction.get(
                "amount",
                0
            ) or 0
        )

    except Exception:

        return 0.0


def get_transaction_type(transaction):

    return str(
        transaction.get(
            "transaction_type",
            transaction.get(
                "type",
                ""
            )
        )
    ).lower()


def parse_date_from_text(text):

    text = str(text).lower()

    today = date.today()

    if "today" in text:

        return today.isoformat()

    if "yesterday" in text:

        return (
            today - timedelta(days=1)
        ).isoformat()

    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
        r"\b\d{2}-\d{2}-\d{4}\b"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if not match:
            continue

        value = match.group(0)

        try:

            if "/" in value:

                dt = datetime.strptime(
                    value,
                    "%d/%m/%Y"
                )

                return dt.date().isoformat()

            if (
                len(value) == 10
                and value[4] == "-"
            ):

                datetime.strptime(
                    value,
                    "%Y-%m-%d"
                )

                return value

            dt = datetime.strptime(
                value,
                "%d-%m-%Y"
            )

            return dt.date().isoformat()

        except Exception:

            pass

    return today.isoformat()


# ============================================================
# PAGE ROUTES
# ============================================================

@app.route("/")
def index():

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
# FILE TEXT EXTRACTION
# ============================================================

def extract_pdf_text(filepath):

    text = ""

    document = fitz.open(
        filepath
    )

    for page in document:

        text += (
            page.get_text()
            + "\n"
        )

    document.close()

    return text


def extract_docx_text(filepath):

    document = Document(
        filepath
    )

    paragraphs = []

    for paragraph in document.paragraphs:

        if paragraph.text.strip():

            paragraphs.append(
                paragraph.text
            )

    return "\n".join(
        paragraphs
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
                "success": False,
                "error": "No file uploaded."
            }), 400

        file = request.files["file"]

        if not file or not file.filename:

            return jsonify({
                "success": False,
                "error": "No file selected."
            }), 400

        if not allowed_file(file.filename):

            return jsonify({
                "success": False,
                "error": "Unsupported file format."
            }), 400

        # Sanitize the browser-provided filename and use an ABSOLUTE path.
        filename = secure_filename(file.filename)

        if not filename:
            return jsonify({
                "success": False,
                "error": "Invalid file name."
            }), 400

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        os.makedirs(
            app.config["UPLOAD_FOLDER"],
            exist_ok=True
        )

        file.save(filepath)

        if not os.path.exists(filepath):
            return jsonify({
                "success": False,
                "error": "Uploaded file could not be saved on the server."
            }), 500

        extension = filename.rsplit(
            ".",
            1
        )[1].lower()

        transactions = []
        analysis = None

        # CSV / EXCEL
        if extension in {"csv", "xlsx", "xls"}:

            analysis = analyze_file(filepath)

            if isinstance(analysis, dict):
                transactions = analysis.get(
                    "transactions",
                    []
                )

        # PDF
        elif extension == "pdf":

            text = extract_pdf_text(filepath)
            extracted = extract_from_text(text)
            transactions = extracted.get(
                "transactions",
                []
            )

        # DOCX
        elif extension == "docx":

            text = extract_docx_text(filepath)
            extracted = extract_from_text(text)
            transactions = extracted.get(
                "transactions",
                []
            )

        # IMAGE
        elif extension in {"png", "jpg", "jpeg"}:

            extracted = extract_from_image(filepath)
            transactions = extracted.get(
                "transactions",
                []
            )

        # SAVE TRANSACTIONS
        if transactions:

            dataframe = ai_transactions_to_dataframe(
                transactions
            )

            save_result = add_transactions(
                dataframe
            )

            # Keep the upload response useful for duplicate testing.
            if isinstance(save_result, dict):
                added_count = save_result.get("added", 0)
                skipped_count = save_result.get("skipped", 0)
            else:
                added_count = None
                skipped_count = None

            try:
                # Analyze the just-uploaded statement for the UI response.
                analysis = analyze_dataframe(
                    dataframe
                )
            except Exception:
                pass
        else:
            added_count = 0
            skipped_count = 0

        if analysis is None:
            analysis = {
                "income": 0,
                "expenses": 0,
                "savings": 0,
                "savings_rate": 0,
                "transaction_count": 0,
                "category_spending": {},
                "recurring": [],
                "unusual": [],
                "monthly_spending": {},
                "transactions": []
            }

        response = {
            "success": True,
            "message": (
                f"Successfully analyzed {len(transactions)} transaction(s)."
            ),
            "filename": filename,
            "analysis": analysis
        }

        if added_count is not None:
            response["added"] = added_count

        if skipped_count is not None:
            response["skipped"] = skipped_count

        return jsonify(response)

    except Exception as e:

        print(
            "UPLOAD ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": str(e)
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

        if not transactions:

            return jsonify({
                "income": 0,
                "expenses": 0,
                "savings": 0,
                "savings_rate": 0,
                "transaction_count": 0,
                "category_spending": {},
                "recurring": [],
                "unusual": [],
                "monthly_spending": {},
                "transactions": [],
                "insights": []
            })

        # Database rows use lowercase keys and store amount/type separately.
        # finance_engine expects statement-style Date/Description/Amount data.
        normalized_transactions = []

        for transaction in transactions:

            try:
                amount = float(
                    transaction.get("amount", 0) or 0
                )
            except Exception:
                amount = 0.0

            transaction_type = str(
                transaction.get(
                    "type",
                    transaction.get("transaction_type", "")
                ) or ""
            ).lower()

            if transaction_type == "expense":
                amount = -abs(amount)
            else:
                amount = abs(amount)

            normalized_transactions.append({
                "Date": transaction.get("date", ""),
                "Description": transaction.get("description", ""),
                "Amount": amount,
                "Category": transaction.get("category", "Other")
            })

        dataframe = pd.DataFrame(
            normalized_transactions
        )

        analysis = analyze_dataframe(
            dataframe
        )

        # Always expose the database records to the existing frontend.
        analysis["transactions"] = transactions
        analysis["transaction_count"] = len(transactions)

        analysis["income"] = float(
            analysis.get("income", 0) or 0
        )
        analysis["expenses"] = float(
            analysis.get("expenses", 0) or 0
        )
        analysis["savings"] = float(
            analysis.get("savings", 0) or 0
        )
        analysis["savings_rate"] = float(
            analysis.get("savings_rate", 0) or 0
        )

        insights = []
        income = analysis["income"]
        expenses = analysis["expenses"]
        savings = analysis["savings"]

        if income > 0:
            rate = (savings / income) * 100

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
                f"You have recorded ₹{expenses:,.0f} in expenses."
            )

        if savings > 0:
            insights.append(
                f"Your recorded savings are ₹{savings:,.0f}."
            )
        elif savings < 0:
            insights.append(
                "Your recorded expenses are higher than your income."
            )

        category_spending = analysis.get(
            "category_spending",
            {}
        ) or {}

        if category_spending:

            highest_category = max(
                category_spending,
                key=category_spending.get
            )

            highest_amount = category_spending[
                highest_category
            ]

            insights.append(
                f"{highest_category} is your highest spending category at ₹{highest_amount:,.0f}."
            )

        analysis["insights"] = insights

        return jsonify(analysis)

    except Exception as e:

        print(
            "DASHBOARD ERROR:",
            repr(e)
        )

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# TRANSACTIONS
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

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


@app.route(
    "/api/transactions",
    methods=["POST"]
)
def create_transaction():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        description = str(
            data.get(
                "description",
                ""
            )
        ).strip()

        if not description:

            return jsonify({
                "error":
                    "Description is required."
            }), 400

        amount = clean_amount(
            data.get(
                "amount",
                0
            )
        )

        if amount <= 0:

            return jsonify({
                "error":
                    "Amount must be greater than zero."
            }), 400

        transaction_type = str(

            data.get(
                "transaction_type",
                data.get(
                    "type",
                    "expense"
                )
            )

        ).lower()

        if transaction_type not in {
            "income",
            "expense"
        }:

            transaction_type = "expense"

        transaction_date = data.get(
            "date"
        )

        if not transaction_date:

            transaction_date = (
                date.today().isoformat()
            )

        category = data.get(
            "category"
        )

        if not category:

            category = categorize(
                description
            )

        transaction_id = add_transaction(

            date=transaction_date,

            description=description,

            amount=amount,

            category=category,

            transaction_type=transaction_type,

            source=data.get(
                "source",
                "manual"
            )

        )

        return jsonify({

            "success": True,

            "message":
                "Transaction added successfully.",

            "id":
                transaction_id

        })

    except Exception as e:

        print(
            "CREATE TRANSACTION ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500


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

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


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

        data = request.get_json(
            silent=True
        ) or {}

        transaction_date = data.get(
            "date",
            existing.get("date")
        )

        description = data.get(
            "description",
            existing.get("description")
        )

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

        transaction_type = data.get(

            "transaction_type",

            existing.get(
                "transaction_type",
                existing.get(
                    "type",
                    "expense"
                )
            )
        )

        update_transaction(

            transaction_id,

            date=transaction_date,

            description=description,

            amount=amount,

            category=category,

            transaction_type=transaction_type

        )

        return jsonify({

            "success": True,

            "message":
                "Transaction updated successfully."

        })

    except Exception as e:

        print(
            "UPDATE TRANSACTION ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500


@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["DELETE"]
)
def remove_transaction(
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

        delete_transaction(
            transaction_id
        )

        return jsonify({

            "success": True,

            "message":
                "Transaction deleted successfully."

        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# BUDGETS
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

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


@app.route(
    "/api/budgets",
    methods=["POST"]
)
def create_budget():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        category = str(
            data.get(
                "category",
                ""
            )
        ).strip()

        if not category:

            return jsonify({
                "error":
                    "Category is required."
            }), 400

        amount = clean_amount(
            data.get(
                "amount",
                0
            )
        )

        if amount <= 0:

            return jsonify({
                "error":
                    "Budget amount must be greater than zero."
            }), 400

        month = data.get(
            "month",
            date.today().strftime(
                "%Y-%m"
            )
        )

        budget_id = set_budget(

            category=category,

            amount=amount,

            month=month

        )

        return jsonify({

            "success": True,

            "message":
                "Budget saved successfully.",

            "id":
                budget_id

        })

    except Exception as e:

        print(
            "BUDGET ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500


@app.route(
    "/api/budgets/<int:budget_id>",
    methods=["DELETE"]
)
def remove_budget(
    budget_id
):

    try:

        delete_budget(
            budget_id
        )

        return jsonify({

            "success": True,

            "message":
                "Budget deleted successfully."

        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# GOALS
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

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


@app.route(
    "/api/goals",
    methods=["POST"]
)
def create_goal():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        name = str(
            data.get(
                "name",
                ""
            )
        ).strip()

        if not name:

            return jsonify({
                "error":
                    "Goal name is required."
            }), 400

        target_amount = clean_amount(
            data.get(
                "target_amount",
                0
            )
        )

        if target_amount <= 0:

            return jsonify({
                "error":
                    "Target amount must be greater than zero."
            }), 400

        current_amount = clean_amount(
            data.get(
                "current_amount",
                0
            )
        )

        deadline = data.get(
            "deadline"
        )

        goal_id = add_goal(

            name=name,

            target_amount=target_amount,

            current_amount=current_amount,

            deadline=deadline

        )

        return jsonify({

            "success": True,

            "message":
                "Goal created successfully.",

            "id":
                goal_id

        })

    except Exception as e:

        print(
            "CREATE GOAL ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500


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

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


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

        data = request.get_json(
            silent=True
        ) or {}

        name = data.get(
            "name",
            existing.get("name")
        )

        target_amount = clean_amount(
            data.get(
                "target_amount",
                existing.get(
                    "target_amount",
                    0
                )
            )
        )

        current_amount = clean_amount(
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
            existing.get("deadline")
        )

        update_goal(

            goal_id,

            name=name,

            target_amount=target_amount,

            current_amount=current_amount,

            deadline=deadline

        )

        return jsonify({

            "success": True,

            "message":
                "Goal updated successfully."

        })

    except Exception as e:

        print(
            "UPDATE GOAL ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500


@app.route(
    "/api/goals/<int:goal_id>",
    methods=["DELETE"]
)
def remove_goal(
    goal_id
):

    try:

        delete_goal(
            goal_id
        )

        return jsonify({

            "success": True,

            "message":
                "Goal deleted successfully."

        })

    except Exception as e:

        return jsonify({
            "error": str(e)
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

        total_income = 0

        total_expenses = 0

        for transaction in transactions:

            amount = transaction_amount(
                transaction
            )

            transaction_type = (
                get_transaction_type(
                    transaction
                )
            )

            if (
                transaction_type == "income"
                or amount > 0
            ):

                total_income += abs(
                    amount
                )

            else:

                total_expenses += abs(
                    amount
                )

        monthly_savings = max(
            total_income -
            total_expenses,
            0
        )

        results = []

        for goal in goals:

            target = float(
                goal.get(
                    "target_amount",
                    0
                ) or 0
            )

            current = float(
                goal.get(
                    "current_amount",
                    0
                ) or 0
            )

            remaining = max(
                target -
                current,
                0
            )

            progress = 0

            if target > 0:

                progress = min(
                    (
                        current /
                        target
                    ) * 100,
                    100
                )

            months_needed = None

            if (
                remaining > 0
                and monthly_savings > 0
            ):

                months_needed = (
                    remaining /
                    monthly_savings
                )

            results.append({

                "id":
                    goal.get("id"),

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

                    round(
                        months_needed,
                        1
                    )
                    if months_needed
                    is not None
                    else None,

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
                    total_income,
                    2
                ),

            "monthly_expenses":
                round(
                    total_expenses,
                    2
                ),

            "monthly_savings":
                round(
                    monthly_savings,
                    2
                )

        })

    except Exception as e:

        print(
            "GOAL IMPACT ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
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

        category_actuals = {}

        for transaction in transactions:

            amount = transaction_amount(
                transaction
            )

            transaction_type = (
                get_transaction_type(
                    transaction
                )
            )

            if (
                transaction_type == "income"
                or amount > 0
            ):

                continue

            category = str(
                transaction.get(
                    "category",
                    "Other"
                )
            )

            category_actuals[category] = (

                category_actuals.get(
                    category,
                    0
                )

                + abs(amount)

            )

        results = []

        for budget in budgets:

            category = str(
                budget.get(
                    "category",
                    "Other"
                )
            )

            budget_amount = float(

                budget.get(
                    "amount",
                    budget.get(
                        "budget_amount",
                        0
                    )
                )
                or 0

            )

            actual = float(
                category_actuals.get(
                    category,
                    0
                )
            )

            remaining = (
                budget_amount -
                actual
            )

            used_percent = 0

            if budget_amount > 0:

                used_percent = (
                    actual /
                    budget_amount
                ) * 100

            if used_percent >= 100:

                status = "over"

            elif used_percent >= 80:

                status = "warning"

            else:

                status = "healthy"

            results.append({

                "id":
                    budget.get("id"),

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
                        remaining,
                        2
                    ),

                "used_percent":
                    round(
                        used_percent,
                        1
                    ),

                "status":
                    status

            })

        return jsonify({
            "budgets":
                results
        })

    except Exception as e:

        print(
            "BUDGET ANALYSIS ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# FINPILOT AGENT
# ============================================================

def agent_query(message):

    query = message.lower().strip()

    transactions = get_transactions()

    # TOTAL SPENDING

    if (
        "how much did i spend" in query
        or "total spending" in query
        or "total expenses" in query
        or "how much have i spent" in query
    ):

        expenses = 0

        for t in transactions:

            amount = transaction_amount(t)

            if (
                get_transaction_type(t)
                == "expense"
                or amount < 0
            ):

                expenses += abs(amount)

        return {

            "message":
                f"You have spent ₹{expenses:,.2f} in total.",

            "action":
                "NONE",

            "requires_confirmation":
                False

        }

    # INCOME

    if (
        "income" in query
        or "salary" in query
        or "earned" in query
    ):

        income = 0

        for t in transactions:

            amount = transaction_amount(t)

            if (
                get_transaction_type(t)
                == "income"
                or amount > 0
            ):

                income += abs(amount)

        return {

            "message":
                f"Your recorded income is ₹{income:,.2f}.",

            "action":
                "NONE",

            "requires_confirmation":
                False

        }

    # SAVINGS

    if (
        "savings" in query
        or "saved" in query
    ):

        income = 0
        expenses = 0

        for t in transactions:

            amount = transaction_amount(t)

            if (
                get_transaction_type(t)
                == "income"
                or amount > 0
            ):

                income += abs(amount)

            else:

                expenses += abs(amount)

        savings = (
            income -
            expenses
        )

        return {

            "message":
                f"Your current recorded savings are ₹{savings:,.2f}.",

            "action":
                "NONE",

            "requires_confirmation":
                False

        }

    # HIGHEST CATEGORY

    if (
        "highest category" in query
        or "biggest expense category" in query
        or "most spending" in query
    ):

        categories = {}

        for t in transactions:

            amount = transaction_amount(t)

            if (
                get_transaction_type(t)
                == "expense"
                or amount < 0
            ):

                category = t.get(
                    "category",
                    "Other"
                )

                categories[category] = (

                    categories.get(
                        category,
                        0
                    )
                    + abs(amount)

                )

        if categories:

            highest = max(
                categories,
                key=categories.get
            )

            return {

                "message":
                    f"Your highest spending category is {highest} at ₹{categories[highest]:,.2f}.",

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }

    # RECURRING

    if (
        "recurring" in query
        or "subscription" in query
        or "subscriptions" in query
    ):

        dataframe = pd.DataFrame(
            transactions
        )

        if not dataframe.empty:

            analysis = analyze_dataframe(
                dataframe
            )

            recurring = analysis.get(
                "recurring",
                []
            )

            if recurring:

                names = []

                for item in recurring:

                    if isinstance(
                        item,
                        dict
                    ):

                        names.append(

                            str(
                                item.get(
                                    "description",
                                    item.get(
                                        "name",
                                        "Payment"
                                    )
                                )
                            )

                        )

                    else:

                        names.append(
                            str(item)
                        )

                return {

                    "message":
                        "Recurring payments detected: "
                        + ", ".join(names),

                    "action":
                        "NONE",

                    "requires_confirmation":
                        False

                }

        return {

            "message":
                "I couldn't detect recurring payments from the current transaction data.",

            "action":
                "NONE",

            "requires_confirmation":
                False

        }

    # UNUSUAL

    if (
        "unusual" in query
        or "abnormal" in query
        or "suspicious spending" in query
    ):

        dataframe = pd.DataFrame(
            transactions
        )

        if not dataframe.empty:

            analysis = analyze_dataframe(
                dataframe
            )

            unusual = analysis.get(
                "unusual",
                []
            )

            if unusual:

                first = unusual[0]

                if isinstance(
                    first,
                    dict
                ):

                    description = first.get(
                        "description",
                        "Transaction"
                    )

                    amount = first.get(
                        "amount",
                        0
                    )

                    return {

                        "message":
                            f"An unusual transaction was detected: {description} for ₹{abs(float(amount)):,.2f}.",

                        "action":
                            "NONE",

                        "requires_confirmation":
                            False

                    }

        return {

            "message":
                "No unusual spending was detected from the current data.",

            "action":
                "NONE",

            "requires_confirmation":
                False

        }

    # SEARCH

    search_words = [
        "amazon",
        "swiggy",
        "zomato",
        "netflix",
        "spotify",
        "uber",
        "rent",
        "electricity"
    ]

    for word in search_words:

        if word in query:

            matches = []

            for t in transactions:

                description = str(
                    t.get(
                        "description",
                        ""
                    )
                ).lower()

                if word in description:

                    matches.append(t)

            if matches:

                total = sum(

                    abs(
                        transaction_amount(t)
                    )

                    for t in matches

                )

                return {

                    "message":
                        f"I found {len(matches)} {word} transaction(s) totaling ₹{total:,.2f}.",

                    "action":
                        "NONE",

                    "requires_confirmation":
                        False,

                    "transactions":
                        matches

                }

    return {

        "message":
            "I can help with spending, income, savings, categories, recurring payments, unusual spending, transactions, budgets and goals.",

        "action":
            "NONE",

        "requires_confirmation":
            False

    }


# ============================================================
# ADD TRANSACTION PARSER
# ============================================================

def parse_add_transaction(message):

    pattern = re.compile(

        r"""
        (?:add|record|log)
        \s+
        (?:₹|rs\.?|inr)?
        \s*
        ([\d,]+(?:\.\d+)?)
        \s+
        (.+?)
        \s+
        (expense|income)
        (?:\s+(today|yesterday|\d{4}-\d{2}-\d{2}))?
        $
        """,

        re.IGNORECASE |
        re.VERBOSE

    )

    match = pattern.search(
        message.strip()
    )

    if not match:

        return None

    amount = clean_amount(
        match.group(1)
    )

    description = (
        match.group(2)
        .strip()
    )

    transaction_type = (
        match.group(3)
        .lower()
    )

    date_text = (
        match.group(4)
        or "today"
    )

    transaction_date = (
        parse_date_from_text(
            date_text
        )
    )

    category = categorize(
        description
    )

    return {

        "date":
            transaction_date,

        "description":
            description,

        "amount":
            amount,

        "category":
            category,

        "transaction_type":
            transaction_type,

        "source":
            "agent"

    }


# ============================================================
# AGENT API
# ============================================================

@app.route(
    "/api/agent",
    methods=["POST"]
)
def agent():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        message = str(
            data.get(
                "message",
                ""
            )
        ).strip()

        if not message:

            return jsonify({

                "message":
                    "Please enter a financial question or command.",

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            })

        # ADD TRANSACTION

        add_data = parse_add_transaction(
            message
        )

        if add_data:

            transaction_id = add_transaction(

                date=add_data["date"],

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
                    f"Done. Added ₹{add_data['amount']:,.2f} {add_data['transaction_type']} for {add_data['description']}.",

                "action":
                    "ADD_TRANSACTION",

                "requires_confirmation":
                    False,

                "data": {

                    **add_data,

                    "id":
                        transaction_id

                }

            })

        # BUDGET

        budget_pattern = re.search(

            r"""
            (?:
                set\s+(.+?)\s+budget
                |
                budget\s+(.+?)
            )
            \s+
            (?:to\s+)?
            (?:₹|rs\.?|inr)?
            \s*
            ([\d,]+(?:\.\d+)?)
            $
            """,

            message.strip(),

            re.IGNORECASE |
            re.VERBOSE

        )

        if budget_pattern:

            category = (

                budget_pattern.group(1)
                or budget_pattern.group(2)

            ).strip()

            amount = clean_amount(
                budget_pattern.group(3)
            )

            month = date.today().strftime(
                "%Y-%m"
            )

            budget_id = set_budget(

                category=category,

                amount=amount,

                month=month

            )

            return jsonify({

                "message":
                    f"Budget set: ₹{amount:,.2f} for {category}.",

                "action":
                    "SET_BUDGET",

                "requires_confirmation":
                    False,

                "data": {

                    "id":
                        budget_id,

                    "category":
                        category,

                    "amount":
                        amount,

                    "month":
                        month

                }

            })

        # GOAL

        goal_pattern = re.search(

            r"""
            (?:
                create
                |
                set
                |
                add
            )
            \s+
            (.+?)
            \s+
            goal
            \s+
            (?:of\s+|to\s+)?
            (?:₹|rs\.?|inr)?
            \s*
            ([\d,]+(?:\.\d+)?)
            $
            """,

            message.strip(),

            re.IGNORECASE |
            re.VERBOSE

        )

        if goal_pattern:

            name = goal_pattern.group(
                1
            ).strip()

            amount = clean_amount(
                goal_pattern.group(2)
            )

            goal_id = add_goal(

                name=name,

                target_amount=amount,

                current_amount=0,

                deadline=None

            )

            return jsonify({

                "message":
                    f"Goal created: {name} with a target of ₹{amount:,.2f}.",

                "action":
                    "SET_GOAL",

                "requires_confirmation":
                    False,

                "data": {

                    "id":
                        goal_id,

                    "name":
                        name,

                    "target_amount":
                        amount

                }

            })

        # DELETE

        delete_match = re.search(

            r"""
            (?:delete|remove)
            \s+
            (.+)
            """,

            message.strip(),

            re.IGNORECASE |
            re.VERBOSE

        )

        if delete_match:

            search_text = (
                delete_match
                .group(1)
                .lower()
                .strip()
            )

            transactions = get_transactions()

            matches = []

            for t in transactions:

                description = str(
                    t.get(
                        "description",
                        ""
                    )
                ).lower()

                if (
                    search_text in description
                    or any(
                        word in description
                        for word in search_text.split()
                    )
                ):

                    matches.append(t)

            if not matches:

                return jsonify({

                    "message":
                        "I couldn't find a matching transaction to delete.",

                    "action":
                        "NONE",

                    "requires_confirmation":
                        False

                })

            transaction = matches[0]

            confirmed = bool(
                data.get(
                    "confirm",
                    False
                )
            )

            if not confirmed:

                return jsonify({

                    "message":
                        f"Please confirm deletion of {transaction.get('description')} for ₹{abs(float(transaction.get('amount', 0))):,.2f}.",

                    "action":
                        "DELETE_TRANSACTION",

                    "requires_confirmation":
                        True,

                    "data":
                        transaction

                })

            delete_transaction(
                transaction.get("id")
            )

            return jsonify({

                "message":
                    "Transaction deleted successfully.",

                "action":
                    "DELETE_TRANSACTION",

                "requires_confirmation":
                    False,

                "data":
                    transaction

            })

        return jsonify(
            agent_query(
                message
            )
        )

    except Exception as e:

        print(
            "AGENT ERROR:",
            e
        )

        return jsonify({

            "message":
                "Something went wrong while processing your request.",

            "error":
                str(e),

            "action":
                "ERROR",

            "requires_confirmation":
                False

        }), 500


# ============================================================
# MONTHLY REPORT
# ============================================================

@app.route(
    "/api/monthly-report",
    methods=["GET"]
)
def monthly_report():

    try:

        transactions = get_transactions()

        requested_month = request.args.get(
            "month",
            date.today().strftime(
                "%Y-%m"
            )
        )

        month_transactions = [

            t for t in transactions

            if str(
                t.get(
                    "date",
                    ""
                )
            ).startswith(
                requested_month
            )

        ]

        income = 0

        expenses = 0

        categories = {}

        for transaction in month_transactions:

            amount = transaction_amount(
                transaction
            )

            transaction_type = (
                get_transaction_type(
                    transaction
                )
            )

            if (
                transaction_type == "income"
                or amount > 0
            ):

                income += abs(amount)

            else:

                expenses += abs(amount)

                category = str(
                    transaction.get(
                        "category",
                        "Other"
                    )
                )

                categories[category] = (

                    categories.get(
                        category,
                        0
                    )

                    + abs(amount)

                )

        savings = (
            income -
            expenses
        )

        savings_rate = (

            (savings / income) * 100

            if income > 0

            else 0

        )

        highest_category = None

        highest_category_amount = 0

        if categories:

            highest_category = max(
                categories,
                key=categories.get
            )

            highest_category_amount = (
                categories[
                    highest_category
                ]
            )

        # RECURRING

        recurring_total = 0

        try:

            dataframe = pd.DataFrame(
                month_transactions
            )

            if not dataframe.empty:

                analysis = analyze_dataframe(
                    dataframe
                )

                recurring = analysis.get(
                    "recurring",
                    []
                )

                for item in recurring:

                    if isinstance(
                        item,
                        dict
                    ):

                        recurring_total += abs(

                            float(
                                item.get(
                                    "amount",
                                    0
                                ) or 0
                            )

                        )

        except Exception:

            pass

        # BUDGETS

        budgets = get_budgets()

        budget_results = []

        for budget in budgets:

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
                ) or 0
            )

            actual = float(
                categories.get(
                    category,
                    0
                )
            )

            used_percent = (

                (
                    actual /
                    budget_amount
                ) * 100

                if budget_amount > 0

                else 0

            )

            budget_results.append({

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

                "used_percent":
                    round(
                        used_percent,
                        1
                    )

            })

        # GOALS

        goals = get_goals()

        goal_results = []

        for goal in goals:

            target = float(
                goal.get(
                    "target_amount",
                    0
                ) or 0
            )

            current = float(
                goal.get(
                    "current_amount",
                    0
                ) or 0
            )

            progress = (

                (
                    current /
                    target
                ) * 100

                if target > 0

                else 0

            )

            goal_results.append({

                "name":
                    goal.get(
                        "name",
                        "Goal"
                    ),

                "target":
                    target,

                "current":
                    current,

                "progress":
                    round(
                        min(
                            progress,
                            100
                        ),
                        1
                    )

            })

        # INSIGHTS

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
                    "Your savings rate is relatively low this month."
                )

        if highest_category:

            insights.append(

                f"{highest_category} was your highest spending category at ₹{highest_category_amount:,.0f}."

            )

        if (
            expenses > income
            and income > 0
        ):

            insights.append(
                "Your recorded expenses were higher than your income this month."
            )

        return jsonify({

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

            "highest_category":
                highest_category,

            "highest_category_amount":
                round(
                    highest_category_amount,
                    2
                ),

            "recurring_total":
                round(
                    recurring_total,
                    2
                ),

            "budgets":
                budget_results,

            "goals":
                goal_results,

            "insights":
                insights

        })

    except Exception as e:

        print(
            "MONTHLY REPORT ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# MONTHLY REPORT PDF
# ============================================================

@app.route(
    "/api/monthly-report/pdf",
    methods=["GET"]
)
def monthly_report_pdf():

    try:

        requested_month = request.args.get(
            "month",
            date.today().strftime(
                "%Y-%m"
            )
        )

        transactions = get_transactions()

        month_transactions = [

            t for t in transactions

            if str(
                t.get(
                    "date",
                    ""
                )
            ).startswith(
                requested_month
            )

        ]

        income = 0

        expenses = 0

        categories = {}

        for transaction in month_transactions:

            amount = transaction_amount(
                transaction
            )

            transaction_type = (
                get_transaction_type(
                    transaction
                )
            )

            if (
                transaction_type == "income"
                or amount > 0
            ):

                income += abs(
                    amount
                )

            else:

                expenses += abs(
                    amount
                )

                category = str(
                    transaction.get(
                        "category",
                        "Other"
                    )
                )

                categories[category] = (

                    categories.get(
                        category,
                        0
                    )

                    + abs(amount)

                )

        savings = (
            income -
            expenses
        )

        savings_rate = (

            (savings / income) * 100

            if income > 0

            else 0

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

            parent=styles["Title"],

            fontSize=24,

            alignment=TA_CENTER,

            spaceAfter=8

        )

        subtitle_style = ParagraphStyle(

            "FinPilotSubtitle",

            parent=styles["Normal"],

            fontSize=11,

            alignment=TA_CENTER,

            textColor=colors.grey,

            spaceAfter=20

        )

        heading_style = ParagraphStyle(

            "SectionHeading",

            parent=styles["Heading2"],

            fontSize=15,

            spaceBefore=15,

            spaceAfter=10

        )

        normal_style = ParagraphStyle(

            "NormalText",

            parent=styles["Normal"],

            fontSize=10,

            leading=14

        )

        story = []

        # TITLE

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
                f"Report Period: {requested_month}",
                normal_style
            )
        )

        story.append(
            Spacer(
                1,
                15
            )
        )

        # SUMMARY

        summary_data = [

            [
                "Income",
                "Expenses",
                "Savings",
                "Savings Rate"
            ],

            [
                f"Rs. {income:,.2f}",
                f"Rs. {expenses:,.2f}",
                f"Rs. {savings:,.2f}",
                f"{savings_rate:.1f}%"
            ]

        ]

        summary_table = Table(
            summary_data,
            colWidths=[
                125,
                125,
                125,
                125
            ]
        )

        summary_table.setStyle(
            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#111827")
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
                    "BACKGROUND",
                    (0, 1),
                    (-1, 1),
                    colors.whitesmoke
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
            summary_table
        )

        # CATEGORY BREAKDOWN

        story.append(
            Paragraph(
                "Spending Breakdown",
                heading_style
            )
        )

        category_data = [

            [
                "Category",
                "Amount",
                "Percentage"
            ]

        ]

        total_category_spending = sum(
            categories.values()
        )

        sorted_categories = sorted(

            categories.items(),

            key=lambda x: x[1],

            reverse=True

        )

        for category, amount in sorted_categories:

            percentage = (

                (
                    amount /
                    total_category_spending
                ) * 100

                if total_category_spending > 0

                else 0

            )

            category_data.append([

                str(category),

                f"Rs. {amount:,.2f}",

                f"{percentage:.1f}%"

            ])

        if len(category_data) == 1:

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
                    colors.HexColor("#111827")
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

        # INSIGHTS

        story.append(
            Paragraph(
                "FinPilot Insights",
                heading_style
            )
        )

        insights = []

        if income > 0:

            if savings_rate >= 30:

                insights.append(
                    "Your recorded savings rate was above 30% this month."
                )

            elif savings_rate >= 15:

                insights.append(
                    "You maintained a positive savings rate this month."
                )

            else:

                insights.append(
                    "Your recorded savings rate was relatively low this month."
                )

        if categories:

            highest_category = max(
                categories,
                key=categories.get
            )

            insights.append(

                f"{highest_category} was your highest spending category at Rs. {categories[highest_category]:,.2f}."

            )

        if (
            expenses > income
            and income > 0
        ):

            insights.append(
                "Your recorded expenses were higher than your income this month."
            )

        if not insights:

            insights.append(
                "There are not enough recorded transactions to generate detailed insights."
            )

        for insight in insights:

            story.append(
                Paragraph(
                    "• " + insight,
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
                f"Total transactions recorded: {len(month_transactions)}",
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
                "Generated by FinPilot Personal Finance Decision Support Agent.",
                subtitle_style
            )
        )

        document.build(
            story
        )

        buffer.seek(0)

        return send_file(

            buffer,

            mimetype="application/pdf",

            as_attachment=True,

            download_name=
                f"FinPilot_Report_{requested_month}.pdf"

        )

    except Exception as e:

        print(
            "PDF EXPORT ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# HEALTH CHECK
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

@app.errorhandler(404)
def not_found(error):

    return jsonify({

        "error":
            "Route not found.",

        "message":
            "The requested page or API route does not exist."

    }), 404


@app.errorhandler(500)
def internal_error(error):

    return jsonify({

        "error":
            "Internal server error."

    }), 500


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(

        host="127.0.0.1",

        port=5000,

        debug=True

    )
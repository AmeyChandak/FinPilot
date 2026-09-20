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
from datetime import (
    datetime,
    date,
    timedelta
)
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

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

DATA_FOLDER = os.path.join(
    BASE_DIR,
    "data"
)

DEMO_FILE = os.path.join(
    DATA_FOLDER,
    "demo_transactions.csv"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config[
    "UPLOAD_FOLDER"
] = UPLOAD_FOLDER

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


# ============================================================
# NO CACHE FOR API
# ============================================================

@app.after_request
def no_cache_api(response):

    if (
        request.path.startswith("/api/")
        or request.path == "/upload"
        or request.path.startswith("/agent/")
    ):

        response.headers[
            "Cache-Control"
        ] = (
            "no-store, "
            "no-cache, "
            "must-revalidate, "
            "max-age=0"
        )

        response.headers[
            "Pragma"
        ] = "no-cache"

        response.headers[
            "Expires"
        ] = "0"

    return response


# ============================================================
# GENERAL HELPERS
# ============================================================

def allowed_file(filename):

    return (
        "." in filename
        and
        filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


def clean_amount(value):

    if value is None:
        return 0.0

    value = str(
        value
    )

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

        return float(
            value
        )

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

    ).strip().lower()


def normalize_db_transactions(
    transactions
):

    normalized = []

    for transaction in transactions:

        amount = abs(
            transaction_amount(
                transaction
            )
        )

        tx_type = get_transaction_type(
            transaction
        )

        if tx_type == "expense":

            signed_amount = -amount

        else:

            signed_amount = amount

        normalized.append({

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
                signed_amount,

            "Category":
                transaction.get(
                    "category",
                    "Other"
                )

        })

    return normalized


def parse_date_from_text(text):

    text = str(
        text
    ).lower()

    today = date.today()

    if "today" in text:

        return today.isoformat()

    if "yesterday" in text:

        return (
            today -
            timedelta(days=1)
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

        value = match.group(
            0
        )

        try:

            if "/" in value:

                dt = datetime.strptime(
                    value,
                    "%d/%m/%Y"
                )

                return dt.date().isoformat()

            if (
                len(value) == 10
                and
                value[4] == "-"
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


def calculate_from_transactions(
    transactions
):

    income = 0.0

    expenses = 0.0

    for transaction in transactions:

        amount = abs(
            transaction_amount(
                transaction
            )
        )

        tx_type = get_transaction_type(
            transaction
        )

        if (
            tx_type == "income"
            or transaction.get(
                "amount",
                0
            ) > 0
            and tx_type != "expense"
        ):

            income += amount

        else:

            expenses += amount

    savings = (
        income -
        expenses
    )

    savings_rate = (

        (
            savings /
            income
        ) * 100

        if income > 0

        else 0

    )

    return (
        income,
        expenses,
        savings,
        savings_rate
    )


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

        filename = secure_filename(
            file.filename
        )

        if not filename:

            return jsonify({

                "success":
                    False,

                "error":
                    "Invalid file name."

            }), 400

        filepath = os.path.join(

            app.config[
                "UPLOAD_FOLDER"
            ],

            filename

        )

        os.makedirs(

            app.config[
                "UPLOAD_FOLDER"
            ],

            exist_ok=True

        )

        file.save(
            filepath
        )

        if not os.path.exists(
            filepath
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Uploaded file could not be saved."

            }), 500

        extension = filename.rsplit(
            ".",
            1
        )[1].lower()

        transactions = []

        analysis = None

        save_transactions = []


        # ====================================================
        # CSV / EXCEL
        # ====================================================

        if extension in {
            "csv",
            "xlsx",
            "xls"
        }:

            analysis = analyze_file(
                filepath
            )

            if isinstance(
                analysis,
                dict
            ):

                transactions = analysis.get(
                    "transactions",
                    []
                )

                for transaction in transactions:

                    amount = clean_amount(
                        transaction.get(
                            "Amount",
                            0
                        )
                    )

                    transaction_type = (

                        "income"

                        if amount > 0

                        else "expense"

                    )

                    save_transactions.append({

                        "date":
                            str(
                                transaction.get(
                                    "Date",
                                    ""
                                )
                            ),

                        "description":
                            str(
                                transaction.get(
                                    "Description",
                                    ""
                                )
                            ).strip(),

                        "amount":
                            amount,

                        "category":
                            transaction.get(
                                "Category",
                                "Other"
                            ),

                        "type":
                            transaction_type

                    })


        # ====================================================
        # PDF
        # ====================================================

        elif extension == "pdf":

            text = extract_pdf_text(
                filepath
            )

            extracted = extract_from_text(
                text
            )

            transactions = extracted.get(
                "transactions",
                []
            )

            if transactions:

                dataframe = (
                    ai_transactions_to_dataframe(
                        transactions
                    )
                )

                analysis = (
                    analyze_dataframe(
                        dataframe
                    )
                )

                for row in dataframe.to_dict(
                    orient="records"
                ):

                    amount = clean_amount(
                        row.get(
                            "Amount",
                            0
                        )
                    )

                    save_transactions.append({

                        "date":
                            str(
                                row.get(
                                    "Date",
                                    ""
                                )
                            ),

                        "description":
                            str(
                                row.get(
                                    "Description",
                                    ""
                                )
                            ).strip(),

                        "amount":
                            amount,

                        "category":
                            row.get(
                                "Category",
                                "Other"
                            ),

                        "type":
                            (
                                "income"
                                if amount > 0
                                else "expense"
                            )

                    })


        # ====================================================
        # DOCX
        # ====================================================

        elif extension == "docx":

            text = extract_docx_text(
                filepath
            )

            extracted = extract_from_text(
                text
            )

            transactions = extracted.get(
                "transactions",
                []
            )

            if transactions:

                dataframe = (
                    ai_transactions_to_dataframe(
                        transactions
                    )
                )

                analysis = (
                    analyze_dataframe(
                        dataframe
                    )
                )

                for row in dataframe.to_dict(
                    orient="records"
                ):

                    amount = clean_amount(
                        row.get(
                            "Amount",
                            0
                        )
                    )

                    save_transactions.append({

                        "date":
                            str(
                                row.get(
                                    "Date",
                                    ""
                                )
                            ),

                        "description":
                            str(
                                row.get(
                                    "Description",
                                    ""
                                )
                            ).strip(),

                        "amount":
                            amount,

                        "category":
                            row.get(
                                "Category",
                                "Other"
                            ),

                        "type":
                            (
                                "income"
                                if amount > 0
                                else "expense"
                            )

                    })


        # ====================================================
        # IMAGE
        # ====================================================

        elif extension in {
            "png",
            "jpg",
            "jpeg"
        }:

            extracted = extract_from_image(
                filepath
            )

            transactions = extracted.get(
                "transactions",
                []
            )

            if transactions:

                dataframe = (
                    ai_transactions_to_dataframe(
                        transactions
                    )
                )

                analysis = (
                    analyze_dataframe(
                        dataframe
                    )
                )

                for row in dataframe.to_dict(
                    orient="records"
                ):

                    amount = clean_amount(
                        row.get(
                            "Amount",
                            0
                        )
                    )

                    save_transactions.append({

                        "date":
                            str(
                                row.get(
                                    "Date",
                                    ""
                                )
                            ),

                        "description":
                            str(
                                row.get(
                                    "Description",
                                    ""
                                )
                            ).strip(),

                        "amount":
                            amount,

                        "category":
                            row.get(
                                "Category",
                                "Other"
                            ),

                        "type":
                            (
                                "income"
                                if amount > 0
                                else "expense"
                            )

                    })


        # ====================================================
        # SAVE TO DATABASE
        # ====================================================

        added_count = 0

        skipped_count = 0

        if save_transactions:

            try:

                result = add_transactions(
                    save_transactions
                )

                if isinstance(
                    result,
                    dict
                ):

                    added_count = int(
                        result.get(
                            "added",
                            0
                        )
                    )

                    skipped_count = int(
                        result.get(
                            "skipped",
                            0
                        )
                    )

            except Exception as save_error:

                print(
                    "ADD TRANSACTIONS ERROR:",
                    repr(save_error)
                )

                # Do not hide successful file analysis.
                added_count = 0
                skipped_count = 0


        # ====================================================
        # EMPTY ANALYSIS FALLBACK
        # ====================================================

        if analysis is None:

            analysis = {

                "income":
                    0,

                "expenses":
                    0,

                "savings":
                    0,

                "savings_rate":
                    0,

                "transaction_count":
                    len(
                        transactions
                    ),

                "category_spending":
                    {},

                "recurring":
                    [],

                "unusual":
                    [],

                "monthly_spending":
                    {},

                "transactions":
                    transactions

            }


        # ====================================================
        # RESPONSE
        # ====================================================

        return jsonify({

            "success":
                True,

            "message":
                f"Successfully analyzed {len(transactions)} transaction(s).",

            "filename":
                filename,

            "added":
                added_count,

            "skipped":
                skipped_count,

            "analysis":
                analysis,

            # Also expose values at top level.
            # This makes the API compatible with
            # older frontend versions.

            "income":
                analysis.get(
                    "income",
                    0
                ),

            "expenses":
                analysis.get(
                    "expenses",
                    0
                ),

            "savings":
                analysis.get(
                    "savings",
                    0
                ),

            "savings_rate":
                analysis.get(
                    "savings_rate",
                    0
                ),

            "transaction_count":
                analysis.get(
                    "transaction_count",
                    len(transactions)
                ),

            "category_spending":
                analysis.get(
                    "category_spending",
                    {}
                ),

            "recurring":
                analysis.get(
                    "recurring",
                    []
                ),

            "unusual":
                analysis.get(
                    "unusual",
                    []
                ),

            "monthly_spending":
                analysis.get(
                    "monthly_spending",
                    {}
                ),

            "transactions":
                analysis.get(
                    "transactions",
                    transactions
                )

        })


    except Exception as e:

        print(
            "UPLOAD ERROR:",
            repr(e)
        )

        return jsonify({

            "success":
                False,

            "error":
                str(e)

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

                "insights":
                    []

            })


        normalized = (
            normalize_db_transactions(
                transactions
            )
        )


        dataframe = pd.DataFrame(
            normalized
        )


        analysis = analyze_dataframe(
            dataframe
        )


        # Use database records for frontend transaction table.

        analysis[
            "transactions"
        ] = transactions


        analysis[
            "transaction_count"
        ] = len(
            transactions
        )


        income = float(
            analysis.get(
                "income",
                0
            ) or 0
        )

        expenses = float(
            analysis.get(
                "expenses",
                0
            ) or 0
        )

        savings = float(
            analysis.get(
                "savings",
                0
            ) or 0
        )

        savings_rate = float(
            analysis.get(
                "savings_rate",
                0
            ) or 0
        )


        insights = []


        if income > 0:

            if savings_rate >= 30:

                insights.append(
                    "Your recorded savings rate is above 30%."
                )

            elif savings_rate >= 15:

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


        category_spending = (
            analysis.get(
                "category_spending",
                {}
            ) or {}
        )


        if category_spending:

            highest_category = max(

                category_spending,

                key=category_spending.get

            )

            highest_amount = (
                category_spending[
                    highest_category
                ]
            )

            insights.append(

                f"{highest_category} is your highest spending category at ₹{highest_amount:,.0f}."

            )


        analysis[
            "insights"
        ] = insights


        # Recent transactions.

        analysis[
            "recent_transactions"
        ] = transactions[
            :10
        ]


        return jsonify(
            analysis
        )


    except Exception as e:

        print(
            "DASHBOARD ERROR:",
            repr(e)
        )

        return jsonify({

            "error":
                str(e)

        }), 500


# ============================================================
# TRANSACTIONS - GET
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

            "error":
                str(e)

        }), 500


# ============================================================
# TRANSACTIONS - CREATE
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
            or {}
        )


        description = str(

            data.get(
                "description",
                ""
            )

        ).strip()


        if not description:

            return jsonify({

                "success":
                    False,

                "error":
                    "Description is required."

            }), 400


        # ====================================================
        # IMPORTANT FIX
        # ====================================================
        #
        # Always convert amount to POSITIVE magnitude.
        #
        # Example:
        # Amount = 500
        # Type = expense
        #
        # Database receives:
        # amount = 500
        # type   = expense
        #
        # Dashboard later converts it to -500 for analysis.
        #
        # This prevents:
        # "Amount must be greater than zero."
        #
        amount = abs(

            clean_amount(

                data.get(
                    "amount",
                    0
                )

            )

        )


        if amount <= 0:

            return jsonify({

                "success":
                    False,

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

        ).strip().lower()


        if transaction_type not in {

            "income",
            "expense"

        }:

            transaction_type = (
                "expense"
            )


        transaction_date = str(

            data.get(
                "date",
                ""
            )

        ).strip()


        if not transaction_date:

            transaction_date = (
                date.today()
                .isoformat()
            )


        category = str(

            data.get(
                "category",
                ""
            )

        ).strip()


        if not category:

            category = categorize(
                description
            )


        transaction_id = add_transaction(

            date=
                transaction_date,

            description=
                description,

            amount=
                amount,

            category=
                category,

            transaction_type=
                transaction_type,

            source=
                data.get(
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
                transaction_id

        })


    except Exception as e:

        print(
            "CREATE TRANSACTION ERROR:",
            repr(e)
        )

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# TRANSACTION - GET ONE
# ============================================================

@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["GET"]
)
def get_single_transaction(
    transaction_id
):

    try:

        transaction = (
            get_transaction(
                transaction_id
            )
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

            "error":
                str(e)

        }), 500


# ============================================================
# TRANSACTION - UPDATE
# ============================================================

@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["PUT"]
)
def edit_transaction(
    transaction_id
):

    try:

        existing = (
            get_transaction(
                transaction_id
            )
        )


        if not existing:

            return jsonify({

                "success":
                    False,

                "error":
                    "Transaction not found."

            }), 404


        data = (
            request.get_json(
                silent=True
            )
            or {}
        )


        transaction_date = str(

            data.get(

                "date",

                existing.get(
                    "date",
                    date.today().isoformat()
                )

            )

        ).strip()


        description = str(

            data.get(

                "description",

                existing.get(
                    "description",
                    ""
                )

            )

        ).strip()


        if not description:

            return jsonify({

                "success":
                    False,

                "error":
                    "Description is required."

            }), 400


        # IMPORTANT FIX:
        # Edit also receives positive magnitude.

        amount = abs(

            clean_amount(

                data.get(

                    "amount",

                    existing.get(
                        "amount",
                        0
                    )

                )

            )

        )


        if amount <= 0:

            return jsonify({

                "success":
                    False,

                "error":
                    "Amount must be greater than zero."

            }), 400


        category = str(

            data.get(

                "category",

                existing.get(
                    "category",
                    ""
                )

            )

        ).strip()


        if not category:

            category = categorize(
                description
            )


        transaction_type = str(

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

        ).strip().lower()


        if transaction_type not in {

            "income",
            "expense"

        }:

            transaction_type = (
                "expense"
            )


        result = update_transaction(

            transaction_id,

            date=
                transaction_date,

            description=
                description,

            amount=
                amount,

            category=
                category,

            transaction_type=
                transaction_type

        )


        return jsonify({

            "success":
                True,

            "message":
                "Transaction updated successfully.",

            "result":
                result

        })


    except Exception as e:

        print(
            "UPDATE TRANSACTION ERROR:",
            repr(e)
        )

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# TRANSACTION - DELETE
# ============================================================

@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["DELETE"]
)
def remove_transaction(
    transaction_id
):

    try:

        existing = (
            get_transaction(
                transaction_id
            )
        )


        if not existing:

            return jsonify({

                "success":
                    False,

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


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# BUDGETS - GET
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

            "error":
                str(e)

        }), 500


# ============================================================
# BUDGET - CREATE
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
            or {}
        )


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


        month = str(

            data.get(

                "month",

                date.today()
                .strftime(
                    "%Y-%m"
                )

            )

        )


        budget_id = set_budget(

            category=
                category,

            amount=
                amount,

            month=
                month

        )


        return jsonify({

            "success":
                True,

            "message":
                "Budget saved successfully.",

            "id":
                budget_id

        })


    except Exception as e:

        print(
            "BUDGET ERROR:",
            repr(e)
        )

        return jsonify({

            "error":
                str(e)

        }), 500


# ============================================================
# BUDGET - DELETE
# ============================================================

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

            "success":
                True,

            "message":
                "Budget deleted successfully."

        })


    except Exception as e:

        return jsonify({

            "error":
                str(e)

        }), 500


# ============================================================
# GOALS - GET
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

            "error":
                str(e)

        }), 500


# ============================================================
# GOAL - CREATE
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
            or {}
        )


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

            name=
                name,

            target_amount=
                target_amount,

            current_amount=
                current_amount,

            deadline=
                deadline

        )


        return jsonify({

            "success":
                True,

            "message":
                "Goal created successfully.",

            "id":
                goal_id

        })


    except Exception as e:

        print(
            "CREATE GOAL ERROR:",
            repr(e)
        )

        return jsonify({

            "error":
                str(e)

        }), 500


# ============================================================
# GOAL - GET ONE
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


    except Exception as e:

        return jsonify({

            "error":
                str(e)

        }), 500


# ============================================================
# GOAL - UPDATE
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
            or {}
        )


        name = str(

            data.get(

                "name",

                existing.get(
                    "name",
                    "Goal"
                )

            )

        ).strip()


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

            existing.get(
                "deadline"
            )

        )


        update_goal(

            goal_id,

            name=
                name,

            target_amount=
                target_amount,

            current_amount=
                current_amount,

            deadline=
                deadline

        )


        return jsonify({

            "success":
                True,

            "message":
                "Goal updated successfully."

        })


    except Exception as e:

        return jsonify({

            "error":
                str(e)

        }), 500


# ============================================================
# GOAL - DELETE
# ============================================================

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

            "success":
                True,

            "message":
                "Goal deleted successfully."

        })


    except Exception as e:

        return jsonify({

            "error":
                str(e)

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


        income = 0.0

        expenses = 0.0


        for transaction in transactions:

            amount = abs(
                transaction_amount(
                    transaction
                )
            )

            tx_type = get_transaction_type(
                transaction
            )


            if tx_type == "income":

                income += amount

            else:

                expenses += amount


        monthly_savings = max(

            income -
            expenses,

            0

        )


        results = []


        for goal in goals:

            target = float(

                goal.get(
                    "target_amount",
                    0
                )
                or 0

            )


            current = float(

                goal.get(
                    "current_amount",
                    0
                )
                or 0

            )


            remaining = max(

                target -
                current,

                0

            )


            progress = (

                (
                    current /
                    target
                ) * 100

                if target > 0

                else 0

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
                        min(
                            progress,
                            100
                        ),
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
                        if months_needed is not None
                        else None
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


    except Exception as e:

        print(
            "GOAL IMPACT ERROR:",
            repr(e)
        )

        return jsonify({

            "error":
                str(e)

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


        actual_by_category = {}


        for transaction in transactions:

            amount = abs(
                transaction_amount(
                    transaction
                )
            )

            tx_type = get_transaction_type(
                transaction
            )


            if tx_type == "income":
                continue


            category = str(

                transaction.get(
                    "category",
                    "Other"
                )

            )


            actual_by_category[
                category
            ] = (

                actual_by_category.get(
                    category,
                    0
                )
                +
                amount

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
                    0
                )
                or 0

            )


            actual = float(

                actual_by_category.get(
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


            remaining = (
                budget_amount -
                actual
            )


            if used_percent > 100:

                status = "over"

            elif used_percent >= 80:

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
            repr(e)
        )

        return jsonify({

            "error":
                str(e)

        }), 500


# ============================================================
# SIMPLE LOCAL AGENT
# ============================================================

def agent_query(
    message
):

    text = str(
        message
    ).strip()

    lower = text.lower()


    transactions = get_transactions()


    income, expenses, savings, savings_rate = (
        calculate_from_transactions(
            transactions
        )
    )


    category_totals = {}


    for transaction in transactions:

        tx_type = get_transaction_type(
            transaction
        )

        if tx_type == "income":
            continue


        amount = abs(
            transaction_amount(
                transaction
            )
        )


        category = str(

            transaction.get(
                "category",
                "Other"
            )

        )


        category_totals[
            category
        ] = (

            category_totals.get(
                category,
                0
            )
            +
            amount

        )


    # --------------------------------------------------------
    # TOTAL SPENDING
    # --------------------------------------------------------

    if (
        "how much did i spend" in lower
        or
        "total spending" in lower
        or
        "total expense" in lower
        or
        "how much have i spent" in lower
    ):

        return {

            "message":
                f"You have recorded ₹{expenses:,.2f} in expenses.",

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # SAVINGS
    # --------------------------------------------------------

    if (
        "how much did i save" in lower
        or
        "my savings" in lower
        or
        "how much have i saved" in lower
    ):

        return {

            "message":
                f"Your recorded savings are ₹{savings:,.2f}.",

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # HIGHEST CATEGORY
    # --------------------------------------------------------

    if (
        "where am i spending the most" in lower
        or
        "highest spending" in lower
        or
        "biggest spending" in lower
    ):

        if category_totals:

            category = max(

                category_totals,

                key=category_totals.get

            )

            amount = category_totals[
                category
            ]

            return {

                "message":
                    f"Your highest spending category is {category} at ₹{amount:,.2f}.",

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }

        return {

            "message":
                "There is not enough spending data yet.",

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # RECURRING
    # --------------------------------------------------------

    if (
        "recurring" in lower
        or
        "subscription" in lower
    ):

        dataframe = pd.DataFrame(
            normalize_db_transactions(
                transactions
            )
        )


        if dataframe.empty:

            return {

                "message":
                    "No transactions available.",

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }


        analysis = analyze_dataframe(
            dataframe
        )


        recurring = analysis.get(
            "recurring",
            []
        )


        if not recurring:

            return {

                "message":
                    "No recurring payments were detected.",

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }


        lines = []


        for item in recurring:

            lines.append(

                f"{item.get('description', 'Payment')}: "
                f"₹{float(item.get('amount', 0) or 0):,.2f}"

            )


        return {

            "message":
                "Recurring payments:\n" +
                "\n".join(
                    lines
                ),

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # UNUSUAL
    # --------------------------------------------------------

    if (
        "unusual spending" in lower
        or
        "unusual expense" in lower
    ):

        dataframe = pd.DataFrame(

            normalize_db_transactions(
                transactions
            )

        )


        if dataframe.empty:

            return {

                "message":
                    "No transactions available.",

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }


        analysis = analyze_dataframe(
            dataframe
        )


        unusual = analysis.get(
            "unusual",
            []
        )


        if not unusual:

            return {

                "message":
                    "No unusual spending was detected.",

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            }


        lines = []


        for item in unusual:

            lines.append(

                f"{item.get('description', 'Transaction')}: "
                f"₹{float(item.get('amount', 0) or 0):,.2f}"

            )


        return {

            "message":
                "Unusual spending:\n" +
                "\n".join(
                    lines
                ),

            "action":
                "NONE",

            "requires_confirmation":
                False

        }


    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    return {

        "message":

            "I can help with spending, savings, recurring payments, "
            "unusual spending, budgets and goals.",

        "action":
            "NONE",

        "requires_confirmation":
            False

    }


# ============================================================
# AGENT API
# ============================================================

@app.route(
    "/api/agent",
    methods=["POST"]
)
def agent_api():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
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
                    "Please enter a question.",

                "action":
                    "NONE",

                "requires_confirmation":
                    False

            })


        return jsonify(
            agent_query(
                message
            )
        )


    except Exception as e:

        return jsonify({

            "message":
                "Something went wrong.",

            "error":
                str(e),

            "action":
                "ERROR",

            "requires_confirmation":
                False

        }), 500


# ============================================================
# AGENT CHAT COMPATIBILITY
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
            or {}
        )


        message = str(

            data.get(
                "message",
                ""
            )

        ).strip()


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


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# AGENT ANALYZE COMPATIBILITY
# ============================================================

@app.route(
    "/agent/analyze",
    methods=["POST"]
)
def agent_analyze():

    try:

        transactions = get_transactions()

        income, expenses, savings, savings_rate = (
            calculate_from_transactions(
                transactions
            )
        )


        category_totals = {}


        for transaction in transactions:

            if (
                get_transaction_type(
                    transaction
                )
                ==
                "income"
            ):

                continue


            category = str(

                transaction.get(
                    "category",
                    "Other"
                )

            )


            amount = abs(
                transaction_amount(
                    transaction
                )
            )


            category_totals[
                category
            ] = (

                category_totals.get(
                    category,
                    0
                )
                +
                amount

            )


        insights = []


        if income > 0:

            insights.append(

                f"Income recorded: ₹{income:,.0f}."

            )


        insights.append(

            f"Expenses recorded: ₹{expenses:,.0f}."

        )


        insights.append(

            f"Savings recorded: ₹{savings:,.0f}."

        )


        if category_totals:

            highest_category = max(

                category_totals,

                key=category_totals.get

            )

            insights.append(

                f"{highest_category} is the highest spending category."

            )


        report = {

            "headline":
                "FinPilot financial analysis is complete.",

            "summary":
                (
                    f"You recorded ₹{income:,.0f} income, "
                    f"₹{expenses:,.0f} expenses and "
                    f"₹{savings:,.0f} savings."
                ),

            "key_insights":
                insights

        }


        return jsonify({

            "success":
                True,

            "report":
                report,

            "message":
                report["summary"],

            "tools_used":
                [
                    "transaction_analysis",
                    "category_analysis",
                    "cashflow_analysis"
                ]

        })


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

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

        requested_month = request.args.get(

            "month",

            date.today().strftime(
                "%Y-%m"
            )

        )


        transactions = get_transactions()


        month_transactions = [

            transaction

            for transaction in transactions

            if str(
                transaction.get(
                    "date",
                    ""
                )
            ).startswith(
                requested_month
            )

        ]


        income = 0.0

        expenses = 0.0

        categories = {}


        for transaction in month_transactions:

            amount = abs(
                transaction_amount(
                    transaction
                )
            )

            tx_type = get_transaction_type(
                transaction
            )


            if tx_type == "income":

                income += amount

            else:

                expenses += amount


                category = str(

                    transaction.get(
                        "category",
                        "Other"
                    )

                )


                categories[
                    category
                ] = (

                    categories.get(
                        category,
                        0
                    )
                    +
                    amount

                )


        savings = (
            income -
            expenses
        )


        savings_rate = (

            (
                savings /
                income
            ) * 100

            if income > 0

            else 0

        )


        insights = []


        if income > 0:

            if savings_rate >= 30:

                insights.append(

                    "Your recorded savings rate is above 30%."

                )

            elif savings_rate >= 15:

                insights.append(

                    "You maintained a positive savings rate."

                )

            else:

                insights.append(

                    "Your recorded savings rate is relatively low."

                )


        if categories:

            highest_category = max(

                categories,

                key=categories.get

            )

            insights.append(

                f"{highest_category} was your highest spending category at "
                f"₹{categories[highest_category]:,.2f}."

            )


        if (
            expenses > income
            and income > 0
        ):

            insights.append(

                "Recorded expenses were higher than recorded income."

            )


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
                )
                or 0

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


        goals = get_goals()

        goal_results = []


        for goal in goals:

            target = float(

                goal.get(
                    "target_amount",
                    0
                )
                or 0

            )


            current = float(

                goal.get(
                    "current_amount",
                    0
                )
                or 0

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


        return jsonify({

            "month":
                requested_month,

            "transaction_count":
                len(
                    month_transactions
                ),

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
            repr(e)
        )

        return jsonify({

            "error":
                str(e)

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

            transaction

            for transaction in transactions

            if str(
                transaction.get(
                    "date",
                    ""
                )
            ).startswith(
                requested_month
            )

        ]


        income = 0.0

        expenses = 0.0

        categories = {}


        for transaction in month_transactions:

            amount = abs(
                transaction_amount(
                    transaction
                )
            )


            tx_type = get_transaction_type(
                transaction
            )


            if tx_type == "income":

                income += amount

            else:

                expenses += amount

                category = str(

                    transaction.get(
                        "category",
                        "Other"
                    )

                )


                categories[
                    category
                ] = (

                    categories.get(
                        category,
                        0
                    )
                    +
                    amount

                )


        savings = (
            income -
            expenses
        )


        savings_rate = (

            (
                savings /
                income
            ) * 100

            if income > 0

            else 0

        )


        buffer = BytesIO()


        pdf = SimpleDocTemplate(

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

            parent=
                styles["Title"],

            fontSize=
                24,

            alignment=
                TA_CENTER,

            spaceAfter=
                8

        )


        subtitle_style = ParagraphStyle(

            "FinPilotSubtitle",

            parent=
                styles["Normal"],

            fontSize=
                11,

            alignment=
                TA_CENTER,

            textColor=
                colors.grey,

            spaceAfter=
                15

        )


        heading_style = ParagraphStyle(

            "SectionHeading",

            parent=
                styles["Heading2"],

            fontSize=
                15,

            spaceBefore=
                15,

            spaceAfter=
                10

        )


        normal_style = ParagraphStyle(

            "NormalText",

            parent=
                styles["Normal"],

            fontSize=
                10,

            leading=
                14

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
            summary_table
        )


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


        total_spending = sum(
            categories.values()
        )


        sorted_categories = sorted(

            categories.items(),

            key=
                lambda item:
                    item[1],

            reverse=
                True

        )


        for category, amount in sorted_categories:

            percentage = (

                (
                    amount /
                    total_spending
                ) * 100

                if total_spending > 0

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


        story.append(

            Paragraph(

                "FinPilot Insights",

                heading_style

            )

        )


        insights = []


        if income > 0:

            insights.append(

                f"Income recorded for the month: "
                f"Rs. {income:,.2f}."

            )


        insights.append(

            f"Expenses recorded for the month: "
            f"Rs. {expenses:,.2f}."

        )


        insights.append(

            f"Savings recorded for the month: "
            f"Rs. {savings:,.2f}."

        )


        if categories:

            highest_category = max(

                categories,

                key=
                    categories.get

            )


            insights.append(

                f"{highest_category} was the highest spending category."

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

                f"Total transactions recorded: "
                f"{len(month_transactions)}",

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


        pdf.build(
            story
        )


        buffer.seek(
            0
        )


        return send_file(

            buffer,

            mimetype=
                "application/pdf",

            as_attachment=
                True,

            download_name=
                (
                    f"FinPilot_Report_"
                    f"{requested_month}.pdf"
                )

        )


    except Exception as e:

        print(
            "PDF ERROR:",
            repr(e)
        )

        return jsonify({

            "error":
                str(e)

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

        "service":
            "FinPilot"

    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({

            "error":
                "Route not found."

        }), 404

    return (
        "Page not found.",
        404
    )


@app.errorhandler(500)
def internal_error(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({

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

        host=
            "127.0.0.1",

        port=
            5000,

        debug=
            True

    )
import sqlite3
from datetime import datetime
import hashlib
import math


# ============================================================
# DATABASE CONFIG
# ============================================================

DATABASE = "finance.db"


# ============================================================
# CONNECTION
# ============================================================

def get_connection():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_amount(value):

    if value is None:
        return 0.0

    try:

        if isinstance(
            value,
            float
        ) and math.isnan(value):

            return 0.0

    except Exception:
        pass

    try:

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

        if not value:
            return 0.0

        return float(value)

    except Exception:

        return 0.0


def normalize_date(value):

    if value is None:

        return ""

    # Pandas Timestamp / datetime / date
    try:

        if hasattr(
            value,
            "strftime"
        ):

            return value.strftime(
                "%Y-%m-%d"
            )

    except Exception:
        pass

    value = str(value).strip()

    if not value:
        return ""

    # Already ISO date
    try:

        parsed = datetime.strptime(
            value[:10],
            "%Y-%m-%d"
        )

        return parsed.strftime(
            "%Y-%m-%d"
        )

    except Exception:
        pass

    # DD/MM/YYYY
    try:

        parsed = datetime.strptime(
            value,
            "%d/%m/%Y"
        )

        return parsed.strftime(
            "%Y-%m-%d"
        )

    except Exception:
        pass

    # DD-MM-YYYY
    try:

        parsed = datetime.strptime(
            value,
            "%d-%m-%Y"
        )

        return parsed.strftime(
            "%Y-%m-%d"
        )

    except Exception:
        pass

    return value


def normalize_description(value):

    if value is None:

        return ""

    return " ".join(
        str(value)
        .strip()
        .lower()
        .split()
    )


def normalize_type(
    transaction_type,
    amount
):

    if transaction_type is not None:

        transaction_type = str(
            transaction_type
        ).strip().lower()

    else:

        transaction_type = ""

    if transaction_type in {
        "income",
        "credit",
        "cr"
    }:

        return "income"

    if transaction_type in {
        "expense",
        "debit",
        "dr"
    }:

        return "expense"

    # Infer type from amount
    numeric_amount = clean_amount(
        amount
    )

    if numeric_amount < 0:

        return "expense"

    return "income"


def normalize_stored_amount(
    amount,
    transaction_type
):

    numeric_amount = abs(
        clean_amount(amount)
    )

    if transaction_type == "expense":

        return -numeric_amount

    return numeric_amount


# ============================================================
# FINGERPRINT
# ============================================================

def create_fingerprint(
    date,
    description,
    amount,
    transaction_type=None
):
    """
    Creates a canonical fingerprint.

    Duplicate comparison uses:

        date
        description
        absolute amount
        transaction type

    This means:

        -850 expense
        +850 expense

    are treated as the same transaction.
    """

    normalized_date = normalize_date(
        date
    )

    normalized_description = (
        normalize_description(
            description
        )
    )

    normalized_type = normalize_type(
        transaction_type,
        amount
    )

    normalized_amount = abs(
        clean_amount(amount)
    )

    raw = (
        f"{normalized_date}|"
        f"{normalized_description}|"
        f"{normalized_amount:.2f}|"
        f"{normalized_type}"
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


# ============================================================
# DUPLICATE CHECK
# ============================================================

def find_duplicate_transaction(
    date,
    description,
    amount,
    transaction_type,
    exclude_id=None
):

    conn = get_connection()

    cursor = conn.cursor()

    normalized_date = normalize_date(
        date
    )

    normalized_description = (
        normalize_description(
            description
        )
    )

    normalized_type = normalize_type(
        transaction_type,
        amount
    )

    normalized_amount = abs(
        clean_amount(amount)
    )

    query = """
        SELECT *
        FROM transactions
        WHERE
            date = ?
            AND LOWER(
                TRIM(description)
            ) = ?
            AND ABS(amount) = ?
            AND LOWER(
                TRIM(type)
            ) = ?
    """

    params = [
        normalized_date,
        normalized_description,
        normalized_amount,
        normalized_type
    ]

    if exclude_id is not None:

        query += """
            AND id != ?
        """

        params.append(
            exclude_id
        )

    query += """
        ORDER BY id
        LIMIT 1
    """

    cursor.execute(
        query,
        params
    )

    row = cursor.fetchone()

    conn.close()

    if row:

        return dict(row)

    return None


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():

    conn = get_connection()

    cursor = conn.cursor()


    # --------------------------------------------------------
    # TRANSACTIONS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            date TEXT NOT NULL,

            description TEXT NOT NULL,

            amount REAL NOT NULL,

            category TEXT,

            type TEXT,

            source TEXT,

            fingerprint TEXT UNIQUE,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # --------------------------------------------------------
    # BUDGETS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            category TEXT NOT NULL,

            amount REAL NOT NULL,

            month TEXT NOT NULL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(category, month)
        )
    """)


    # --------------------------------------------------------
    # GOALS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            target_amount REAL NOT NULL,

            current_amount REAL DEFAULT 0,

            deadline TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


    conn.commit()

    conn.close()


# ============================================================
# TRANSACTION FUNCTIONS
# ============================================================

def add_transaction(
    date,
    description,
    amount,
    category=None,
    transaction_type=None,
    source="manual"
):

    normalized_date = normalize_date(
        date
    )

    normalized_description = str(
        description
        if description is not None
        else ""
    ).strip()

    if not normalized_description:

        return None


    normalized_type = normalize_type(
        transaction_type,
        amount
    )


    stored_amount = normalize_stored_amount(
        amount,
        normalized_type
    )


    fingerprint = create_fingerprint(

        normalized_date,

        normalized_description,

        stored_amount,

        normalized_type

    )


    # --------------------------------------------------------
    # SEMANTIC DUPLICATE CHECK
    # --------------------------------------------------------

    duplicate = find_duplicate_transaction(

        normalized_date,

        normalized_description,

        stored_amount,

        normalized_type

    )


    if duplicate:

        return None


    # --------------------------------------------------------
    # INSERT
    # --------------------------------------------------------

    conn = get_connection()

    cursor = conn.cursor()


    try:

        cursor.execute("""
            INSERT INTO transactions
            (
                date,
                description,
                amount,
                category,
                type,
                source,
                fingerprint
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (

            normalized_date,

            normalized_description,

            stored_amount,

            category,

            normalized_type,

            source,

            fingerprint

        ))


        conn.commit()

        transaction_id = (
            cursor.lastrowid
        )


    except sqlite3.IntegrityError:

        # Fingerprint already exists
        transaction_id = None


    finally:

        conn.close()


    return transaction_id


# ============================================================
# BULK TRANSACTIONS
# ============================================================

def add_transactions(
    transactions,
    source="upload"
):
    """
    Accepts:

    1. List of dictionaries

    OR

    2. Pandas DataFrame

    Returns:

    {
        "added": number,
        "skipped": number,
        "ids": [...]
    }
    """

    # --------------------------------------------------------
    # CONVERT DATAFRAME TO DICTIONARIES
    # --------------------------------------------------------

    if hasattr(
        transactions,
        "to_dict"
    ):

        try:

            transactions = transactions.to_dict(
                orient="records"
            )

        except Exception:

            transactions = []


    if transactions is None:

        transactions = []


    added = 0

    skipped = 0

    inserted_ids = []


    # --------------------------------------------------------
    # ITERATE
    # --------------------------------------------------------

    for transaction in transactions:


        # Safety
        if not isinstance(
            transaction,
            dict
        ):

            skipped += 1

            continue


        # ----------------------------------------------------
        # SUPPORT BOTH DATABASE / DATAFRAME COLUMN NAMES
        # ----------------------------------------------------

        transaction_date = (
            transaction.get("date")
            if transaction.get("date")
            is not None

            else transaction.get(
                "Date"
            )
        )


        description = (
            transaction.get(
                "description"
            )

            if transaction.get(
                "description"
            ) is not None

            else transaction.get(
                "Description"
            )
        )


        amount = (

            transaction.get(
                "amount"
            )

            if transaction.get(
                "amount"
            ) is not None

            else transaction.get(
                "Amount",
                0
            )

        )


        category = (

            transaction.get(
                "category"
            )

            if transaction.get(
                "category"
            ) is not None

            else transaction.get(
                "Category"
            )

        )


        transaction_type = (

            transaction.get(
                "type"
            )

            if transaction.get(
                "type"
            ) is not None

            else transaction.get(
                "transaction_type"
            )

        )


        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        transaction_date = normalize_date(
            transaction_date
        )


        # ----------------------------------------------------
        # AMOUNT
        # ----------------------------------------------------

        amount = clean_amount(
            amount
        )


        # ----------------------------------------------------
        # TYPE
        # ----------------------------------------------------

        transaction_type = normalize_type(

            transaction_type,

            amount

        )


        # ----------------------------------------------------
        # CATEGORY
        # ----------------------------------------------------

        if category is None:

            category = "Other"


        category = str(
            category
        ).strip()


        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        row_source = transaction.get(
            "source",
            source
        )


        # ----------------------------------------------------
        # INSERT
        # ----------------------------------------------------

        transaction_id = add_transaction(

            date=transaction_date,

            description=description,

            amount=amount,

            category=category,

            transaction_type=transaction_type,

            source=row_source

        )


        if transaction_id:

            added += 1

            inserted_ids.append(
                transaction_id
            )

        else:

            skipped += 1


    return {

        "added":
            added,

        "skipped":
            skipped,

        "ids":
            inserted_ids

    }


# ============================================================
# GET TRANSACTIONS
# ============================================================

def get_transactions():

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        SELECT *
        FROM transactions
        ORDER BY date DESC, id DESC
    """)


    rows = cursor.fetchall()

    conn.close()


    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# GET SINGLE TRANSACTION
# ============================================================

def get_transaction(
    transaction_id
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        SELECT *
        FROM transactions
        WHERE id = ?
    """, (
        transaction_id,
    ))


    row = cursor.fetchone()

    conn.close()


    if row:

        return dict(row)


    return None


# ============================================================
# UPDATE TRANSACTION
# ============================================================

def update_transaction(
    transaction_id,
    date=None,
    description=None,
    amount=None,
    category=None,
    transaction_type=None
):

    existing = get_transaction(
        transaction_id
    )


    if not existing:

        return False


    # --------------------------------------------------------
    # FILL MISSING VALUES
    # --------------------------------------------------------

    date = (
        date
        if date is not None
        else existing["date"]
    )


    description = (
        description
        if description is not None
        else existing["description"]
    )


    amount = (
        amount
        if amount is not None
        else existing["amount"]
    )


    category = (
        category
        if category is not None
        else existing["category"]
    )


    transaction_type = (

        transaction_type

        if transaction_type
        is not None

        else existing["type"]

    )


    # --------------------------------------------------------
    # NORMALIZE
    # --------------------------------------------------------

    normalized_date = normalize_date(
        date
    )


    normalized_type = normalize_type(

        transaction_type,

        amount

    )


    stored_amount = normalize_stored_amount(

        amount,

        normalized_type

    )


    # --------------------------------------------------------
    # CHECK DUPLICATE
    # --------------------------------------------------------

    duplicate = find_duplicate_transaction(

        normalized_date,

        description,

        stored_amount,

        normalized_type,

        exclude_id=transaction_id

    )


    if duplicate:

        return False


    fingerprint = create_fingerprint(

        normalized_date,

        description,

        stored_amount,

        normalized_type

    )


    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    conn = get_connection()

    cursor = conn.cursor()


    try:

        cursor.execute("""
            UPDATE transactions
            SET
                date = ?,
                description = ?,
                amount = ?,
                category = ?,
                type = ?,
                fingerprint = ?
            WHERE id = ?
        """, (

            normalized_date,

            str(description).strip(),

            stored_amount,

            category,

            normalized_type,

            fingerprint,

            transaction_id

        ))


        conn.commit()

        success = (
            cursor.rowcount > 0
        )


    except sqlite3.IntegrityError:

        success = False


    finally:

        conn.close()


    return success


# ============================================================
# DELETE TRANSACTION
# ============================================================

def delete_transaction(
    transaction_id
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        DELETE FROM transactions
        WHERE id = ?
    """, (
        transaction_id,
    ))


    deleted = (
        cursor.rowcount > 0
    )


    conn.commit()

    conn.close()


    return deleted


# ============================================================
# CLEAR TRANSACTIONS
# ============================================================

def clear_transactions():

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        DELETE FROM transactions
    """)


    conn.commit()

    conn.close()


# ============================================================
# BUDGET FUNCTIONS
# ============================================================

def set_budget(
    category,
    amount,
    month
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        INSERT INTO budgets
        (
            category,
            amount,
            month
        )
        VALUES (?, ?, ?)

        ON CONFLICT(category, month)

        DO UPDATE SET
            amount = excluded.amount
    """, (

        category,

        clean_amount(amount),

        month

    ))


    conn.commit()


    cursor.execute("""
        SELECT id
        FROM budgets
        WHERE
            category = ?
            AND month = ?
    """, (
        category,
        month
    ))


    row = cursor.fetchone()


    conn.close()


    if row:

        return row["id"]


    return None


def get_budgets(
    month=None
):

    conn = get_connection()

    cursor = conn.cursor()


    if month:

        cursor.execute("""
            SELECT *
            FROM budgets
            WHERE month = ?
            ORDER BY category
        """, (
            month,
        ))

    else:

        cursor.execute("""
            SELECT *
            FROM budgets
            ORDER BY month DESC, category
        """)


    rows = cursor.fetchall()

    conn.close()


    return [
        dict(row)
        for row in rows
    ]


def delete_budget(
    budget_id
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        DELETE FROM budgets
        WHERE id = ?
    """, (
        budget_id,
    ))


    deleted = (
        cursor.rowcount > 0
    )


    conn.commit()

    conn.close()


    return deleted


# ============================================================
# GOAL FUNCTIONS
# ============================================================

def add_goal(
    name,
    target_amount,
    current_amount=0,
    deadline=None
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        INSERT INTO goals
        (
            name,
            target_amount,
            current_amount,
            deadline
        )
        VALUES (?, ?, ?, ?)
    """, (

        name,

        clean_amount(
            target_amount
        ),

        clean_amount(
            current_amount
        ),

        deadline

    ))


    conn.commit()


    goal_id = cursor.lastrowid


    conn.close()


    return goal_id


def get_goals():

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        SELECT *
        FROM goals
        ORDER BY id DESC
    """)


    rows = cursor.fetchall()

    conn.close()


    return [
        dict(row)
        for row in rows
    ]


def get_goal(
    goal_id
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        SELECT *
        FROM goals
        WHERE id = ?
    """, (
        goal_id,
    ))


    row = cursor.fetchone()

    conn.close()


    if row:

        return dict(row)


    return None


def update_goal(
    goal_id,
    name=None,
    target_amount=None,
    current_amount=None,
    deadline=None
):

    existing = get_goal(
        goal_id
    )


    if not existing:

        return False


    name = (
        name
        if name is not None
        else existing["name"]
    )


    target_amount = (

        target_amount

        if target_amount
        is not None

        else existing[
            "target_amount"
        ]

    )


    current_amount = (

        current_amount

        if current_amount
        is not None

        else existing[
            "current_amount"
        ]

    )


    deadline = (

        deadline

        if deadline is not None

        else existing[
            "deadline"
        ]

    )


    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        UPDATE goals
        SET
            name = ?,
            target_amount = ?,
            current_amount = ?,
            deadline = ?
        WHERE id = ?
    """, (

        name,

        clean_amount(
            target_amount
        ),

        clean_amount(
            current_amount
        ),

        deadline,

        goal_id

    ))


    conn.commit()

    success = (
        cursor.rowcount > 0
    )

    conn.close()


    return success


def delete_goal(
    goal_id
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
        DELETE FROM goals
        WHERE id = ?
    """, (
        goal_id,
    ))


    deleted = (
        cursor.rowcount > 0
    )


    conn.commit()

    conn.close()


    return deleted


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()
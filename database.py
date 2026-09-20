import sqlite3
import hashlib
import os

from datetime import datetime

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ============================================================
# DATABASE PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "finance.db"
)


# ============================================================
# CONNECTION
# ============================================================

def get_connection():

    conn = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


# ============================================================
# HELPERS
# ============================================================

def normalize_text(value):

    return str(
        value or ""
    ).strip()


def normalize_email(email):

    return (
        normalize_text(email)
        .lower()
    )


def normalize_transaction_type(
    transaction_type
):

    transaction_type = (
        normalize_text(
            transaction_type
        )
        .lower()
    )

    if transaction_type not in {
        "income",
        "expense"
    }:

        transaction_type = "expense"

    return transaction_type


def normalize_amount(amount):

    try:

        return abs(
            float(
                amount or 0
            )
        )

    except Exception:

        return 0.0


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def table_columns(
    cursor,
    table_name
):

    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    rows = cursor.fetchall()

    return [
        row["name"]
        for row in rows
    ]


def add_column_if_missing(
    cursor,
    table_name,
    column_name,
    column_definition
):

    columns = table_columns(
        cursor,
        table_name
    )

    if column_name not in columns:

        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name}
            {column_definition}
            """
        )


def init_db():

    conn = get_connection()

    cursor = conn.cursor()


    # ========================================================
    # USERS
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT NOT NULL UNIQUE,

            password_hash TEXT NOT NULL,

            created_at TEXT
                DEFAULT CURRENT_TIMESTAMP

        )
        """
    )


    # ========================================================
    # TRANSACTIONS
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            date TEXT NOT NULL,

            description TEXT NOT NULL,

            amount REAL NOT NULL,

            category TEXT,

            type TEXT,

            source TEXT,

            fingerprint TEXT UNIQUE,

            created_at TEXT
                DEFAULT CURRENT_TIMESTAMP

        )
        """
    )


    # ========================================================
    # BUDGETS
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS budgets (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            category TEXT NOT NULL,

            amount REAL NOT NULL,

            month TEXT NOT NULL,

            created_at TEXT
                DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(
                category,
                month
            )

        )
        """
    )


    # ========================================================
    # GOALS
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS goals (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            target_amount REAL NOT NULL,

            current_amount REAL
                DEFAULT 0,

            deadline TEXT,

            created_at TEXT
                DEFAULT CURRENT_TIMESTAMP

        )
        """
    )


    # ========================================================
    # MIGRATION
    #
    # Existing DB already has transactions/budgets/goals.
    # Add user_id without deleting existing data.
    # ========================================================

    add_column_if_missing(

        cursor,

        "transactions",

        "user_id",

        "INTEGER"

    )


    add_column_if_missing(

        cursor,

        "budgets",

        "user_id",

        "INTEGER"

    )


    add_column_if_missing(

        cursor,

        "goals",

        "user_id",

        "INTEGER"

    )


    # ========================================================
    # INDEXES
    # ========================================================

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_transactions_user_id
        ON transactions(user_id)
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_transactions_date
        ON transactions(date)
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_budgets_user_id
        ON budgets(user_id)
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_goals_user_id
        ON goals(user_id)
        """
    )


    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_users_email
        ON users(email)
        """
    )


    conn.commit()

    conn.close()


# ============================================================
# USER FUNCTIONS
# ============================================================

def create_user(
    name,
    email,
    password
):

    name = normalize_text(
        name
    )

    email = normalize_email(
        email
    )

    password = str(
        password or ""
    )


    if not name:

        return None


    if not email:

        return None


    if not password:

        return None


    password_hash = (
        generate_password_hash(
            password
        )
    )


    conn = get_connection()

    cursor = conn.cursor()


    try:

        cursor.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password_hash
            )
            VALUES (?, ?, ?)
            """,
            (
                name,
                email,
                password_hash
            )
        )


        conn.commit()

        user_id = (
            cursor.lastrowid
        )


    except sqlite3.IntegrityError:

        conn.close()

        return None


    conn.close()

    return user_id


def get_user_by_id(
    user_id
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            id,
            name,
            email,
            created_at
        FROM users
        WHERE id = ?
        """,
        (
            user_id,
        )
    )


    row = cursor.fetchone()

    conn.close()


    if row:

        return dict(
            row
        )


    return None


def get_user_by_email(
    email
):

    email = normalize_email(
        email
    )


    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            id,
            name,
            email,
            password_hash,
            created_at
        FROM users
        WHERE LOWER(email) = ?
        """,
        (
            email,
        )
    )


    row = cursor.fetchone()

    conn.close()


    if row:

        return dict(
            row
        )


    return None


def verify_user_password(
    email,
    password
):

    user = get_user_by_email(
        email
    )


    if not user:

        return None


    try:

        valid = check_password_hash(

            user.get(
                "password_hash",
                ""
            ),

            str(
                password or ""
            )

        )

    except Exception:

        valid = False


    if not valid:

        return None


    return {

        "id":
            user["id"],

        "name":
            user["name"],

        "email":
            user["email"],

        "created_at":
            user["created_at"]

    }


def email_exists(
    email
):

    return (
        get_user_by_email(
            email
        )
        is not None
    )


def update_user_profile(
    user_id,
    name=None,
    email=None
):

    existing = get_user_by_id(
        user_id
    )


    if not existing:

        return False


    new_name = (

        normalize_text(
            name
        )

        if name is not None

        else existing["name"]

    )


    new_email = (

        normalize_email(
            email
        )

        if email is not None

        else existing["email"]

    )


    if not new_name:

        return False


    if not new_email:

        return False


    conn = get_connection()

    cursor = conn.cursor()


    try:

        cursor.execute(
            """
            UPDATE users
            SET
                name = ?,
                email = ?
            WHERE id = ?
            """,
            (
                new_name,
                new_email,
                user_id
            )
        )


        conn.commit()


    except sqlite3.IntegrityError:

        conn.close()

        return False


    conn.close()

    return True


def update_user_password(
    user_id,
    new_password
):

    new_password = str(
        new_password or ""
    )


    if not new_password:

        return False


    password_hash = (
        generate_password_hash(
            new_password
        )
    )


    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        UPDATE users
        SET
            password_hash = ?
        WHERE id = ?
        """,
        (
            password_hash,
            user_id
        )
    )


    changed = (
        cursor.rowcount > 0
    )


    conn.commit()

    conn.close()

    return changed


def delete_user(
    user_id
):

    conn = get_connection()

    cursor = conn.cursor()


    # Delete user's data first.

    cursor.execute(
        """
        DELETE FROM transactions
        WHERE user_id = ?
        """,
        (
            user_id,
        )
    )


    cursor.execute(
        """
        DELETE FROM budgets
        WHERE user_id = ?
        """,
        (
            user_id,
        )
    )


    cursor.execute(
        """
        DELETE FROM goals
        WHERE user_id = ?
        """,
        (
            user_id,
        )
    )


    cursor.execute(
        """
        DELETE FROM users
        WHERE id = ?
        """,
        (
            user_id,
        )
    )


    deleted = (
        cursor.rowcount > 0
    )


    conn.commit()

    conn.close()

    return deleted


# ============================================================
# TRANSACTION FINGERPRINT
# ============================================================

def create_fingerprint(
    transaction_date,
    description,
    amount,
    transaction_type="expense",
    user_id=None
):

    transaction_date = normalize_text(
        transaction_date
    )

    description = (
        normalize_text(
            description
        )
        .lower()
    )

    amount = normalize_amount(
        amount
    )

    transaction_type = (
        normalize_transaction_type(
            transaction_type
        )
    )


    # User ID is included so two different users
    # can legitimately have identical transactions.

    user_part = (
        str(
            user_id
        )
        if user_id is not None
        else "legacy"
    )


    raw = (

        f"{user_part}|"
        f"{transaction_date}|"
        f"{description}|"
        f"{amount:.2f}|"
        f"{transaction_type}"

    )


    return hashlib.sha256(

        raw.encode(
            "utf-8"
        )

    ).hexdigest()


# ============================================================
# SEMANTIC DUPLICATE CHECK
# ============================================================

def transaction_exists(
    transaction_date,
    description,
    amount,
    transaction_type,
    user_id=None,
    exclude_id=None
):

    transaction_date = normalize_text(
        transaction_date
    )

    description = normalize_text(
        description
    )

    amount = normalize_amount(
        amount
    )

    transaction_type = (
        normalize_transaction_type(
            transaction_type
        )
    )


    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        query = """
            SELECT id
            FROM transactions
            WHERE
                date = ?
                AND LOWER(TRIM(description))
                    = LOWER(TRIM(?))
                AND ABS(amount) = ?
                AND LOWER(COALESCE(type, 'expense'))
                    = ?
                AND user_id IS NULL
        """

        params = [

            transaction_date,

            description,

            amount,

            transaction_type

        ]

    else:

        query = """
            SELECT id
            FROM transactions
            WHERE
                user_id = ?
                AND date = ?
                AND LOWER(TRIM(description))
                    = LOWER(TRIM(?))
                AND ABS(amount) = ?
                AND LOWER(COALESCE(type, 'expense'))
                    = ?
        """

        params = [

            user_id,

            transaction_date,

            description,

            amount,

            transaction_type

        ]


    if exclude_id is not None:

        query += """
            AND id != ?
        """

        params.append(
            exclude_id
        )


    query += """
        LIMIT 1
    """


    cursor.execute(
        query,
        tuple(params)
    )


    row = cursor.fetchone()

    conn.close()


    if row:

        return True


    return False


# ============================================================
# ADD SINGLE TRANSACTION
# ============================================================

def add_transaction(
    date,
    description,
    amount,
    category=None,
    transaction_type=None,
    source="manual",
    user_id=None
):

    transaction_date = normalize_text(
        date
    )

    description = normalize_text(
        description
    )

    transaction_type = (
        normalize_transaction_type(
            transaction_type
        )
    )

    amount = normalize_amount(
        amount
    )

    category = normalize_text(
        category
    )

    source = normalize_text(
        source
    )


    if not transaction_date:

        return None


    if not description:

        return None


    if amount <= 0:

        return None


    # --------------------------------------------------------
    # SEMANTIC DUPLICATE PROTECTION
    # --------------------------------------------------------

    if transaction_exists(

        transaction_date,
        description,
        amount,
        transaction_type,
        user_id

    ):

        return None


    fingerprint = create_fingerprint(

        transaction_date,

        description,

        amount,

        transaction_type,

        user_id

    )


    conn = get_connection()

    cursor = conn.cursor()


    try:

        cursor.execute(
            """
            INSERT INTO transactions
            (
                date,
                description,
                amount,
                category,
                type,
                source,
                fingerprint,
                user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction_date,
                description,
                amount,
                category,
                transaction_type,
                source,
                fingerprint,
                user_id
            )
        )


        conn.commit()

        transaction_id = (
            cursor.lastrowid
        )


    except sqlite3.IntegrityError:

        conn.close()

        return None


    conn.close()

    return transaction_id


# ============================================================
# ADD MULTIPLE TRANSACTIONS
# ============================================================

def add_transactions(
    transactions,
    source="upload",
    user_id=None
):

    added = 0

    skipped = 0


    # Support DataFrame input.

    if hasattr(
        transactions,
        "to_dict"
    ):

        transactions = (
            transactions
            .to_dict(
                orient="records"
            )
        )


    if transactions is None:

        return {

            "added":
                0,

            "skipped":
                0

        }


    for transaction in transactions:

        if transaction is None:

            skipped += 1

            continue


        # ----------------------------------------------------
        # Support both lowercase and uppercase keys.
        # ----------------------------------------------------

        transaction_date = (

            transaction.get(
                "date"
            )

            if transaction.get(
                "date"
            )
            is not None

            else transaction.get(
                "Date",
                ""
            )

        )


        description = (

            transaction.get(
                "description"
            )

            if transaction.get(
                "description"
            )
            is not None

            else transaction.get(
                "Description",
                ""
            )

        )


        amount = (

            transaction.get(
                "amount"
            )

            if transaction.get(
                "amount"
            )
            is not None

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
            )
            is not None

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
            )
            is not None

            else transaction.get(
                "transaction_type",
                "expense"
            )

        )


        # ----------------------------------------------------
        # Determine type from signed amount where needed.
        # ----------------------------------------------------

        try:

            numeric_amount = float(
                amount or 0
            )

        except Exception:

            numeric_amount = 0.0


        if (
            transaction_type is None
            or
            str(
                transaction_type
            )
            .strip()
            .lower()
            not in {
                "income",
                "expense"
            }
        ):

            transaction_type = (

                "income"

                if numeric_amount > 0

                else "expense"

            )


        transaction_id = add_transaction(

            date=
                transaction_date,

            description=
                description,

            amount=
                abs(
                    numeric_amount
                ),

            category=
                category,

            transaction_type=
                transaction_type,

            source=
                source,

            user_id=
                user_id

        )


        if transaction_id:

            added += 1

        else:

            skipped += 1


    return {

        "added":
            added,

        "skipped":
            skipped

    }


# ============================================================
# GET TRANSACTIONS
# ============================================================

def get_transactions(
    user_id=None,
    include_legacy=False
):

    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        # Backward-compatible behavior:
        # return all data when no user is supplied.

        cursor.execute(
            """
            SELECT *
            FROM transactions
            ORDER BY
                date DESC,
                id DESC
            """
        )

    elif include_legacy:

        cursor.execute(
            """
            SELECT *
            FROM transactions
            WHERE
                user_id = ?
                OR user_id IS NULL
            ORDER BY
                date DESC,
                id DESC
            """,
            (
                user_id,
            )
        )

    else:

        cursor.execute(
            """
            SELECT *
            FROM transactions
            WHERE user_id = ?
            ORDER BY
                date DESC,
                id DESC
            """,
            (
                user_id,
            )
        )


    rows = cursor.fetchall()

    conn.close()


    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# GET ONE TRANSACTION
# ============================================================

def get_transaction(
    transaction_id,
    user_id=None
):

    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        cursor.execute(
            """
            SELECT *
            FROM transactions
            WHERE id = ?
            """,
            (
                transaction_id,
            )
        )

    else:

        cursor.execute(
            """
            SELECT *
            FROM transactions
            WHERE
                id = ?
                AND user_id = ?
            """,
            (
                transaction_id,
                user_id
            )
        )


    row = cursor.fetchone()

    conn.close()


    if row:

        return dict(
            row
        )


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
    transaction_type=None,
    user_id=None
):

    existing = get_transaction(

        transaction_id,

        user_id=user_id

    )


    if not existing:

        return False


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

        if transaction_type is not None

        else existing["type"]

    )


    date = normalize_text(
        date
    )

    description = normalize_text(
        description
    )

    amount = normalize_amount(
        amount
    )

    category = normalize_text(
        category
    )

    transaction_type = (
        normalize_transaction_type(
            transaction_type
        )
    )


    if amount <= 0:

        return False


    # Prevent changing a transaction into
    # another duplicate transaction.

    if transaction_exists(

        date,
        description,
        amount,
        transaction_type,
        user_id=user_id,
        exclude_id=transaction_id

    ):

        return False


    fingerprint = create_fingerprint(

        date,

        description,

        amount,

        transaction_type,

        user_id

    )


    conn = get_connection()

    cursor = conn.cursor()


    try:

        if user_id is None:

            cursor.execute(
                """
                UPDATE transactions
                SET
                    date = ?,
                    description = ?,
                    amount = ?,
                    category = ?,
                    type = ?,
                    fingerprint = ?
                WHERE id = ?
                """,
                (
                    date,
                    description,
                    amount,
                    category,
                    transaction_type,
                    fingerprint,
                    transaction_id
                )
            )

        else:

            cursor.execute(
                """
                UPDATE transactions
                SET
                    date = ?,
                    description = ?,
                    amount = ?,
                    category = ?,
                    type = ?,
                    fingerprint = ?
                WHERE
                    id = ?
                    AND user_id = ?
                """,
                (
                    date,
                    description,
                    amount,
                    category,
                    transaction_type,
                    fingerprint,
                    transaction_id,
                    user_id
                )
            )


        conn.commit()


    except sqlite3.IntegrityError:

        conn.close()

        return False


    changed = (
        cursor.rowcount > 0
    )


    conn.close()

    return changed


# ============================================================
# DELETE TRANSACTION
# ============================================================

def delete_transaction(
    transaction_id,
    user_id=None
):

    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        cursor.execute(
            """
            DELETE FROM transactions
            WHERE id = ?
            """,
            (
                transaction_id,
            )
        )

    else:

        cursor.execute(
            """
            DELETE FROM transactions
            WHERE
                id = ?
                AND user_id = ?
            """,
            (
                transaction_id,
                user_id
            )
        )


    deleted = (
        cursor.rowcount > 0
    )


    conn.commit()

    conn.close()

    return deleted


# ============================================================
# CLEAR TRANSACTIONS
# ============================================================

def clear_transactions(
    user_id=None
):

    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        cursor.execute(
            """
            DELETE FROM transactions
            """
        )

    else:

        cursor.execute(
            """
            DELETE FROM transactions
            WHERE user_id = ?
            """,
            (
                user_id,
            )
        )


    conn.commit()

    conn.close()


# ============================================================
# BUDGETS
# ============================================================

def set_budget(
    category,
    amount,
    month,
    user_id=None
):

    category = normalize_text(
        category
    )

    amount = normalize_amount(
        amount
    )

    month = normalize_text(
        month
    )


    if not category:

        return None


    if amount <= 0:

        return None


    if not month:

        return None


    conn = get_connection()

    cursor = conn.cursor()


    try:

        if user_id is None:

            cursor.execute(
                """
                SELECT id
                FROM budgets
                WHERE
                    category = ?
                    AND month = ?
                    AND user_id IS NULL
                LIMIT 1
                """,
                (
                    category,
                    month
                )
            )

        else:

            cursor.execute(
                """
                SELECT id
                FROM budgets
                WHERE
                    category = ?
                    AND month = ?
                    AND user_id = ?
                LIMIT 1
                """,
                (
                    category,
                    month,
                    user_id
                )
            )


        existing = cursor.fetchone()


        if existing:

            if user_id is None:

                cursor.execute(
                    """
                    UPDATE budgets
                    SET amount = ?
                    WHERE id = ?
                    """,
                    (
                        amount,
                        existing["id"]
                    )
                )

            else:

                cursor.execute(
                    """
                    UPDATE budgets
                    SET amount = ?
                    WHERE
                        id = ?
                        AND user_id = ?
                    """,
                    (
                        amount,
                        existing["id"],
                        user_id
                    )
                )


            budget_id = (
                existing["id"]
            )

        else:

            cursor.execute(
                """
                INSERT INTO budgets
                (
                    category,
                    amount,
                    month,
                    user_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    category,
                    amount,
                    month,
                    user_id
                )
            )


            budget_id = (
                cursor.lastrowid
            )


        conn.commit()


    except sqlite3.IntegrityError:

        conn.close()

        return None


    conn.close()

    return budget_id


def get_budgets(
    month=None,
    user_id=None
):

    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        if month:

            cursor.execute(
                """
                SELECT *
                FROM budgets
                WHERE
                    month = ?
                    AND user_id IS NULL
                ORDER BY category
                """,
                (
                    month,
                )
            )

        else:

            cursor.execute(
                """
                SELECT *
                FROM budgets
                WHERE user_id IS NULL
                ORDER BY
                    month DESC,
                    category
                """
            )

    else:

        if month:

            cursor.execute(
                """
                SELECT *
                FROM budgets
                WHERE
                    month = ?
                    AND user_id = ?
                ORDER BY category
                """,
                (
                    month,
                    user_id
                )
            )

        else:

            cursor.execute(
                """
                SELECT *
                FROM budgets
                WHERE user_id = ?
                ORDER BY
                    month DESC,
                    category
                """,
                (
                    user_id,
                )
            )


    rows = cursor.fetchall()

    conn.close()


    return [
        dict(row)
        for row in rows
    ]


def delete_budget(
    budget_id,
    user_id=None
):

    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        cursor.execute(
            """
            DELETE FROM budgets
            WHERE id = ?
            """,
            (
                budget_id,
            )
        )

    else:

        cursor.execute(
            """
            DELETE FROM budgets
            WHERE
                id = ?
                AND user_id = ?
            """,
            (
                budget_id,
                user_id
            )
        )


    deleted = (
        cursor.rowcount > 0
    )


    conn.commit()

    conn.close()

    return deleted


# ============================================================
# GOALS
# ============================================================

def add_goal(
    name,
    target_amount,
    current_amount=0,
    deadline=None,
    user_id=None
):

    name = normalize_text(
        name
    )

    target_amount = (
        normalize_amount(
            target_amount
        )
    )

    current_amount = (
        normalize_amount(
            current_amount
        )
    )


    if not name:

        return None


    if target_amount <= 0:

        return None


    conn = get_connection()

    cursor = conn.cursor()


    try:

        cursor.execute(
            """
            INSERT INTO goals
            (
                name,
                target_amount,
                current_amount,
                deadline,
                user_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                target_amount,
                current_amount,
                deadline,
                user_id
            )
        )


        conn.commit()

        goal_id = (
            cursor.lastrowid
        )


    except sqlite3.IntegrityError:

        conn.close()

        return None


    conn.close()

    return goal_id


def get_goals(
    user_id=None
):

    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        cursor.execute(
            """
            SELECT *
            FROM goals
            WHERE user_id IS NULL
            ORDER BY id DESC
            """
        )

    else:

        cursor.execute(
            """
            SELECT *
            FROM goals
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (
                user_id,
            )
        )


    rows = cursor.fetchall()

    conn.close()


    return [
        dict(row)
        for row in rows
    ]


def get_goal(
    goal_id,
    user_id=None
):

    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        cursor.execute(
            """
            SELECT *
            FROM goals
            WHERE
                id = ?
                AND user_id IS NULL
            """,
            (
                goal_id,
            )
        )

    else:

        cursor.execute(
            """
            SELECT *
            FROM goals
            WHERE
                id = ?
                AND user_id = ?
            """,
            (
                goal_id,
                user_id
            )
        )


    row = cursor.fetchone()

    conn.close()


    if row:

        return dict(
            row
        )


    return None


def update_goal(
    goal_id,
    name=None,
    target_amount=None,
    current_amount=None,
    deadline=None,
    user_id=None
):

    existing = get_goal(

        goal_id,

        user_id=user_id

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

        if target_amount is not None

        else existing["target_amount"]

    )


    current_amount = (

        current_amount

        if current_amount is not None

        else existing["current_amount"]

    )


    deadline = (

        deadline

        if deadline is not None

        else existing["deadline"]

    )


    name = normalize_text(
        name
    )

    target_amount = (
        normalize_amount(
            target_amount
        )
    )

    current_amount = (
        normalize_amount(
            current_amount
        )
    )


    if not name:

        return False


    if target_amount <= 0:

        return False


    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        cursor.execute(
            """
            UPDATE goals
            SET
                name = ?,
                target_amount = ?,
                current_amount = ?,
                deadline = ?
            WHERE id = ?
            """,
            (
                name,
                target_amount,
                current_amount,
                deadline,
                goal_id
            )
        )

    else:

        cursor.execute(
            """
            UPDATE goals
            SET
                name = ?,
                target_amount = ?,
                current_amount = ?,
                deadline = ?
            WHERE
                id = ?
                AND user_id = ?
            """,
            (
                name,
                target_amount,
                current_amount,
                deadline,
                goal_id,
                user_id
            )
        )


    changed = (
        cursor.rowcount > 0
    )


    conn.commit()

    conn.close()

    return changed


def delete_goal(
    goal_id,
    user_id=None
):

    conn = get_connection()

    cursor = conn.cursor()


    if user_id is None:

        cursor.execute(
            """
            DELETE FROM goals
            WHERE id = ?
            """,
            (
                goal_id,
            )
        )

    else:

        cursor.execute(
            """
            DELETE FROM goals
            WHERE
                id = ?
                AND user_id = ?
            """,
            (
                goal_id,
                user_id
            )
        )


    deleted = (
        cursor.rowcount > 0
    )


    conn.commit()

    conn.close()

    return deleted


# ============================================================
# DATABASE INIT
# ============================================================

init_db()
import os
import pandas as pd
import numpy as np


# ==========================================
# CATEGORY DETECTION
# ==========================================

def categorize(description):

    description = str(
        description
    ).lower()

    # Income
    if any(word in description for word in [
        "salary",
        "income",
        "bonus",
        "freelance",
        "credited",
        "credit"
    ]):
        return "Income"

    # Food
    if any(word in description for word in [
        "swiggy",
        "zomato",
        "restaurant",
        "food",
        "dominos",
        "pizza",
        "mcdonald",
        "starbucks"
    ]):
        return "Food"

    # Shopping
    if any(word in description for word in [
        "amazon",
        "flipkart",
        "myntra",
        "shopping",
        "mall"
    ]):
        return "Shopping"

    # Entertainment
    if any(word in description for word in [
        "netflix",
        "spotify",
        "prime",
        "hotstar",
        "movie",
        "cinema"
    ]):
        return "Entertainment"

    # Transport
    if any(word in description for word in [
        "uber",
        "ola",
        "rapido",
        "petrol",
        "fuel",
        "metro",
        "bus",
        "train"
    ]):
        return "Transport"

    # Bills
    if any(word in description for word in [
        "electricity",
        "electric",
        "water",
        "internet",
        "wifi",
        "mobile",
        "recharge",
        "bill"
    ]):
        return "Bills"

    # Rent
    if any(word in description for word in [
        "rent",
        "house rent",
        "room rent"
    ]):
        return "Rent"

    # Education
    if any(word in description for word in [
        "college",
        "school",
        "course",
        "udemy",
        "coursera",
        "education"
    ]):
        return "Education"

    # Healthcare
    if any(word in description for word in [
        "hospital",
        "doctor",
        "medicine",
        "medical",
        "pharmacy"
    ]):
        return "Healthcare"

    return "Other"


# ==========================================
# NORMALIZE TRANSACTIONS
# ==========================================

def normalize_transactions(df):

    df = df.copy()

    # --------------------------------------
    # Clean column names
    # --------------------------------------

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    # --------------------------------------
    # Find date column
    # --------------------------------------

    date_column = None

    for column in df.columns:

        if str(column).lower() in [
            "date",
            "transaction date",
            "transaction_date"
        ]:

            date_column = column
            break

    if date_column is None:

        raise ValueError(
            "No Date column found in the file."
        )

    # --------------------------------------
    # Find description column
    # --------------------------------------

    description_column = None

    for column in df.columns:

        if str(column).lower() in [
            "description",
            "desc",
            "details",
            "narration",
            "merchant"
        ]:

            description_column = column
            break

    if description_column is None:

        raise ValueError(
            "No Description column found in the file."
        )

    # --------------------------------------
    # Find amount column
    # --------------------------------------

    amount_column = None

    for column in df.columns:

        if str(column).lower() in [
            "amount",
            "transaction amount",
            "transaction_amount",
            "value"
        ]:

            amount_column = column
            break

    if amount_column is None:

        raise ValueError(
            "No Amount column found in the file."
        )

    # --------------------------------------
    # Standardize column names
    # --------------------------------------

    df = df.rename(
        columns={
            date_column: "Date",
            description_column: "Description",
            amount_column: "Amount"
        }
    )

    # --------------------------------------
    # DATE CONVERSION
    # --------------------------------------

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    # Remove invalid dates

    df = df.dropna(
        subset=["Date"]
    )

    # --------------------------------------
    # AMOUNT CONVERSION
    # --------------------------------------

    df["Amount"] = (
        df["Amount"]
        .astype(str)
        .str.replace(
            "₹",
            "",
            regex=False
        )
        .str.replace(
            ",",
            "",
            regex=False
        )
        .str.strip()
    )

    df["Amount"] = pd.to_numeric(
        df["Amount"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["Amount"]
    )

    # --------------------------------------
    # DESCRIPTION
    # --------------------------------------

    df["Description"] = (
        df["Description"]
        .astype(str)
        .str.strip()
    )

    # --------------------------------------
    # CATEGORY
    # --------------------------------------

    if "Category" not in df.columns:

        df["Category"] = (
            df["Description"]
            .apply(categorize)
        )

    else:

        df["Category"] = (
            df["Category"]
            .fillna("")
            .astype(str)
        )

        empty_categories = (
            df["Category"].str.strip() == ""
        )

        df.loc[
            empty_categories,
            "Category"
        ] = df.loc[
            empty_categories,
            "Description"
        ].apply(categorize)

    return df


# ==========================================
# LOAD STATEMENT
# ==========================================

def load_statement(filepath):

    # IMPORTANT:
    # Keep the original file path unchanged.
    # Render/Linux is case-sensitive.
    #
    # WRONG:
    # filepath = str(filepath).lower()
    #
    # That can convert:
    # FinPilot_demo_transactions.csv
    #
    # into:
    # finpilot_demo_transactions.csv
    #
    # which causes FileNotFoundError.

    filepath = str(filepath)

    extension = os.path.splitext(
        filepath
    )[1].lower()

    if extension == ".csv":

        df = pd.read_csv(
            filepath
        )

    elif extension in (
        ".xlsx",
        ".xls"
    ):

        df = pd.read_excel(
            filepath
        )

    else:

        raise ValueError(
            "Unsupported spreadsheet format. "
            "Please use CSV, XLSX or XLS."
        )

    return normalize_transactions(
        df
    )


# ==========================================
# ANALYZE DATAFRAME
# ==========================================

def analyze_dataframe(df):

    df = df.copy()

    # ======================================
    # MAKE SURE DATE IS DATETIME
    # ======================================

    if "Date" in df.columns:

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

    # Remove rows with invalid dates

    if "Date" in df.columns:

        df = df.dropna(
            subset=["Date"]
        )

    # ======================================
    # MAKE SURE AMOUNT IS NUMERIC
    # ======================================

    df["Amount"] = pd.to_numeric(
        df["Amount"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["Amount"]
    )

    # ======================================
    # CATEGORY
    # ======================================

    if "Category" not in df.columns:

        df["Category"] = (
            df["Description"]
            .apply(categorize)
        )

    else:

        df["Category"] = (
            df["Category"]
            .fillna("")
            .astype(str)
        )

        empty_categories = (
            df["Category"].str.strip() == ""
        )

        df.loc[
            empty_categories,
            "Category"
        ] = df.loc[
            empty_categories,
            "Description"
        ].apply(categorize)

    # ======================================
    # INCOME
    # ======================================

    income = df.loc[
        df["Amount"] > 0,
        "Amount"
    ].sum()

    # ======================================
    # EXPENSES
    # ======================================

    expenses = abs(
        df.loc[
            df["Amount"] < 0,
            "Amount"
        ].sum()
    )

    # ======================================
    # SAVINGS
    # ======================================

    savings = (
        income -
        expenses
    )

    # ======================================
    # SAVINGS RATE
    # ======================================

    if income > 0:

        savings_rate = (
            savings /
            income
        ) * 100

    else:

        savings_rate = 0

    # ======================================
    # CATEGORY SPENDING
    # ======================================

    expense_df = df[
        df["Amount"] < 0
    ].copy()

    if len(expense_df) > 0:

        expense_df["ExpenseAmount"] = (
            expense_df["Amount"]
            .abs()
        )

        category_spending = (
            expense_df
            .groupby("Category")[
                "ExpenseAmount"
            ]
            .sum()
            .sort_values(
                ascending=False
            )
            .round(2)
            .to_dict()
        )

    else:

        category_spending = {}

    # ======================================
    # RECURRING PAYMENTS
    # ======================================

    recurring = []

    if len(expense_df) > 0:

        grouped = (
            expense_df
            .groupby(
                "Description"
            )
        )

        for description, group in grouped:

            if len(group) >= 2:

                average_amount = (
                    group["ExpenseAmount"]
                    .mean()
                )

                recurring.append({

                    "description":
                        description,

                    "amount":
                        round(
                            average_amount,
                            2
                        ),

                    "payments":
                        len(group)

                })

    # Sort recurring

    recurring = sorted(
        recurring,
        key=lambda x: x["amount"],
        reverse=True
    )

    # ======================================
    # UNUSUAL SPENDING
    # ======================================

    unusual = []

    if len(expense_df) > 0:

        for category, group in (
            expense_df
            .groupby("Category")
        ):

            if len(group) >= 2:

                average = (
                    group["ExpenseAmount"]
                    .mean()
                )

                threshold = (
                    average * 2
                )

                unusual_rows = group[
                    group["ExpenseAmount"]
                    > threshold
                ]

                for _, row in unusual_rows.iterrows():

                    unusual.append({

                        "description":
                            row["Description"],

                        "amount":
                            round(
                                float(
                                    row["ExpenseAmount"]
                                ),
                                2
                            ),

                        "category":
                            category,

                        "average":
                            round(
                                float(
                                    average
                                ),
                                2
                            )

                    })

    # ======================================
    # MONTHLY SPENDING
    # ======================================

    monthly_spending = {}

    if len(expense_df) > 0:

        expense_df["Month"] = (
            expense_df["Date"]
            .dt.to_period("M")
            .astype(str)
        )

        monthly_spending = (
            expense_df
            .groupby("Month")[
                "ExpenseAmount"
            ]
            .sum()
            .round(2)
            .to_dict()
        )

    # ======================================
    # JSON-SAFE TRANSACTIONS
    # ======================================

    transaction_records = []

    for _, row in df.iterrows():

        date_value = row["Date"]

        if pd.notna(date_value):

            date_value = (
                pd.to_datetime(
                    date_value
                )
                .strftime(
                    "%Y-%m-%d"
                )
            )

        transaction_records.append({

            "Date":
                date_value,

            "Description":
                str(
                    row["Description"]
                ),

            "Amount":
                float(
                    row["Amount"]
                ),

            "Category":
                str(
                    row["Category"]
                )

        })

    # ======================================
    # FINAL RESULT
    # ======================================

    return {

        "income":
            round(
                float(income),
                2
            ),

        "expenses":
            round(
                float(expenses),
                2
            ),

        "savings":
            round(
                float(savings),
                2
            ),

        "savings_rate":
            round(
                float(savings_rate),
                2
            ),

        "transaction_count":
            len(df),

        "category_spending":
            category_spending,

        "recurring":
            recurring,

        "unusual":
            unusual,

        "monthly_spending":
            monthly_spending,

        "transactions":
            transaction_records

    }


# ==========================================
# ANALYZE FILE
# ==========================================

def analyze_file(filepath):

    df = load_statement(
        filepath
    )

    return analyze_dataframe(
        df
    )


# ==========================================
# AI TRANSACTIONS → DATAFRAME
# ==========================================

def ai_transactions_to_dataframe(
    transactions
):

    rows = []

    for transaction in transactions:

        date = transaction.get(
            "date"
        )

        description = transaction.get(
            "description",
            ""
        )

        amount = float(
            transaction.get(
                "amount",
                0
            )
        )

        transaction_type = transaction.get(
            "type",
            "expense"
        )

        # ----------------------------------
        # AI amount normalization
        # ----------------------------------

        if (
            transaction_type == "expense"
            and amount > 0
        ):

            amount = -amount

        elif (
            transaction_type == "income"
            and amount < 0
        ):

            amount = abs(
                amount
            )

        rows.append({

            "Date":
                date,

            "Description":
                description,

            "Amount":
                amount,

            "Category":
                categorize(
                    description
                )

        })

    df = pd.DataFrame(
        rows
    )

    return normalize_transactions(
        df
    )
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

    filepath = str(
        filepath
    ).lower()

    if filepath.endswith(".csv"):

        df = pd.read_csv(
            filepath
        )

    elif filepath.endswith(
        (".xlsx", ".xls")
    ):

        df = pd.read_excel(
            filepath
        )

    else:

        raise ValueError(
            "Unsupported spreadsheet format."
        )

    return normalize_transactions(
        df
    )


# ==========================================
# RECURRING PAYMENT DETECTION
# ==========================================

def detect_recurring(expense_df):

    recurring = []

    if len(expense_df) == 0:
        return recurring

    grouped = (
        expense_df
        .groupby("Description")
    )

    for description, group in grouped:

        if len(group) >= 2:

            average_amount = (
                group["ExpenseAmount"]
                .mean()
            )

            recurring.append({

                "description":
                    str(description),

                "amount":
                    round(
                        float(
                            average_amount
                        ),
                        2
                    ),

                "payments":
                    int(len(group))

            })

    recurring = sorted(
        recurring,
        key=lambda x: x["amount"],
        reverse=True
    )

    return recurring


# ==========================================
# UNUSUAL SPENDING DETECTION
# ==========================================

def detect_unusual(expense_df):

    unusual = []

    if len(expense_df) == 0:
        return unusual

    for category, group in (
        expense_df
        .groupby("Category")
    ):

        if len(group) < 2:
            continue

        average = (
            group["ExpenseAmount"]
            .mean()
        )

        # A transaction more than
        # 2x the category average
        threshold = average * 2

        unusual_rows = group[
            group["ExpenseAmount"]
            > threshold
        ]

        for _, row in unusual_rows.iterrows():

            unusual.append({

                "description":
                    str(
                        row["Description"]
                    ),

                "amount":
                    round(
                        float(
                            row["ExpenseAmount"]
                        ),
                        2
                    ),

                "category":
                    str(category),

                "average":
                    round(
                        float(average),
                        2
                    ),

                "reason":
                    "Spending is more than 2x the category average."

            })

    return unusual


# ==========================================
# SMART FINANCIAL INSIGHTS
# ==========================================

def generate_insights(
    df,
    income,
    expenses,
    savings,
    savings_rate,
    category_spending,
    recurring,
    unusual,
    monthly_spending
):

    insights = []

    # --------------------------------------
    # NO DATA
    # --------------------------------------

    if len(df) == 0:

        return [{
            "type": "info",
            "title": "No financial data yet",
            "message":
                "Upload transactions to generate personalized financial insights.",
            "priority": "low"
        }]


    # --------------------------------------
    # SAVINGS RATE
    # --------------------------------------

    if income > 0:

        if savings_rate < 10:

            insights.append({

                "type": "warning",

                "title":
                    "Low savings rate",

                "message":
                    f"Your current savings rate is {savings_rate:.1f}%. "
                    "A large portion of your income is being spent.",

                "priority":
                    "high"

            })

        elif savings_rate < 20:

            insights.append({

                "type": "info",

                "title":
                    "Savings could improve",

                "message":
                    f"You are currently saving {savings_rate:.1f}% of your income.",

                "priority":
                    "medium"

            })

        else:

            insights.append({

                "type": "positive",

                "title":
                    "Healthy savings pattern",

                "message":
                    f"Your current savings rate is {savings_rate:.1f}% of income.",

                "priority":
                    "low"

            })


    # --------------------------------------
    # TOP SPENDING CATEGORY
    # --------------------------------------

    if category_spending:

        top_category = max(
            category_spending,
            key=category_spending.get
        )

        top_amount = float(
            category_spending[
                top_category
            ]
        )

        percentage = 0

        if expenses > 0:

            percentage = (
                top_amount /
                expenses
            ) * 100

        insights.append({

            "type":
                "info",

            "title":
                f"Highest spending: {top_category}",

            "message":
                f"{top_category} accounts for "
                f"{percentage:.1f}% of your total expenses "
                f"with spending of ₹{top_amount:,.2f}.",

            "priority":
                "medium"

        })


    # --------------------------------------
    # HIGH FOOD SPENDING
    # --------------------------------------

    food_spending = (
        category_spending
        .get("Food", 0)
    )

    if expenses > 0 and food_spending > 0:

        food_percentage = (
            food_spending /
            expenses
        ) * 100

        if food_percentage >= 20:

            insights.append({

                "type":
                    "warning",

                "title":
                    "Food spending is significant",

                "message":
                    f"Food expenses are ₹{food_spending:,.2f}, "
                    f"which is {food_percentage:.1f}% of total spending.",

                "priority":
                    "medium"

            })


    # --------------------------------------
    # HIGH SHOPPING SPENDING
    # --------------------------------------

    shopping_spending = (
        category_spending
        .get("Shopping", 0)
    )

    if expenses > 0 and shopping_spending > 0:

        shopping_percentage = (
            shopping_spending /
            expenses
        ) * 100

        if shopping_percentage >= 20:

            insights.append({

                "type":
                    "warning",

                "title":
                    "Shopping spending is significant",

                "message":
                    f"Shopping expenses are ₹{shopping_spending:,.2f}, "
                    f"representing {shopping_percentage:.1f}% "
                    "of total expenses.",

                "priority":
                    "medium"

            })


    # --------------------------------------
    # RECURRING PAYMENTS
    # --------------------------------------

    if recurring:

        recurring_total = sum(

            float(
                item["amount"]
            )

            for item in recurring

        )

        insights.append({

            "type":
                "info",

            "title":
                "Recurring payments detected",

            "message":
                f"FinPilot detected {len(recurring)} recurring payment(s). "
                f"Their combined average cost is approximately "
                f"₹{recurring_total:,.2f} per payment cycle.",

            "priority":
                "medium"

        })


    # --------------------------------------
    # UNUSUAL TRANSACTIONS
    # --------------------------------------

    if unusual:

        largest_unusual = max(
            unusual,
            key=lambda x:
                x["amount"]
        )

        insights.append({

            "type":
                "warning",

            "title":
                "Unusual spending detected",

            "message":
                f"{largest_unusual['description']} "
                f"was ₹{largest_unusual['amount']:,.2f}, "
                f"while the average {largest_unusual['category']} "
                f"transaction is around "
                f"₹{largest_unusual['average']:,.2f}.",

            "priority":
                "high"

        })


    # --------------------------------------
    # MONTHLY TREND
    # --------------------------------------

    months = list(
        monthly_spending.items()
    )

    if len(months) >= 2:

        previous_month = float(
            months[-2][1]
        )

        current_month = float(
            months[-1][1]
        )

        if previous_month > 0:

            change = (
                (
                    current_month -
                    previous_month
                )
                /
                previous_month
            ) * 100


            if change >= 20:

                insights.append({

                    "type":
                        "warning",

                    "title":
                        "Spending increased",

                    "message":
                        f"Spending increased by "
                        f"{change:.1f}% compared with "
                        f"the previous month.",

                    "priority":
                        "high"

                })


            elif change <= -20:

                insights.append({

                    "type":
                        "positive",

                    "title":
                        "Spending decreased",

                    "message":
                        f"Spending decreased by "
                        f"{abs(change):.1f}% compared with "
                        f"the previous month.",

                    "priority":
                        "low"

                })


    # --------------------------------------
    # NEGATIVE SAVINGS
    # --------------------------------------

    if income > 0 and savings < 0:

        insights.append({

            "type":
                "danger",

            "title":
                "Expenses exceed income",

            "message":
                f"Your expenses exceed your recorded income "
                f"by ₹{abs(savings):,.2f}.",

            "priority":
                "high"

        })


    # --------------------------------------
    # POSITIVE CASH FLOW
    # --------------------------------------

    if income > 0 and savings > 0:

        insights.append({

            "type":
                "positive",

            "title":
                "Positive cash flow",

            "message":
                f"You currently have positive cash flow of "
                f"₹{savings:,.2f}.",

            "priority":
                "low"

        })


    # --------------------------------------
    # SORT BY PRIORITY
    # --------------------------------------

    priority_order = {

        "high": 1,
        "medium": 2,
        "low": 3

    }

    insights.sort(
        key=lambda x:
            priority_order.get(
                x["priority"],
                3
            )
    )

    return insights


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

    recurring = detect_recurring(
        expense_df
    )

    # ======================================
    # UNUSUAL SPENDING
    # ======================================

    unusual = detect_unusual(
        expense_df
    )

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
    # SMART INSIGHTS
    # ======================================

    insights = generate_insights(

        df=df,

        income=float(income),

        expenses=float(expenses),

        savings=float(savings),

        savings_rate=float(
            savings_rate
        ),

        category_spending=
            category_spending,

        recurring=
            recurring,

        unusual=
            unusual,

        monthly_spending=
            monthly_spending

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

        # NEW
        "insights":
            insights,

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
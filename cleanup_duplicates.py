import sqlite3
import os


DB_PATH = "finance.db"


def main():

    print("=" * 65)
    print("FINPILOT SMART DUPLICATE CLEANUP")
    print("=" * 65)

    if not os.path.exists(DB_PATH):

        print("\n❌ finance.db not found.")
        return


    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()


    # ========================================================
    # CHECK TABLE
    # ========================================================

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
    """)

    tables = [
        row[0]
        for row in cursor.fetchall()
    ]

    print("\nTables:")
    print(tables)


    if "transactions" not in tables:

        print("\n❌ transactions table not found.")

        connection.close()

        return


    # ========================================================
    # COUNT BEFORE
    # ========================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM transactions
    """)

    before_count = cursor.fetchone()[0]

    print(
        f"\nTransactions before cleanup: {before_count}"
    )


    # ========================================================
    # CREATE BACKUP
    # ========================================================

    cursor.execute("""
        DROP TABLE IF EXISTS transactions_backup_cleanup
    """)


    cursor.execute("""
        CREATE TABLE transactions_backup_cleanup
        AS
        SELECT *
        FROM transactions
    """)

    connection.commit()


    print(
        "✅ Backup created."
    )


    # ========================================================
    # SHOW UPLOAD RECORDS
    # ========================================================

    cursor.execute("""
        SELECT
            id,
            date,
            description,
            amount,
            category,
            type,
            source
        FROM transactions
        WHERE source = 'upload'
        ORDER BY id
    """)

    upload_rows = cursor.fetchall()


    print(
        f"\nUpload records found: {len(upload_rows)}"
    )


    # ========================================================
    # SMART DUPLICATE DETECTION
    #
    # A record from source='upload' is considered a duplicate
    # if a NON-upload record already exists with:
    #
    # same date
    # same description
    # same absolute amount
    #
    # This handles:
    # - positive vs negative amount
    # - different category
    # - different source
    # - different fingerprint
    # ========================================================

    duplicate_ids = []


    for row in upload_rows:

        (
            transaction_id,
            transaction_date,
            description,
            amount,
            category,
            transaction_type,
            source
        ) = row


        cursor.execute("""
            SELECT id
            FROM transactions
            WHERE
                source != 'upload'
                AND date = ?
                AND LOWER(TRIM(description))
                    = LOWER(TRIM(?))
                AND ABS(amount) = ABS(?)
            ORDER BY id
            LIMIT 1
        """, (
            transaction_date,
            description,
            amount
        ))


        matching_original = cursor.fetchone()


        if matching_original:

            duplicate_ids.append(
                transaction_id
            )

            print(
                f"\nDuplicate found:"
                f"\n  Upload ID : {transaction_id}"
                f"\n  Original ID: {matching_original[0]}"
                f"\n  Date      : {transaction_date}"
                f"\n  Description: {description}"
                f"\n  Amount    : {amount}"
            )


    # ========================================================
    # DELETE DUPLICATES
    # ========================================================

    if duplicate_ids:

        placeholders = ",".join(
            "?"
            for _ in duplicate_ids
        )


        delete_sql = f"""
            DELETE FROM transactions
            WHERE id IN ({placeholders})
        """


        cursor.execute(
            delete_sql,
            duplicate_ids
        )


        removed = cursor.rowcount


    else:

        removed = 0


    connection.commit()


    # ========================================================
    # COUNT AFTER
    # ========================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM transactions
    """)

    after_count = cursor.fetchone()[0]


    print("\n" + "=" * 65)

    print(
        f"Duplicate upload rows removed: {removed}"
    )

    print(
        f"Transactions after cleanup: {after_count}"
    )

    print("=" * 65)


    # ========================================================
    # CURRENT TRANSACTIONS
    # ========================================================

    cursor.execute("""
        SELECT
            id,
            date,
            description,
            amount,
            category,
            type,
            source
        FROM transactions
        ORDER BY date, id
    """)


    rows = cursor.fetchall()


    print("\nCurrent transactions:\n")


    for row in rows:

        print(row)


    # ========================================================
    # SUMMARY
    # ========================================================

    cursor.execute("""
        SELECT
            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'income'
                        THEN ABS(amount)
                        ELSE 0
                    END
                ),
                0
            )
        FROM transactions
    """)

    income = cursor.fetchone()[0]


    cursor.execute("""
        SELECT
            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'expense'
                        THEN ABS(amount)
                        ELSE 0
                    END
                ),
                0
            )
        FROM transactions
    """)

    expenses = cursor.fetchone()[0]


    savings = income - expenses


    print("\n" + "=" * 65)

    print("FINPILOT SUMMARY")

    print("=" * 65)

    print(
        f"Income    : ₹{income:,.2f}"
    )

    print(
        f"Expenses  : ₹{expenses:,.2f}"
    )

    print(
        f"Savings   : ₹{savings:,.2f}"
    )

    print(
        f"Transactions: {after_count}"
    )

    print("=" * 65)


    connection.close()


if __name__ == "__main__":

    main()
import csv
from datetime import date, datetime
import io
import sqlite3
import uuid
from contextlib import contextmanager

import streamlit as st


ACCOUNT_SEED = (
    ("1000", "Cash on hand", "Asset", "cash_cash", "Operating"),
    ("1010", "Card clearing", "Asset", "cash_card", "Operating"),
    ("1020", "bKash", "Asset", "cash_bkash", "Operating"),
    ("1030", "Nagad", "Asset", "cash_nagad", "Operating"),
    ("1040", "Rocket", "Asset", "cash_rocket", "Operating"),
    ("1050", "Upay", "Asset", "cash_upay", "Operating"),
    ("1060", "Bank account", "Asset", "cash_bank_transfer", "Operating"),
    ("1100", "Patient receivables", "Asset", "accounts_receivable", "Operating"),
    ("1200", "Diagnostic inventory", "Asset", "inventory", "Operating"),
    ("1500", "Fixed assets at cost", "Asset", "fixed_assets", "Investing"),
    ("1590", "Accumulated depreciation", "Asset", "accumulated_depreciation", "Investing"),
    ("2000", "Supplier payables", "Liability", "accounts_payable", "Operating"),
    ("2100", "Referrer commissions payable", "Liability", "referrer_payable", "Operating"),
    ("2110", "Doctor fees payable", "Liability", "doctor_fee_payable", "Operating"),
    ("2200", "Patient refunds payable", "Liability", "patient_refunds_payable", "Operating"),
    ("3000", "Owner capital", "Equity", "owner_capital", "Financing"),
    ("3100", "Opening balance equity", "Equity", "opening_equity", "Financing"),
    ("3200", "Retained earnings", "Equity", "retained_earnings", "Financing"),
    ("4000", "Test revenue", "Income", "test_revenue", "Operating"),
    ("4090", "Other income", "Income", "other_income", "Operating"),
    ("4100", "Cancellation income retained", "Income", "cancellation_income", "Operating"),
    ("5000", "Discounts given", "Expense", "discount_expense", "Operating"),
    ("5010", "Referral commission expense", "Expense", "commission_expense", "Operating"),
    ("5020", "Laboratory consumables", "Expense", "consumables_expense", "Operating"),
    ("5030", "Outside laboratory expense", "Expense", "outside_lab_expense", "Operating"),
    ("5040", "Consultant fees", "Expense", "consultant_expense", "Operating"),
    ("5050", "Rent expense", "Expense", "rent_expense", "Operating"),
    ("5060", "Utilities expense", "Expense", "utilities_expense", "Operating"),
    ("5070", "Staff and other operating expense", "Expense", "staff_expense", "Operating"),
    ("5080", "Depreciation expense", "Expense", "depreciation_expense", "Operating"),
    ("5090", "Bad debt expense", "Expense", "bad_debt_expense", "Operating"),
    ("5100", "Miscellaneous expenses", "Expense", "miscellaneous_expense", "Operating"),
    ("5110", "Cash variance", "Expense", "cash_variance", "Operating"),
    ("4120", "Cash overage income", "Income", "cash_variance_income", "Operating"),
)

CASH_FLOW_CLASS = ("Operating", "Investing", "Financing")


@contextmanager
def accounting_database():
    db_path = st.session_state.get("tenant_db_path")
    if not db_path:
        raise RuntimeError("A tenant database context is required for accounting.")
    connection = sqlite3.connect(db_path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def money_to_paisa(amount):
    return int(round(float(amount) * 100))


def paisa_to_money(amount):
    return int(amount or 0) / 100


def ensure_accounting_schema(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounting_accounts (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL UNIQUE,
            account_type TEXT NOT NULL CHECK (
                account_type IN ('Asset', 'Liability', 'Equity', 'Income', 'Expense')
            ),
            system_key TEXT UNIQUE,
            cash_flow_class TEXT NOT NULL DEFAULT 'Operating'
                CHECK (cash_flow_class IN ('Operating', 'Investing', 'Financing')),
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS accounting_journals (
            id INTEGER PRIMARY KEY,
            journal_no TEXT NOT NULL UNIQUE,
            journal_date TEXT NOT NULL,
            memo TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'Manual',
            source_key TEXT UNIQUE,
            source_id INTEGER,
            created_by INTEGER REFERENCES staff(id),
            created_at TEXT NOT NULL,
            reverses_id INTEGER REFERENCES accounting_journals(id),
            CHECK (length(journal_date) = 10)
        );
        CREATE TABLE IF NOT EXISTS accounting_journal_lines (
            id INTEGER PRIMARY KEY,
            journal_id INTEGER NOT NULL REFERENCES accounting_journals(id),
            account_id INTEGER NOT NULL REFERENCES accounting_accounts(id),
            debit_paisa INTEGER NOT NULL DEFAULT 0 CHECK (debit_paisa >= 0),
            credit_paisa INTEGER NOT NULL DEFAULT 0 CHECK (credit_paisa >= 0),
            party_type TEXT NOT NULL DEFAULT '',
            party_id INTEGER,
            description TEXT NOT NULL DEFAULT '',
            CHECK (
                (debit_paisa > 0 AND credit_paisa = 0)
                OR (credit_paisa > 0 AND debit_paisa = 0)
            )
        );
        CREATE TABLE IF NOT EXISTS accounting_parties (
            id INTEGER PRIMARY KEY,
            party_type TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            UNIQUE(party_type, name)
        );
        CREATE TABLE IF NOT EXISTS accounting_periods (
            id INTEGER PRIMARY KEY,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            closed_by INTEGER REFERENCES staff(id),
            closed_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            CHECK (start_date <= end_date),
            UNIQUE(start_date, end_date)
        );
        CREATE TABLE IF NOT EXISTS accounting_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS accounting_vendor_bills (
            id INTEGER PRIMARY KEY,
            vendor_id INTEGER REFERENCES accounting_parties(id),
            bill_number TEXT NOT NULL,
            bill_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            description TEXT NOT NULL,
            debit_account_id INTEGER NOT NULL REFERENCES accounting_accounts(id),
            amount_paisa INTEGER NOT NULL CHECK (amount_paisa > 0),
            stock_item_id INTEGER REFERENCES stock_items(id),
            quantity REAL NOT NULL DEFAULT 0,
            unit_cost_paisa INTEGER NOT NULL DEFAULT 0,
            asset_name TEXT NOT NULL DEFAULT '',
            useful_life_months INTEGER NOT NULL DEFAULT 0,
            residual_paisa INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER REFERENCES staff(id),
            created_at TEXT NOT NULL,
            UNIQUE(bill_number, vendor_id)
        );
        CREATE TABLE IF NOT EXISTS accounting_vendor_payments (
            id INTEGER PRIMARY KEY,
            vendor_bill_id INTEGER NOT NULL REFERENCES accounting_vendor_bills(id),
            amount_paisa INTEGER NOT NULL CHECK (amount_paisa > 0),
            cash_account_id INTEGER NOT NULL REFERENCES accounting_accounts(id),
            method TEXT NOT NULL,
            reference TEXT NOT NULL DEFAULT '',
            paid_at TEXT NOT NULL,
            paid_by INTEGER REFERENCES staff(id)
        );
        CREATE TABLE IF NOT EXISTS accounting_fixed_assets (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            acquired_on TEXT NOT NULL,
            cost_paisa INTEGER NOT NULL CHECK (cost_paisa > 0),
            residual_paisa INTEGER NOT NULL DEFAULT 0 CHECK (residual_paisa >= 0),
            useful_life_months INTEGER NOT NULL CHECK (useful_life_months > 0),
            vendor_bill_id INTEGER REFERENCES accounting_vendor_bills(id),
            active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER REFERENCES staff(id),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS accounting_depreciation_runs (
            id INTEGER PRIMARY KEY,
            asset_id INTEGER NOT NULL REFERENCES accounting_fixed_assets(id),
            period TEXT NOT NULL,
            amount_paisa INTEGER NOT NULL CHECK (amount_paisa > 0),
            journal_id INTEGER NOT NULL REFERENCES accounting_journals(id),
            created_at TEXT NOT NULL,
            UNIQUE(asset_id, period)
        );
        CREATE INDEX IF NOT EXISTS accounting_journal_date_id
            ON accounting_journals(journal_date, id);
        CREATE INDEX IF NOT EXISTS accounting_lines_account_journal
            ON accounting_journal_lines(account_id, journal_id);
        CREATE INDEX IF NOT EXISTS accounting_lines_party
            ON accounting_journal_lines(party_type, party_id);
        CREATE INDEX IF NOT EXISTS accounting_vendor_due
            ON accounting_vendor_bills(due_date, vendor_id);
        """
    )
    existing = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(stock_items)").fetchall()
    }
    if "average_cost_paisa" not in existing:
        connection.execute(
            "ALTER TABLE stock_items ADD COLUMN average_cost_paisa INTEGER NOT NULL DEFAULT 0"
        )
    movement_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(stock_movements)").fetchall()
    }
    if "unit_cost_paisa" not in movement_columns:
        connection.execute(
            "ALTER TABLE stock_movements ADD COLUMN unit_cost_paisa INTEGER NOT NULL DEFAULT 0"
        )
    connection.executemany(
        """INSERT OR IGNORE INTO accounting_accounts
           (code, name, account_type, system_key, cash_flow_class, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (*row, datetime.now().astimezone().isoformat(timespec="seconds"))
            for row in ACCOUNT_SEED
        ],
    )
    connection.execute(
        """INSERT OR IGNORE INTO accounting_settings(setting_key, setting_value)
           VALUES ('go_live_date', ?)""",
        (date.today().isoformat(),),
    )


def account_id(connection, system_key):
    row = connection.execute(
        "SELECT id FROM accounting_accounts WHERE system_key = ? AND active = 1",
        (system_key,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Required accounting account is not configured: {system_key}.")
    return row["id"]


def cash_account_key(method):
    method_keys = {
        "Cash": "cash_cash",
        "Card": "cash_card",
        "bKash": "cash_bkash",
        "Nagad": "cash_nagad",
        "Rocket": "cash_rocket",
        "Upay": "cash_upay",
        "Bank transfer": "cash_bank_transfer",
    }
    try:
        return method_keys[method]
    except KeyError as error:
        raise ValueError(f"Payment method has no accounting account: {method}.") from error


def assert_period_open(connection, journal_date):
    period = connection.execute(
        """SELECT start_date, end_date FROM accounting_periods
           WHERE ? BETWEEN start_date AND end_date LIMIT 1""",
        (journal_date,),
    ).fetchone()
    if period:
        raise ValueError(
            f"Accounting period {period['start_date']} to {period['end_date']} is closed."
        )


def post_journal_entry(
    connection,
    journal_date,
    memo,
    lines,
    created_by=None,
    source_type="Manual",
    source_key=None,
    source_id=None,
    reverses_id=None,
):
    journal_date = str(journal_date)[:10]
    try:
        date.fromisoformat(journal_date)
    except ValueError as error:
        raise ValueError("Enter a valid accounting journal date.") from error
    if not memo.strip():
        raise ValueError("Enter a journal description.")
    if source_key:
        existing = connection.execute(
            "SELECT id FROM accounting_journals WHERE source_key = ?",
            (source_key,),
        ).fetchone()
        if existing:
            return existing["id"]
    assert_period_open(connection, journal_date)

    prepared = []
    debit_total = credit_total = 0
    for line in lines:
        debit = int(line.get("debit_paisa", money_to_paisa(line.get("debit", 0))))
        credit = int(line.get("credit_paisa", money_to_paisa(line.get("credit", 0))))
        if debit < 0 or credit < 0 or bool(debit) == bool(credit):
            raise ValueError("Each journal line must have either a positive debit or credit.")
        if "account_id" in line:
            selected_account = line["account_id"]
        else:
            selected_account = account_id(connection, line["account_key"])
        if not connection.execute(
            "SELECT 1 FROM accounting_accounts WHERE id = ? AND active = 1",
            (selected_account,),
        ).fetchone():
            raise ValueError("A journal line uses an inactive or missing account.")
        debit_total += debit
        credit_total += credit
        prepared.append(
            (
                selected_account,
                debit,
                credit,
                line.get("party_type", ""),
                line.get("party_id"),
                line.get("description", ""),
            )
        )
    if len(prepared) < 2:
        raise ValueError("A journal entry must contain at least two lines.")
    if debit_total != credit_total:
        raise ValueError(
            f"Journal debits and credits must balance; difference is "
            f"৳{paisa_to_money(debit_total - credit_total):,.2f}."
        )

    cursor = connection.execute(
        """INSERT INTO accounting_journals(
               journal_no, journal_date, memo, source_type, source_key, source_id,
               created_by, created_at, reverses_id
           ) VALUES ('PENDING', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            journal_date,
            memo.strip(),
            source_type,
            source_key,
            source_id,
            created_by,
            datetime.now().astimezone().isoformat(timespec="seconds"),
            reverses_id,
        ),
    )
    journal_id = cursor.lastrowid
    journal_no = f"JE-{journal_id:07d}"
    connection.execute(
        "UPDATE accounting_journals SET journal_no = ? WHERE id = ?",
        (journal_no, journal_id),
    )
    connection.executemany(
        """INSERT INTO accounting_journal_lines(
               journal_id, account_id, debit_paisa, credit_paisa,
               party_type, party_id, description
           ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [(journal_id, *line) for line in prepared],
    )
    return journal_id


def record_audit(connection, staff_id, action, entity_id, details):
    row = (
        connection.execute("SELECT role FROM staff WHERE id = ?", (staff_id,)).fetchone()
        if staff_id is not None
        else None
    )
    acting_role = row["role"] if row else "Unknown"
    dev_actor = st.session_state.get("tenant_dev_actor")
    if dev_actor:
        acting_role = f"Platform Dev ({dev_actor})"
    connection.execute(
        """INSERT INTO audit_log(
               staff_id, acting_role, action, entity_type, entity_id,
               before_value, after_value, created_at
           ) VALUES (?, ?, ?, 'accounting', ?, '', ?, ?)""",
        (
            staff_id,
            acting_role,
            action,
            str(entity_id),
            details,
            datetime.now().astimezone().isoformat(timespec="seconds"),
        ),
    )


def reverse_journal_entry(connection, journal_id, reason, staff_id):
    if not reason.strip():
        raise ValueError("Enter a reason for reversing this journal.")
    original = connection.execute(
        "SELECT * FROM accounting_journals WHERE id = ?",
        (journal_id,),
    ).fetchone()
    if original is None:
        raise ValueError("The selected journal entry no longer exists.")
    if original["reverses_id"] is not None:
        raise ValueError("A reversal entry cannot itself be reversed.")
    if connection.execute(
        "SELECT 1 FROM accounting_journals WHERE reverses_id = ?",
        (journal_id,),
    ).fetchone():
        raise ValueError("This journal entry has already been reversed.")
    lines = connection.execute(
        "SELECT * FROM accounting_journal_lines WHERE journal_id = ?",
        (journal_id,),
    ).fetchall()
    reversed_lines = [
        {
            "account_id": line["account_id"],
            "debit_paisa": line["credit_paisa"],
            "credit_paisa": line["debit_paisa"],
            "party_type": line["party_type"],
            "party_id": line["party_id"],
            "description": line["description"],
        }
        for line in lines
    ]
    return post_journal_entry(
        connection,
        date.today().isoformat(),
        f"Reversal of {original['journal_no']}: {reason.strip()}",
        reversed_lines,
        created_by=staff_id,
        source_type="Reversal",
        source_key=f"reversal:{journal_id}",
        source_id=journal_id,
        reverses_id=journal_id,
    )


def _account_rows(connection):
    return [
        dict(row)
        for row in connection.execute(
            """SELECT id, code, name, account_type, system_key, cash_flow_class, active
               FROM accounting_accounts ORDER BY code"""
        ).fetchall()
    ]


def _journal_summary(connection, start_date=None, end_date=None):
    conditions = []
    params = []
    if start_date:
        conditions.append("j.journal_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("j.journal_date <= ?")
        params.append(end_date)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return [
        dict(row)
        for row in connection.execute(
            f"""SELECT j.id, j.journal_no, j.journal_date, j.memo, j.source_type,
                       j.source_key, j.reverses_id, s.display_name AS created_by,
                       SUM(l.debit_paisa) AS debit_paisa,
                       SUM(l.credit_paisa) AS credit_paisa
                FROM accounting_journals j
                JOIN accounting_journal_lines l ON l.journal_id = j.id
                LEFT JOIN staff s ON s.id = j.created_by
                {where}
                GROUP BY j.id ORDER BY j.journal_date DESC, j.id DESC LIMIT 500""",
            params,
        ).fetchall()
    ]


def _download_csv(rows, label, file_name):
    if not rows:
        st.info("No accounting records are available for this report.")
        return
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    st.download_button(
        label,
        output.getvalue().encode("utf-8-sig"),
        file_name=f"{file_name}.csv",
        mime="text/csv",
    )


def _line_query(connection, start_date=None, end_date=None):
    conditions = []
    params = []
    if start_date:
        conditions.append("j.journal_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("j.journal_date <= ?")
        params.append(end_date)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return [
        dict(row)
        for row in connection.execute(
            f"""SELECT j.journal_date, j.journal_no, j.memo, j.source_type,
                       a.code, a.name AS account, a.account_type, a.system_key,
                       a.cash_flow_class, l.debit_paisa, l.credit_paisa,
                       l.party_type, l.party_id, l.description
                FROM accounting_journals j
                JOIN accounting_journal_lines l ON l.journal_id = j.id
                JOIN accounting_accounts a ON a.id = l.account_id
                {where}
                ORDER BY j.journal_date, j.id, l.id""",
            params,
        ).fetchall()
    ]


def _report_date_range(prefix):
    first, last = st.columns(2)
    today = date.today()
    start = first.date_input(
        "From",
        value=today.replace(day=1),
        key=f"{prefix}_from",
    )
    end = last.date_input("To", value=today, key=f"{prefix}_to")
    if start > end:
        st.error("The start date must be on or before the end date.")
        return None
    return start.isoformat(), end.isoformat()


def _reporting_tab(connection):
    st.subheader("Accounting reports")
    selected_range = _report_date_range("accounting_report")
    if not selected_range:
        return
    start_date, end_date = selected_range
    accounts = _account_rows(connection)
    account_map = {row["id"]: row for row in accounts}
    lines = _line_query(connection, end_date=end_date)
    period_lines = [
        line for line in lines if start_date <= line["journal_date"] <= end_date
    ]
    as_of_balances = {}
    period_balances = {}
    for line in lines:
        account_id_value = next(
            row["id"] for row in accounts if row["code"] == line["code"]
        )
        as_of_balances.setdefault(account_id_value, [0, 0])
        as_of_balances[account_id_value][0] += line["debit_paisa"]
        as_of_balances[account_id_value][1] += line["credit_paisa"]
        if start_date <= line["journal_date"] <= end_date:
            period_balances.setdefault(account_id_value, [0, 0])
            period_balances[account_id_value][0] += line["debit_paisa"]
            period_balances[account_id_value][1] += line["credit_paisa"]

    report_tabs = st.tabs(
        [
            "Trial balance",
            "Profit & loss",
            "Balance sheet",
            "Cash flow",
            "Cash book",
            "Dues & payables",
            "Referrer cost",
        ]
    )
    with report_tabs[0]:
        rows = []
        total_debit = total_credit = 0
        for account in accounts:
            debit, credit = as_of_balances.get(account["id"], (0, 0))
            signed = debit - credit
            if signed > 0:
                dr, cr = signed, 0
            else:
                dr, cr = 0, -signed
            if dr or cr:
                rows.append(
                    {
                        "Code": account["code"],
                        "Account": account["name"],
                        "Type": account["account_type"],
                        "Debit ৳": paisa_to_money(dr),
                        "Credit ৳": paisa_to_money(cr),
                    }
                )
                total_debit += dr
                total_credit += cr
        st.caption(f"Balances through {end_date}")
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
            st.write(
                f"**Total debits:** ৳{paisa_to_money(total_debit):,.2f} · "
                f"**Total credits:** ৳{paisa_to_money(total_credit):,.2f}"
            )
            _download_csv(rows, "Download trial balance CSV", "trial-balance")
        else:
            st.info("No journals have been posted yet.")
    with report_tabs[1]:
        income = expense = 0
        rows = []
        for account in accounts:
            if account["account_type"] not in ("Income", "Expense"):
                continue
            debit, credit = period_balances.get(account["id"], (0, 0))
            balance = credit - debit if account["account_type"] == "Income" else debit - credit
            if balance:
                if account["account_type"] == "Income":
                    income += balance
                else:
                    expense += balance
                rows.append(
                    {
                        "Code": account["code"],
                        "Account": account["name"],
                        "Category": account["account_type"],
                        "Amount ৳": paisa_to_money(balance),
                    }
                )
        rows.append(
            {
                "Code": "",
                "Account": "Net income",
                "Category": "Summary",
                "Amount ৳": paisa_to_money(income - expense),
            }
        )
        st.caption(f"Accrual basis · {start_date} through {end_date}")
        st.dataframe(rows, hide_index=True, use_container_width=True)
        _download_csv(rows, "Download profit and loss CSV", "profit-and-loss")
    with report_tabs[2]:
        assets = liabilities = equity = 0
        rows = []
        for account in accounts:
            if account["account_type"] not in ("Asset", "Liability", "Equity"):
                continue
            debit, credit = as_of_balances.get(account["id"], (0, 0))
            raw_balance = debit - credit
            if account["account_type"] == "Asset":
                balance = raw_balance
                assets += balance
            else:
                balance = -raw_balance
                if account["account_type"] == "Liability":
                    liabilities += balance
                else:
                    equity += balance
            if balance:
                rows.append(
                    {
                        "Code": account["code"],
                        "Account": account["name"],
                        "Category": account["account_type"],
                        "Balance ৳": paisa_to_money(balance),
                    }
                )
        earnings = 0
        for account in accounts:
            if account["account_type"] not in ("Income", "Expense"):
                continue
            debit, credit = as_of_balances.get(account["id"], (0, 0))
            earnings += credit - debit if account["account_type"] == "Income" else debit - credit
        rows.append(
            {
                "Code": "",
                "Account": "Accumulated current earnings",
                "Category": "Equity",
                "Balance ৳": paisa_to_money(earnings),
            }
        )
        rows.append(
            {
                "Code": "",
                "Account": "Total assets",
                "Category": "Summary",
                "Balance ৳": paisa_to_money(assets),
            }
        )
        rows.append(
            {
                "Code": "",
                "Account": "Total liabilities and equity",
                "Category": "Summary",
                "Balance ৳": paisa_to_money(liabilities + equity + earnings),
            }
        )
        difference = assets - liabilities - equity - earnings
        if difference:
            st.warning(
                f"Balance sheet is out of balance by ৳{paisa_to_money(difference):,.2f}. "
                "Review opening balances and journal entries."
            )
        st.caption(f"Accrual basis · As of {end_date}")
        st.dataframe(rows, hide_index=True, use_container_width=True)
        _download_csv(rows, "Download balance sheet CSV", "balance-sheet")
    with report_tabs[3]:
        cash_lines = [
            line
            for line in period_lines
            if line["system_key"] and line["system_key"].startswith("cash_")
        ]
        cash_rows = [
            {
                "Date": line["journal_date"],
                "Journal": line["journal_no"],
                "Description": line["memo"],
                "Cash / bank account": line["account"],
                "Cash flow class": line["cash_flow_class"],
                "Received ৳": paisa_to_money(line["debit_paisa"]),
                "Paid ৳": paisa_to_money(line["credit_paisa"]),
            }
            for line in cash_lines
        ]
        received = sum(line["debit_paisa"] for line in cash_lines)
        paid = sum(line["credit_paisa"] for line in cash_lines)
        st.metric("Net cash change", f"৳{paisa_to_money(received - paid):,.2f}")
        if cash_rows:
            st.dataframe(cash_rows, hide_index=True, use_container_width=True)
            _download_csv(cash_rows, "Download cash flow CSV", "cash-flow")
        else:
            st.info("No cash or bank journal activity in this date range.")
    with report_tabs[4]:
        cash_rows = [
            {
                "Date": line["journal_date"],
                "Journal": line["journal_no"],
                "Account": line["account"],
                "Description": line["memo"],
                "Received ৳": paisa_to_money(line["debit_paisa"]),
                "Paid ৳": paisa_to_money(line["credit_paisa"]),
            }
            for line in period_lines
            if line["system_key"] and line["system_key"].startswith("cash_")
        ]
        st.dataframe(cash_rows, hide_index=True, use_container_width=True)
        _download_csv(cash_rows, "Download cash book CSV", "cash-book")
    with report_tabs[5]:
        dues = [
            {
                "Invoice": row["invoice_no"],
                "Patient": row["patient"],
                "Due ৳": float(row["due"]),
                "Date": row["created_at"],
            }
            for row in connection.execute(
                """SELECT i.invoice_no, p.full_name AS patient, i.due, i.created_at
                   FROM invoices i JOIN visits v ON v.id = i.visit_id
                   JOIN patients p ON p.id = v.patient_id
                   WHERE i.due > 0 ORDER BY i.created_at, i.id"""
            ).fetchall()
        ]
        payables = [
            {
                "Supplier bill": row["bill_number"],
                "Supplier": row["vendor"],
                "Due date": row["due_date"],
                "Outstanding ৳": paisa_to_money(row["amount_paisa"] - row["paid_paisa"]),
            }
            for row in connection.execute(
                """SELECT b.bill_number, b.due_date, b.amount_paisa,
                          COALESCE(SUM(p.amount_paisa), 0) AS paid_paisa,
                          COALESCE(v.name, 'Unspecified supplier') AS vendor
                   FROM accounting_vendor_bills b
                   LEFT JOIN accounting_parties v ON v.id = b.vendor_id
                   LEFT JOIN accounting_vendor_payments p ON p.vendor_bill_id = b.id
                   GROUP BY b.id
                   HAVING b.amount_paisa > paid_paisa
                   ORDER BY b.due_date"""
            ).fetchall()
        ]
        st.write("**Patient dues**")
        st.dataframe(dues, hide_index=True, use_container_width=True)
        st.write("**Supplier payables**")
        st.dataframe(payables, hide_index=True, use_container_width=True)
        _download_csv(dues, "Download patient dues CSV", "patient-dues")
        _download_csv(payables, "Download supplier payables CSV", "supplier-payables")
    with report_tabs[6]:
        commission_rows = [
            {
                "Referrer": row["referrer"],
                "Accrued ৳": float(row["amount"]),
                "Paid ৳": float(row["paid_amount"]),
                "Balance ৳": float(row["amount"] - row["paid_amount"]),
            }
            for row in connection.execute(
                """SELECT r.name AS referrer, SUM(ce.amount) AS amount,
                          SUM(ce.paid_amount) AS paid_amount
                   FROM commission_entries ce
                   JOIN referrers r ON r.id = ce.referrer_id
                   GROUP BY r.id, r.name ORDER BY r.name"""
            ).fetchall()
        ]
        st.dataframe(commission_rows, hide_index=True, use_container_width=True)
        _download_csv(
            commission_rows,
            "Download referrer cost CSV",
            "referrer-cost",
        )


def _add_accounting_journal(connection, staff_id, journal_id, action, details):
    record_audit(connection, staff_id, action, journal_id, details)


def _manual_journal_tab(connection, staff):
    st.subheader("General journal")
    accounts = [row for row in _account_rows(connection) if row["active"]]
    choices = {f"{row['code']} · {row['name']}": row for row in accounts}
    journals = _journal_summary(connection)
    if journals:
        st.dataframe(
            [
                {
                    "Date": row["journal_date"],
                    "Journal": row["journal_no"],
                    "Description": row["memo"],
                    "Source": row["source_type"],
                    "Debit ৳": paisa_to_money(row["debit_paisa"]),
                    "Credit ৳": paisa_to_money(row["credit_paisa"]),
                    "By": row["created_by"],
                    "Reversal of": row["reverses_id"],
                }
                for row in journals
            ],
            hide_index=True,
            use_container_width=True,
        )
        reversible = [row for row in journals if row["reverses_id"] is None]
        if reversible:
            journal_choices = {
                f"{row['journal_no']} · {row['journal_date']} · {row['memo']}": row
                for row in reversible
            }
            with st.form("reverse_accounting_journal", clear_on_submit=True):
                selected = st.selectbox("Journal to reverse", list(journal_choices))
                reason = st.text_input("Reversal reason")
                reverse_submitted = st.form_submit_button("Post reversing entry")
            if reverse_submitted:
                try:
                    journal = journal_choices[selected]
                    with accounting_database() as transaction:
                        reversal_id = reverse_journal_entry(
                            transaction, journal["id"], reason, staff["id"]
                        )
                        _add_accounting_journal(
                            transaction,
                            staff["id"],
                            reversal_id,
                            "Accounting journal reversed",
                            f"reverses={journal['journal_no']}; reason={reason.strip()}",
                        )
                    st.success("A reversing journal was posted; the original entry was retained.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

    with st.expander("Post a manual journal", expanded=not journals):
        st.caption("Use equal debits and credits. Posted journals are immutable.")
        with st.form("manual_accounting_journal", clear_on_submit=True):
            entry_date = st.date_input("Journal date", value=date.today())
            memo = st.text_input("Description")
            rows = [
                {"Account": "", "Debit ৳": 0.0, "Credit ৳": 0.0}
                for _ in range(6)
            ]
            edited = st.data_editor(
                rows,
                hide_index=True,
                num_rows="fixed",
                column_config={
                    "Account": st.column_config.SelectboxColumn(
                        "Account",
                        options=list(choices),
                        required=False,
                    ),
                    "Debit ৳": st.column_config.NumberColumn(
                        "Debit ৳", min_value=0.0, step=100.0, format="%.2f"
                    ),
                    "Credit ৳": st.column_config.NumberColumn(
                        "Credit ৳", min_value=0.0, step=100.0, format="%.2f"
                    ),
                },
                key="manual_journal_lines",
            )
            submitted = st.form_submit_button("Post journal", type="primary")
        if submitted:
            records = edited.to_dict("records") if hasattr(edited, "to_dict") else edited
            lines = []
            for row in records:
                account_label = row.get("Account")
                debit = money_to_paisa(row.get("Debit ৳", 0))
                credit = money_to_paisa(row.get("Credit ৳", 0))
                if not account_label and not debit and not credit:
                    continue
                if account_label not in choices:
                    st.error("Select an active account for each journal line.")
                    return
                lines.append(
                    {
                        "account_id": choices[account_label]["id"],
                        "debit_paisa": debit,
                        "credit_paisa": credit,
                        "description": memo.strip(),
                    }
                )
            try:
                with accounting_database() as transaction:
                    journal_id = post_journal_entry(
                        transaction,
                        entry_date.isoformat(),
                        memo,
                        lines,
                        created_by=staff["id"],
                    )
                    _add_accounting_journal(
                        transaction,
                        staff["id"],
                        journal_id,
                        "Manual accounting journal posted",
                        memo.strip(),
                    )
                st.success("Journal posted.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

    with st.expander("Enter opening balances", expanded=False):
        already_opened = connection.execute(
            "SELECT setting_value FROM accounting_settings WHERE setting_key = 'opening_journal_id'"
        ).fetchone()
        if already_opened:
            st.info("Opening balances have already been posted. Corrections must use a reversal journal.")
            return
        st.caption(
            "Enter the verified balances as of the start date. Leave zero-value rows blank; "
            "the opening entry must balance."
        )
        balances = [
            row for row in accounts
            if row["system_key"] not in ("opening_equity", "retained_earnings")
        ]
        with st.form("opening_accounting_balances", clear_on_submit=True):
            opening_date = st.date_input(
                "Opening balance date",
                value=date.today(),
                key="opening_balance_date",
            )
            opening_rows = [
                {"Account": "", "Debit ৳": 0.0, "Credit ৳": 0.0}
                for _ in range(min(max(len(balances), 6), 32))
            ]
            edited_opening = st.data_editor(
                opening_rows,
                hide_index=True,
                num_rows="fixed",
                column_config={
                    "Account": st.column_config.SelectboxColumn(
                        "Account",
                        options=[f"{row['code']} · {row['name']}" for row in balances],
                        required=False,
                    ),
                    "Debit ৳": st.column_config.NumberColumn(
                        "Debit ৳", min_value=0.0, step=100.0, format="%.2f"
                    ),
                    "Credit ৳": st.column_config.NumberColumn(
                        "Credit ৳", min_value=0.0, step=100.0, format="%.2f"
                    ),
                },
                key="opening_balance_lines",
            )
            opening_submitted = st.form_submit_button(
                "Post opening balances",
                type="primary",
            )
        if opening_submitted:
            records = (
                edited_opening.to_dict("records")
                if hasattr(edited_opening, "to_dict")
                else edited_opening
            )
            opening_choices = {
                f"{row['code']} · {row['name']}": row for row in balances
            }
            lines = []
            for row in records:
                selected_account = row.get("Account")
                debit = money_to_paisa(row.get("Debit ৳", 0))
                credit = money_to_paisa(row.get("Credit ৳", 0))
                if not selected_account and not debit and not credit:
                    continue
                if selected_account not in opening_choices:
                    st.error("Select an account for each opening balance.")
                    return
                lines.append(
                    {
                        "account_id": opening_choices[selected_account]["id"],
                        "debit_paisa": debit,
                        "credit_paisa": credit,
                        "description": "Verified opening balance",
                    }
                )
            try:
                with accounting_database() as transaction:
                    journal_id = post_journal_entry(
                        transaction,
                        opening_date.isoformat(),
                        "Opening balances",
                        lines,
                        created_by=staff["id"],
                        source_type="Opening balance",
                        source_key="opening-balances",
                    )
                    transaction.execute(
                        """INSERT INTO accounting_settings(setting_key, setting_value)
                           VALUES ('opening_journal_id', ?)
                           ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value""",
                        (str(journal_id),),
                    )
                    _add_accounting_journal(
                        transaction,
                        staff["id"],
                        journal_id,
                        "Accounting opening balances posted",
                        f"date={opening_date.isoformat()}",
                    )
                st.success("Opening balances posted.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))


def _accounts_tab(connection, staff):
    st.subheader("Chart of accounts")
    accounts = _account_rows(connection)
    st.dataframe(accounts, hide_index=True, use_container_width=True)
    with st.form("add_accounting_account", clear_on_submit=True):
        code = st.text_input("Account code")
        name = st.text_input("Account name")
        account_type = st.selectbox(
            "Account type", ("Asset", "Liability", "Equity", "Income", "Expense")
        )
        cash_flow_class = st.selectbox("Cash-flow class", CASH_FLOW_CLASS)
        submitted = st.form_submit_button("Add account")
    if submitted:
        try:
            if not code.strip() or not name.strip():
                raise ValueError("Enter both an account code and name.")
            with accounting_database() as transaction:
                transaction.execute(
                    """INSERT INTO accounting_accounts(
                           code, name, account_type, cash_flow_class, created_at
                       ) VALUES (?, ?, ?, ?, ?)""",
                    (
                        code.strip(),
                        name.strip(),
                        account_type,
                        cash_flow_class,
                        datetime.now().astimezone().isoformat(timespec="seconds"),
                    ),
                )
                record_audit(
                    transaction, staff["id"], "Accounting account created", code.strip(), name.strip()
                )
            st.success("Account added.")
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("That account code or name is already in use.")
        except ValueError as error:
            st.error(str(error))


def _party_id(connection, name, phone, staff_id):
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Enter the supplier or payee name.")
    connection.execute(
        """INSERT OR IGNORE INTO accounting_parties(
               party_type, name, phone, created_at
           ) VALUES ('Supplier', ?, ?, ?)""",
        (
            normalized_name,
            phone.strip(),
            datetime.now().astimezone().isoformat(timespec="seconds"),
        ),
    )
    return connection.execute(
        "SELECT id FROM accounting_parties WHERE party_type = 'Supplier' AND name = ?",
        (normalized_name,),
    ).fetchone()["id"]


def _expenses_and_payables_tab(connection, staff):
    st.subheader("Expenses, suppliers and payables")
    vendors = [
        dict(row)
        for row in connection.execute(
            """SELECT id, name, phone FROM accounting_parties
               WHERE party_type = 'Supplier' AND active = 1 ORDER BY name"""
        ).fetchall()
    ]
    expense_accounts = [
        row for row in _account_rows(connection)
        if row["active"] and row["account_type"] == "Expense"
    ]
    asset_account = next(
        row for row in _account_rows(connection)
        if row["system_key"] == "fixed_assets"
    )
    inventory_account = next(
        row for row in _account_rows(connection)
        if row["system_key"] == "inventory"
    )
    stock_items = [
        dict(row)
        for row in connection.execute(
            "SELECT id, name, unit, on_hand, average_cost_paisa FROM stock_items ORDER BY name"
        ).fetchall()
    ]
    vendor_labels = {"No supplier (petty cash)": None}
    vendor_labels.update({row["name"]: row for row in vendors})
    bill_type = st.radio(
        "Record type",
        ("Miscellaneous expense", "Supplier bill", "Inventory purchase", "Fixed asset purchase"),
        horizontal=True,
        key="accounting_record_type",
    )
    with st.form("accounting_expense_or_bill", clear_on_submit=True):
        supplier_options = list(vendor_labels)
        supplier_label = st.selectbox("Supplier / payee", supplier_options)
        new_supplier = st.text_input("New supplier (optional)")
        supplier_phone = st.text_input("Supplier contact")
        if bill_type == "Inventory purchase":
            stock_names = [row["name"] for row in stock_items]
            if not stock_names:
                st.caption("Add an inventory item first in the Inventory module.")
                stock_name = ""
            else:
                stock_name = st.selectbox("Inventory item", stock_names)
            quantity = st.number_input("Quantity received", min_value=0.001, value=1.0, step=1.0)
            unit_cost = st.number_input("Unit cost (৳)", min_value=0.01, value=100.0, step=10.0)
            expense_account = inventory_account
            asset_name = ""
            useful_life = 0
            residual = 0.0
        elif bill_type == "Fixed asset purchase":
            asset_name = st.text_input("Asset name")
            amount = st.number_input("Asset purchase cost (৳)", min_value=0.01, value=10000.0, step=1000.0)
            useful_life = st.number_input("Useful life (months)", min_value=1, value=60, step=1)
            residual = st.number_input("Residual value (৳)", min_value=0.0, value=0.0, step=500.0)
            quantity = 0.0
            unit_cost = 0.0
            expense_account = asset_account
        else:
            descriptions = {
                f"{row['code']} · {row['name']}": row for row in expense_accounts
            }
            selected_expense = st.selectbox("Expense category", list(descriptions))
            expense_account = descriptions[selected_expense]
            amount = st.number_input("Amount (৳)", min_value=0.01, value=500.0, step=100.0)
            useful_life = 0
            residual = 0.0
            asset_name = ""
            quantity = 0.0
            unit_cost = 0.0
        bill_number = st.text_input("Voucher / supplier bill number")
        transaction_date = st.date_input("Transaction date", value=date.today())
        due_date = st.date_input("Due date", value=date.today())
        settle_now = st.checkbox(
            "Paid now",
            value=bill_type == "Miscellaneous expense",
            help="Unpaid items are posted to supplier payables.",
        )
        if settle_now:
            method = st.selectbox("Paid from", tuple(
                ("Cash", "Card", "bKash", "Nagad", "Rocket", "Upay", "Bank transfer")
            ))
        else:
            method = "Cash"
        description = st.text_input("Description / business purpose")
        submitted = st.form_submit_button("Post accounting transaction", type="primary")
    if submitted:
        if bill_type == "Inventory purchase":
            amount_paisa = money_to_paisa(quantity * unit_cost)
        else:
            amount_paisa = money_to_paisa(amount)
        if amount_paisa <= 0 or not description.strip():
            st.error("Enter a positive amount and transaction description.")
            return
        if bill_type == "Inventory purchase" and not stock_name:
            st.error("Add an inventory item before recording this purchase.")
            return
        if bill_type == "Fixed asset purchase" and not asset_name.strip():
            st.error("Enter the fixed asset name.")
            return
        try:
            with accounting_database() as transaction:
                supplier_name = new_supplier.strip() or (
                    supplier_label if vendor_labels[supplier_label] else ""
                )
                party_id = (
                    _party_id(transaction, supplier_name, supplier_phone, staff["id"])
                    if supplier_name
                    else None
                )
                item = next(
                    (row for row in stock_items if row["name"] == stock_name),
                    None,
                )
                bill_cursor = transaction.execute(
                    """INSERT INTO accounting_vendor_bills(
                           vendor_id, bill_number, bill_date, due_date, description,
                           debit_account_id, amount_paisa, stock_item_id, quantity,
                           unit_cost_paisa, asset_name, useful_life_months,
                           residual_paisa, created_by, created_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        party_id,
                        bill_number.strip() or f"DCMS-{uuid.uuid4().hex[:12].upper()}",
                        transaction_date.isoformat(),
                        due_date.isoformat(),
                        description.strip(),
                        expense_account["id"],
                        amount_paisa,
                        item["id"] if item and bill_type == "Inventory purchase" else None,
                        quantity,
                        money_to_paisa(unit_cost) if bill_type == "Inventory purchase" else 0,
                        asset_name.strip(),
                        int(useful_life),
                        money_to_paisa(residual),
                        staff["id"],
                        datetime.now().astimezone().isoformat(timespec="seconds"),
                    ),
                )
                bill_id = bill_cursor.lastrowid
                if bill_type == "Inventory purchase":
                    stock_item = transaction.execute(
                        "SELECT on_hand, average_cost_paisa FROM stock_items WHERE id = ?",
                        (item["id"],),
                    ).fetchone()
                    old_quantity = stock_item["on_hand"]
                    if old_quantity < 0:
                        raise ValueError(
                            "This item has negative on-hand stock. Reconcile its quantity to zero "
                            "before posting a supplier purchase."
                        )
                    new_qty = stock_item["on_hand"] + quantity
                    if new_qty <= 0:
                        raise ValueError(
                            "The received quantity must leave a positive on-hand balance."
                        )
                    if old_quantity == 0:
                        average_cost_paisa = money_to_paisa(unit_cost)
                    else:
                        old_value = int(
                            round(old_quantity * stock_item["average_cost_paisa"])
                        )
                        new_value = old_value + amount_paisa
                        average_cost_paisa = int(round(new_value / new_qty))
                    transaction.execute(
                        "UPDATE stock_items SET on_hand = ?, average_cost_paisa = ? WHERE id = ?",
                        (new_qty, average_cost_paisa, item["id"]),
                    )
                    transaction.execute(
                        """INSERT INTO stock_movements(
                               stock_item_id, quantity, movement_type, note, created_by,
                               created_at, unit_cost_paisa
                           ) VALUES (?, ?, 'Stock received', ?, ?, ?, ?)""",
                        (
                            item["id"],
                            quantity,
                            f"Supplier bill {bill_number or bill_id}",
                            staff["id"],
                            datetime.now().astimezone().isoformat(timespec="seconds"),
                            money_to_paisa(unit_cost),
                        ),
                    )
                if bill_type == "Fixed asset purchase":
                    transaction.execute(
                        """INSERT INTO accounting_fixed_assets(
                               name, acquired_on, cost_paisa, residual_paisa,
                               useful_life_months, vendor_bill_id, created_by, created_at
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            asset_name.strip(),
                            transaction_date.isoformat(),
                            amount_paisa,
                            money_to_paisa(residual),
                            int(useful_life),
                            bill_id,
                            staff["id"],
                            datetime.now().astimezone().isoformat(timespec="seconds"),
                        ),
                    )
                payable_account = account_id(transaction, "accounts_payable")
                journal_lines = [
                    {
                        "account_id": expense_account["id"],
                        "debit_paisa": amount_paisa,
                        "credit_paisa": 0,
                        "party_type": "Supplier" if party_id else "",
                        "party_id": party_id,
                        "description": description.strip(),
                    }
                ]
                if settle_now:
                    journal_lines.append(
                        {
                            "account_key": cash_account_key(method),
                            "debit_paisa": 0,
                            "credit_paisa": amount_paisa,
                            "description": description.strip(),
                        }
                    )
                else:
                    journal_lines.append(
                        {
                            "account_id": payable_account,
                            "debit_paisa": 0,
                            "credit_paisa": amount_paisa,
                            "party_type": "Supplier" if party_id else "",
                            "party_id": party_id,
                            "description": description.strip(),
                        }
                    )
                journal_id = post_journal_entry(
                    transaction,
                    transaction_date.isoformat(),
                    description.strip(),
                    journal_lines,
                    created_by=staff["id"],
                    source_type=bill_type,
                    source_key=f"accounting-bill:{bill_id}",
                    source_id=bill_id,
                )
                if not settle_now:
                    record_audit(
                        transaction,
                        staff["id"],
                        "Supplier payable recorded",
                        bill_id,
                        f"amount_paisa={amount_paisa}; due={due_date.isoformat()}",
                    )
                else:
                    transaction.execute(
                        """INSERT INTO accounting_vendor_payments(
                               vendor_bill_id, amount_paisa, cash_account_id, method,
                               reference, paid_at, paid_by
                           ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            bill_id,
                            amount_paisa,
                            account_id(transaction, cash_account_key(method)),
                            method,
                            bill_number.strip(),
                            transaction_date.isoformat(),
                            staff["id"],
                        ),
                    )
                _add_accounting_journal(
                    transaction,
                    staff["id"],
                    journal_id,
                    "Accounting transaction posted",
                    f"type={bill_type}; amount_paisa={amount_paisa}; bill_id={bill_id}",
                )
            st.success("Accounting transaction posted.")
            st.rerun()
        except (ValueError, sqlite3.IntegrityError) as error:
            st.error(str(error) or "The accounting transaction could not be posted.")

    st.subheader("Supplier bills and balances")
    bill_rows = [
        dict(row)
        for row in connection.execute(
            """SELECT b.id, b.bill_number, b.bill_date, b.due_date, b.description,
                      b.amount_paisa, COALESCE(v.name, 'Unspecified supplier') AS supplier,
                      COALESCE(SUM(p.amount_paisa), 0) AS paid_paisa,
                      b.debit_account_id, b.vendor_id
               FROM accounting_vendor_bills b
               LEFT JOIN accounting_parties v ON v.id = b.vendor_id
               LEFT JOIN accounting_vendor_payments p ON p.vendor_bill_id = b.id
               GROUP BY b.id ORDER BY b.bill_date DESC, b.id DESC LIMIT 250"""
        ).fetchall()
    ]
    if bill_rows:
        st.dataframe(
            [
                {
                    "Date": row["bill_date"],
                    "Bill": row["bill_number"],
                    "Supplier": row["supplier"],
                    "Description": row["description"],
                    "Amount ৳": paisa_to_money(row["amount_paisa"]),
                    "Paid ৳": paisa_to_money(row["paid_paisa"]),
                    "Balance ৳": paisa_to_money(row["amount_paisa"] - row["paid_paisa"]),
                    "Due date": row["due_date"],
                }
                for row in bill_rows
            ],
            hide_index=True,
            use_container_width=True,
        )
        unpaid = [
            row for row in bill_rows
            if row["amount_paisa"] > row["paid_paisa"]
        ]
        if unpaid:
            unpaid_options = {
                f"{row['bill_number']} · {row['supplier']} · "
                f"Due ৳{paisa_to_money(row['amount_paisa'] - row['paid_paisa']):,.2f}": row
                for row in unpaid
            }
            with st.form("accounting_pay_supplier_bill", clear_on_submit=True):
                selected = st.selectbox("Bill to pay", list(unpaid_options))
                bill = unpaid_options[selected]
                remaining = bill["amount_paisa"] - bill["paid_paisa"]
                payment_amount = st.number_input(
                    "Payment amount (৳)",
                    min_value=0.01,
                    max_value=paisa_to_money(remaining),
                    value=paisa_to_money(remaining),
                    step=100.0,
                )
                payment_method = st.selectbox(
                    "Payment source",
                    ("Cash", "Card", "bKash", "Nagad", "Rocket", "Upay", "Bank transfer"),
                )
                payment_reference = st.text_input("Payment reference")
                payment_date = st.date_input("Payment date", value=date.today())
                pay_submitted = st.form_submit_button("Pay supplier bill")
            if pay_submitted:
                amount_paisa = money_to_paisa(payment_amount)
                try:
                    with accounting_database() as transaction:
                        transaction.execute("BEGIN IMMEDIATE")
                        current_bill = transaction.execute(
                            """SELECT b.bill_number, b.vendor_id, b.amount_paisa,
                                      COALESCE(SUM(p.amount_paisa), 0) AS paid_paisa
                               FROM accounting_vendor_bills b
                               LEFT JOIN accounting_vendor_payments p
                                 ON p.vendor_bill_id = b.id
                               WHERE b.id = ?
                               GROUP BY b.id""",
                            (bill["id"],),
                        ).fetchone()
                        if current_bill is None:
                            raise ValueError("The selected supplier bill no longer exists.")
                        current_remaining = (
                            current_bill["amount_paisa"] - current_bill["paid_paisa"]
                        )
                        if amount_paisa <= 0 or amount_paisa > current_remaining:
                            raise ValueError(
                                "Payment must be positive and no greater than the current bill balance."
                            )
                        payable = account_id(transaction, "accounts_payable")
                        party_type = "Supplier" if current_bill["vendor_id"] else ""
                        lines = [
                            {
                                "account_id": payable,
                                "debit_paisa": amount_paisa,
                                "credit_paisa": 0,
                                "party_type": party_type,
                                "party_id": current_bill["vendor_id"],
                            },
                            {
                                "account_key": cash_account_key(payment_method),
                                "debit_paisa": 0,
                                "credit_paisa": amount_paisa,
                            },
                        ]
                        payment_cursor = transaction.execute(
                            """INSERT INTO accounting_vendor_payments(
                                   vendor_bill_id, amount_paisa, cash_account_id, method,
                                   reference, paid_at, paid_by
                               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                bill["id"],
                                amount_paisa,
                                account_id(transaction, cash_account_key(payment_method)),
                                payment_method,
                                payment_reference.strip(),
                                payment_date.isoformat(),
                                staff["id"],
                            ),
                        )
                        journal_id = post_journal_entry(
                            transaction,
                            payment_date.isoformat(),
                            f"Supplier payment {current_bill['bill_number']}",
                            lines,
                            created_by=staff["id"],
                            source_type="Supplier payment",
                            source_key=f"supplier-payment:{payment_cursor.lastrowid}",
                            source_id=payment_cursor.lastrowid,
                        )
                        _add_accounting_journal(
                            transaction,
                            staff["id"],
                            journal_id,
                            "Supplier payment posted",
                            f"bill={current_bill['bill_number']}; amount_paisa={amount_paisa}",
                        )
                    st.success("Supplier payment posted.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))


def _fixed_assets_tab(connection, staff):
    st.subheader("Fixed assets and depreciation")
    assets = [
        dict(row)
        for row in connection.execute(
            """SELECT fa.*, COALESCE(SUM(dr.amount_paisa), 0) AS depreciation_paisa
               FROM accounting_fixed_assets fa
               LEFT JOIN accounting_depreciation_runs dr ON dr.asset_id = fa.id
               GROUP BY fa.id ORDER BY fa.acquired_on, fa.id"""
        ).fetchall()
    ]
    if assets:
        st.dataframe(
            [
                {
                    "Asset": row["name"],
                    "Acquired": row["acquired_on"],
                    "Cost ৳": paisa_to_money(row["cost_paisa"]),
                    "Accumulated depreciation ৳": paisa_to_money(row["depreciation_paisa"]),
                    "Net book value ৳": paisa_to_money(
                        max(0, row["cost_paisa"] - row["depreciation_paisa"])
                    ),
                    "Useful life (months)": row["useful_life_months"],
                    "Status": "Active" if row["active"] else "Disposed",
                }
                for row in assets
            ],
            hide_index=True,
            use_container_width=True,
        )
    active_assets = [asset for asset in assets if asset["active"]]
    if active_assets:
        st.markdown("#### Post monthly straight-line depreciation")
        period_month = st.date_input(
            "Depreciation month",
            value=date.today().replace(day=1),
            key="accounting_depreciation_month",
        ).replace(day=1)
        if st.button("Post depreciation for month", type="primary"):
            total_depreciation = 0
            lines = []
            run_assets = []
            for asset in active_assets:
                if asset["acquired_on"][:7] >= period_month.isoformat()[:7]:
                    continue
                prior = connection.execute(
                    """SELECT 1 FROM accounting_depreciation_runs
                       WHERE asset_id = ? AND period = ?""",
                    (asset["id"], period_month.isoformat()[:7]),
                ).fetchone()
                if prior:
                    continue
                monthly = int(
                    round(
                        (asset["cost_paisa"] - asset["residual_paisa"])
                        / asset["useful_life_months"]
                    )
                )
                remaining = max(
                    0,
                    asset["cost_paisa"]
                    - asset["residual_paisa"]
                    - asset["depreciation_paisa"],
                )
                monthly = min(monthly, remaining)
                if monthly <= 0:
                    continue
                total_depreciation += monthly
                run_assets.append((asset["id"], monthly))
            if not run_assets:
                st.info("No eligible unposted depreciation is due for this month.")
            else:
                lines = [
                    {
                        "account_key": "depreciation_expense",
                        "debit_paisa": total_depreciation,
                        "credit_paisa": 0,
                        "description": "Monthly straight-line depreciation",
                    },
                    {
                        "account_key": "accumulated_depreciation",
                        "debit_paisa": 0,
                        "credit_paisa": total_depreciation,
                        "description": "Monthly straight-line depreciation",
                    },
                ]
                try:
                    with accounting_database() as transaction:
                        journal_id = post_journal_entry(
                            transaction,
                            period_month.isoformat(),
                            f"Depreciation for {period_month:%B %Y}",
                            lines,
                            created_by=staff["id"],
                            source_type="Depreciation",
                            source_key=f"depreciation:{period_month:%Y-%m}",
                        )
                        for asset_id_value, amount_paisa in run_assets:
                            transaction.execute(
                                """INSERT INTO accounting_depreciation_runs(
                                       asset_id, period, amount_paisa, journal_id, created_at
                                   ) VALUES (?, ?, ?, ?, ?)""",
                                (
                                    asset_id_value,
                                    period_month.isoformat()[:7],
                                    amount_paisa,
                                    journal_id,
                                    datetime.now().astimezone().isoformat(timespec="seconds"),
                                ),
                            )
                        _add_accounting_journal(
                            transaction,
                            staff["id"],
                            journal_id,
                            "Fixed-asset depreciation posted",
                            f"period={period_month:%Y-%m}; amount_paisa={total_depreciation}",
                        )
                    st.success("Monthly depreciation posted.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))


def _periods_tab(connection, staff):
    st.subheader("Accounting period controls")
    st.caption("A closed period is immutable; corrections must be posted as dated reversing entries.")
    periods = [
        dict(row)
        for row in connection.execute(
            """SELECT p.start_date, p.end_date, p.closed_at, s.display_name AS closed_by, p.reason
               FROM accounting_periods p LEFT JOIN staff s ON s.id = p.closed_by
               ORDER BY p.start_date DESC"""
        ).fetchall()
    ]
    if periods:
        st.dataframe(periods, hide_index=True, use_container_width=True)
    with st.form("close_accounting_period", clear_on_submit=True):
        start = st.date_input("Period starts", value=date.today().replace(day=1))
        end = st.date_input("Period ends", value=date.today())
        reason = st.text_input("Period close note")
        submitted = st.form_submit_button("Close accounting period", type="primary")
    if submitted:
        if start > end:
            st.error("Period start must be on or before its end.")
        elif not reason.strip():
            st.error("Enter a close note.")
        else:
            try:
                with accounting_database() as transaction:
                    overlap = transaction.execute(
                        """SELECT 1 FROM accounting_periods
                           WHERE start_date <= ? AND end_date >= ? LIMIT 1""",
                        (end.isoformat(), start.isoformat()),
                    ).fetchone()
                    if overlap:
                        raise ValueError("This date range overlaps an already closed period.")
                    transaction.execute(
                        """INSERT INTO accounting_periods(
                               start_date, end_date, closed_by, closed_at, reason
                           ) VALUES (?, ?, ?, ?, ?)""",
                        (
                            start.isoformat(),
                            end.isoformat(),
                            staff["id"],
                            datetime.now().astimezone().isoformat(timespec="seconds"),
                            reason.strip(),
                        ),
                    )
                    record_audit(
                        transaction,
                        staff["id"],
                        "Accounting period closed",
                        f"{start.isoformat()}..{end.isoformat()}",
                        reason.strip(),
                    )
                st.success("Accounting period closed.")
                st.rerun()
            except (ValueError, sqlite3.IntegrityError) as error:
                st.error(str(error) or "The accounting period could not be closed.")


def accounting_screen(staff):
    if staff.get("role") != "Owner":
        st.error("Only the Owner role can access the accounting module.")
        return
    st.title("Accounting")
    st.caption(
        "Accrual-basis, immutable double-entry accounting · "
        "All journal values are maintained in taka and poisha precision."
    )
    try:
        with accounting_database() as connection:
            ensure_accounting_schema(connection)
    except sqlite3.Error as error:
        st.error(f"Accounting schema could not be initialized: {error}")
        return

    with accounting_database() as connection:
        accounts = _account_rows(connection)
        posted_count = connection.execute(
            "SELECT COUNT(*) FROM accounting_journals"
        ).fetchone()[0]
        opening = connection.execute(
            "SELECT setting_value FROM accounting_settings WHERE setting_key = 'opening_journal_id'"
        ).fetchone()
        live_date = connection.execute(
            "SELECT setting_value FROM accounting_settings WHERE setting_key = 'go_live_date'"
        ).fetchone()["setting_value"]
        metrics = st.columns(4)
        metrics[0].metric("Accounts", len(accounts))
        metrics[1].metric("Posted journals", posted_count)
        metrics[2].metric("Opening balances", "Entered" if opening else "Not entered")
        metrics[3].metric("Accounting go-live", live_date)
        tabs = st.tabs(
            [
                "Reports",
                "Journal",
                "Chart of accounts",
                "Expenses & payables",
                "Fixed assets",
                "Periods",
            ]
        )
        with tabs[0]:
            _reporting_tab(connection)
        with tabs[1]:
            _manual_journal_tab(connection, staff)
        with tabs[2]:
            _accounts_tab(connection, staff)
        with tabs[3]:
            _expenses_and_payables_tab(connection, staff)
        with tabs[4]:
            _fixed_assets_tab(connection, staff)
        with tabs[5]:
            _periods_tab(connection, staff)

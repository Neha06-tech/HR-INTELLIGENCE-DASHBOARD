"""
generate_factpayroll.py

Generate a synthetic FactPayroll CSV from zenvy_hr_payroll_data.csv.

Produces: FactPayroll.csv (one or more monthly payroll rows per employee)
Derived fields:
 - PayrollDate (YYYY-MM-01)
 - PayPeriodStart, PayPeriodEnd
 - EmployeeID (generated if not present)
 - EmployeeKey (surrogate int)
 - BaseSalary
 - Attendance_Days
 - Overtime_Hours
 - Overtime_Pay
 - Gross_Salary
 - Deductions
 - Net_Salary
 - PaymentReference
 - IsDuplicatePayment (bool)
 - Employee_Status (Active / Inactive)

Usage example:
python generate_factpayroll.py \
  --input zenvy_hr_payroll_data.csv \
  --output FactPayroll.csv \
  --start-month 2025-12 \
  --months 1 \
  --workdays 22 \
  --overtime-multiplier 1.5 \
  --missing-attendance-pct 0.05 \
  --duplicate-pct 0.03 \
  --ghost-pct 0.02 \
  --overtime-abuse-pct 0.04 \
  --seed 42

Author: ChatGPT (generated)
"""

import argparse
import math
import uuid
from datetime import datetime
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser(description="Generate synthetic FactPayroll from employee CSV")
    p.add_argument("--input", required=True, help="Input employee CSV (zenvy_hr_payroll_data.csv)")
    p.add_argument("--output", default="FactPayroll.csv", help="Output payroll CSV")
    p.add_argument("--start-month", default=None, help="Start month YYYY-MM (default = last month)")
    p.add_argument("--months", type=int, default=1, help="Number of months to generate (default 1)")
    p.add_argument("--workdays", type=int, default=22, help="Working days in month (default 22)")
    p.add_argument("--overtime-multiplier", type=float, default=1.5, help="Overtime rate multiplier (default 1.5x)")
    p.add_argument("--missing-attendance-pct", type=float, default=0.05, help="Pct of employee-months with missing attendance (0-1)")
    p.add_argument("--duplicate-pct", type=float, default=0.03, help="Pct of employee-months that will receive a duplicate payment (0-1)")
    p.add_argument("--ghost-pct", type=float, default=0.02, help="Pct of employees to simulate as ghost candidates (Active with 0 attendance across months)")
    p.add_argument("--overtime-abuse-pct", type=float, default=0.04, help="Pct of employee-months to simulate as overtime-abuse (large OT hours)")
    p.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    return p.parse_args()


def month_range(start_month_str, months):
    if start_month_str:
        start = datetime.strptime(start_month_str + "-01", "%Y-%m-%d")
    else:
        # default to previous month
        today = datetime.today()
        first_of_this_month = datetime(today.year, today.month, 1)
        start = first_of_this_month - relativedelta(months=1)
    months_list = []
    for m in range(months):
        dt = start + relativedelta(months=m)
        months_list.append(dt)
    return months_list


def safe_div(a, b):
    return a / b if b else a


def main():
    args = parse_args()
    np.random.seed(args.seed)

    # Load employees
    df = pd.read_csv(args.input)

    # Basic clean / ensure Salary numeric
    if "Salary" not in df.columns:
        raise ValueError("Input CSV must contain 'Salary' column (monthly salary).")
    df["BaseSalary"] = pd.to_numeric(df["Salary"], errors="coerce").fillna(0)

    # Create EmployeeID / EmployeeKey
    if "EmployeeID" not in df.columns:
        # create synthetic EmployeeID using index + initials
        def make_eid(row, idx):
            fn = str(row.get("First Name", "") or row.get("FirstName", "") or "")
            ln = str(row.get("Last Name", "") or row.get("LastName", "") or "")
            initials = (fn[:1] + ln[:1]).upper() if fn or ln else ""
            return f"E{100000 + idx}_{initials}"

        df = df.reset_index(drop=True)
        df["EmployeeID"] = [make_eid(row, i) for i, row in df.iterrows()]

    df["EmployeeKey"] = np.arange(1, len(df) + 1)

    # Derive simple fields if not present
    if "Department" not in df.columns:
        df["Department"] = df.get("dept", "Unknown")
    if "Job Title" not in df.columns and "JobTitle" in df.columns:
        df["Job Title"] = df["JobTitle"]

    months = month_range(args.start_month, args.months)

    payroll_rows = []

    # Select ghost employee set (employees who will have repeated 0 attendance but paid)
    num_ghosts = int(round(len(df) * args.ghost_pct))
    ghost_employee_keys = set(np.random.choice(df["EmployeeKey"], size=num_ghosts, replace=False)) if num_ghosts > 0 else set()

    for month_dt in months:
        payroll_date = datetime(month_dt.year, month_dt.month, 1)  # set to first of month; can use month-end if desired
        pay_period_start = payroll_date
        pay_period_end = (payroll_date + relativedelta(months=1)) - relativedelta(days=1)

        # For each employee, simulate payroll row for this month
        for _, emp in df.iterrows():
            emp_key = int(emp["EmployeeKey"])
            base_salary = float(emp["BaseSalary"])
            # employment type not provided; assume full time for simulation
            employment_type = "Full-time"

            # Attendance Days simulation
            # Attendance factor influenced slightly by Years Of Experience if present
            yoe = 0
            for col in ["Years Of Experience", "YearsOfExperience", "Years Of Experience "]:
                if col in emp.index:
                    try:
                        yoe = float(emp[col])
                        break
                    except Exception:
                        yoe = 0
            # base attendance factor around 0.93-0.99 depending on randomness
            att_factor = np.random.normal(loc=0.95 + min(0.02, yoe * 0.002), scale=0.06)
            att_factor = float(np.clip(att_factor, 0.5, 1.0))
            attendance_days = int(round(args.workdays * att_factor))

            # If employee selected as ghost, force zero attendance for all months
            if emp_key in ghost_employee_keys:
                attendance_days = 0

            # Randomly apply missing attendance per employee-month
            if np.random.rand() < args.missing_attendance_pct:
                # decide between zero vs null: use zero to simulate ghost-like case, and NaN for tracking missing
                attendance_days = 0

            # Overtime Hours simulation
            # baseline: 70% zero to low OT (0-5), 25% moderate (6-20), remaining are higher
            r = np.random.rand()
            if r < 0.70:
                overtime_hours = float(np.random.poisson(1))  # many zeros/1-2 hours
            elif r < 0.95:
                overtime_hours = float(np.random.randint(6, 21))
            else:
                overtime_hours = float(np.random.randint(21, 41))

            # Inject overtime abuse cases (large OT)
            if np.random.rand() < args.overtime_abuse_pct:
                overtime_hours = float(np.random.randint(41, 101))  # abuse: 41-100 hours

            # Hourly rate and overtime pay
            monthly_work_hours = args.workdays * 8
            hourly_rate = safe_div(base_salary, monthly_work_hours) if monthly_work_hours > 0 else 0.0
            overtime_pay = overtime_hours * hourly_rate * args.overtime_multiplier

            # Gross Salary = Base + Overtime
            gross_salary = base_salary + overtime_pay

            # Deductions % by base salary band (simple progressive simulation)
            if base_salary < 7000:
                ded_pct = 0.12
            elif base_salary < 10000:
                ded_pct = 0.15
            elif base_salary < 14000:
                ded_pct = 0.18
            else:
                ded_pct = 0.22
            deductions = round(gross_salary * ded_pct, 2)

            net_salary = round(gross_salary - deductions, 2)

            # Employee status: default Active; small chance Inactive to simulate offboarded records
            emp_status = "Active" if np.random.rand() > 0.02 else "Inactive"

            payment_ref = str(uuid.uuid4())
            row = {
                "EmployeeKey": emp_key,
                "EmployeeID": emp.get("EmployeeID"),
                "FullName": f"{emp.get('First Name', '')} {emp.get('Last Name', '')}".strip(),
                "Department": emp.get("Department", ""),
                "JobTitle": emp.get("Job Title", emp.get("JobTitle", "")),
                "PayrollDate": payroll_date.strftime("%Y-%m-%d"),
                "PayPeriodStart": pay_period_start.strftime("%Y-%m-%d"),
                "PayPeriodEnd": pay_period_end.strftime("%Y-%m-%d"),
                "BaseSalary": round(base_salary, 2),
                "Attendance_Days": int(attendance_days) if not math.isnan(attendance_days) else None,
                "Overtime_Hours": round(overtime_hours, 2),
                "Overtime_Pay": round(overtime_pay, 2),
                "Gross_Salary": round(gross_salary, 2),
                "Deductions": deductions,
                "Net_Salary": net_salary,
                "PaymentReference": payment_ref,
                "IsDuplicatePayment": False,
                "Employee_Status": emp_status,
            }
            payroll_rows.append(row)

    payroll_df = pd.DataFrame(payroll_rows)

    # Introduce duplicate payments: select a subset of employee-months and add an extra payment row
    # We'll choose rows at random and duplicate them (with a distinct PaymentReference)
    total_rows = len(payroll_df)
    num_duplicates = int(round(total_rows * args.duplicate_pct))
    if num_duplicates > 0:
        dup_indices = np.random.choice(payroll_df.index, size=num_duplicates, replace=False)
        dup_rows = payroll_df.loc[dup_indices].copy()
        new_refs = [str(uuid.uuid4()) for _ in range(len(dup_rows))]
        dup_rows["PaymentReference"] = new_refs
        # slight variation in duplicate net salary (simulate manual adjustment)
        dup_rows["Net_Salary"] = dup_rows["Net_Salary"] + np.round(np.random.normal(loc=0, scale=5, size=len(dup_rows)), 2)
        dup_rows["IsDuplicatePayment"] = True
        # Append duplicates
        payroll_df = pd.concat([payroll_df, dup_rows], ignore_index=True)

    # Now set IsDuplicatePayment flag where employee has >1 payments in same month
    payroll_df["PayrollMonth"] = pd.to_datetime(payroll_df["PayrollDate"]).dt.to_period("M")
    dup_counts = payroll_df.groupby(["EmployeeKey", "PayrollMonth"]).size().reset_index(name="pcount")
    dup_map = dup_counts.set_index(["EmployeeKey", "PayrollMonth"]) ["pcount"].to_dict()
    payroll_df["IsDuplicatePayment"] = payroll_df.apply(
        lambda r: True if dup_map.get((r["EmployeeKey"], r["PayrollMonth"]), 0) > 1 else r["IsDuplicatePayment"],
        axis=1,
    )

    # Clean PayrollMonth column
    payroll_df.drop(columns=["PayrollMonth"], inplace=True)

    # Reorder columns for clarity
    cols = [
        "EmployeeKey",
        "EmployeeID",
        "FullName",
        "Employee_Status",
        "Department",
        "JobTitle",
        "PayrollDate",
        "PayPeriodStart",
        "PayPeriodEnd",
        "BaseSalary",
        "Attendance_Days",
        "Overtime_Hours",
        "Overtime_Pay",
        "Gross_Salary",
        "Deductions",
        "Net_Salary",
        "PaymentReference",
        "IsDuplicatePayment",
    ]
    payroll_df = payroll_df[cols]

    # Sort for readability
    payroll_df.sort_values(by=["PayrollDate", "Department", "EmployeeKey"], inplace=True)

    # Output CSV
    payroll_df.to_csv(args.output, index=False)
    print(f"Generated {len(payroll_df)} payroll rows across {args.months} month(s) -> {args.output}")


if __name__ == "__main__":
    main()

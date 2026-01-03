# KPI Definitions — ZENVY HR & Payroll Intelligence

This file provides clear KPI definitions, formulas (business language), fields used and interpretation for each KPI used on the dashboard. Use these as the canonical definitions for report cards and executive scorecards.

---

## Group A — Workforce KPIs

1. Total Employees (TotalEmployees)
- Definition: Number of distinct employees in the DimEmployee table (snapshot).
- Fields: EmployeeKey
- Business use: Measures total workforce size.

2. Active Employees (ActiveEmployees)
- Definition: Count of employees where Employee_Status = "Active".
- Fields: Employee_Status
- Business use: Basis for per-employee normalization of payroll metrics.

3. Inactive Employees (InactiveEmployees)
- Definition: Count where Employee_Status = "Inactive".
- Fields: Employee_Status
- Business use: Detects records that may still have payroll activity (audit interest).

4. Average Tenure (AvgTenureMonths)
- Definition: Average months from DateOfJoining to PayrollDate for active employees.
- Fields: DateOfJoining, PayrollDate
- Business use: Benchmarks experience and risk of attrition.

5. Average Attendance Days (AvgAttendanceDays)
- Definition: Average Attendance_Days for active employees during the pay period.
- Fields: Attendance_Days
- Business use: Operational attendance baseline for productivity and payroll normalization.

---

## Group B — Payroll KPIs

6. Total Gross Payroll (TotalGrossPayroll)
- Definition: Sum of Gross_Salary for the payroll period.
- Fields: Gross_Salary, PayrollDate
- Business use: Top-line payroll obligation before deductions and taxes.

7. Total Net Payroll (TotalNetPayroll)
- Definition: Sum of Net_Salary for the payroll period.
- Fields: Net_Salary, PayrollDate
- Business use: Actual cash outflow for payroll.

8. Total Deductions (TotalDeductions)
- Definition: Sum of Deductions across payroll rows for the period.
- Fields: Deductions
- Business use: Reconciliation to payroll ledger and review of benefits/tax application.

9. Average Net Salary (AvgNetSalary)
- Definition: Average Net_Salary for active employees in the period.
- Fields: Net_Salary
- Business use: Benchmark for compensation planning and affordability.

10. Gross-to-Net Ratio (GrossToNetRatio)
- Definition: TotalGrossPayroll / TotalNetPayroll.
- Fields: Gross_Salary, Net_Salary
- Business use: Shows the relative size of deductions; large changes may indicate policy or calculation issues.

---

## Group C — Overtime KPIs

11. Total Overtime Hours (TotalOvertimeHours)
- Definition: Sum of Overtime_Hours for the period.
- Fields: Overtime_Hours
- Business use: Quantifies extra work burden and potential cost drivers.

12. Average Overtime Hours per Employee (AvgOvertimeHoursPerEmp)
- Definition: TotalOvertimeHours / Count(employees with Overtime_Hours > 0).
- Fields: Overtime_Hours
- Business use: Reveals whether overtime is concentrated or spread across the workforce.

13. Total Overtime Cost (TotalOvertimeCost)
- Definition: Sum of Overtime_Pay for the period.
- Fields: Overtime_Pay
- Business use: Financial impact of overtime on payroll.

14. % Payroll from Overtime (PctPayrollOvertime)
- Definition: TotalOvertimeCost / TotalNetPayroll (percentage).
- Fields: Overtime_Pay, Net_Salary
- Business use: Shows if overtime is materially inflating payroll.

15. Overtime Abuse Count (OvertimeAbuseCount)
- Definition: Count of employees where Overtime_Hours exceed policy or are significant outliers vs department peers.
- Fields: Overtime_Hours, Department
- Business use: Operational control indicator to drive compliance actions.

---

## Group D — Risk & Compliance KPIs

16. Salary Leakage Amount (EstimatedLeakageAmount)
- Definition: Estimated sum of excess pay attributable to abnormal Net_Salary per attendance day after excluding legitimate overtime. Computed as sum(NetSalary - ExpectedNetBasedOnAttendance) for flagged employees.
- Fields: Net_Salary, Attendance_Days, JobTitle, Department, Overtime_Pay
- Business use: Quantifies suspected overpayments and helps prioritize recovery.

17. Salary Leakage Count (SalaryLeakageCount)
- Definition: Number of employees flagged for salary leakage (NetPerAttendanceDay > LeakageMultiplier * peer median).
- Fields: Net_Salary, Attendance_Days, Department, JobTitle
- Business use: Operational workload and risk sizing.

18. Ghost Employee Count (GhostEmployeeCount)
- Definition: Count of Active employees with zero or missing attendance and at least one Net_Salary payment in the pay period. High-confidence ghost label requires occurrence across N pay periods.
- Fields: Employee_Status, Attendance_Days, Net_Salary, Payment_Date
- Business use: Immediate audit priority for potential fraud or process breakdown.

19. Missing Attendance Count (MissingAttendanceCount)
- Definition: Number of salary-paid employees with Attendance_Days = 0 or NULL in the pay period.
- Fields: Attendance_Days, Net_Salary, PayrollDate
- Business use: Indicates payroll runs without attendance validation.

20. Duplicate Salary Credit Count (DuplicateSalaryCreditCount)
- Definition: Number of instances where an EmployeeKey has more than one payment recorded in the same pay period.
- Fields: EmployeeKey, PayrollDate, PaymentReference
- Business use: Immediate cash recovery priority and systemic control fix.

21. Average Net Salary per Attendance Day (AvgNetPerAttendanceDay)
- Definition: Average(Net_Salary / Attendance_Days) across the population (safe divide).
- Fields: Net_Salary, Attendance_Days
- Business use: Normalizes pay by presence to fairly compare roles.

22. Payroll Risk Score (AggregatedRiskScore)
- Definition: Weighted composite score per employee combining:
  - Salary leakage flag (weight 0.4)
  - Overtime abuse flag (weight 0.25)
  - Duplicate payment flag (weight 0.2)
  - Ghost/missing attendance flag (weight 0.15)
- Fields: Flags across risk categories
- Business use: Priority ranking to allocate investigative resources.

---

## Notes on thresholds and tuning

- All thresholds should be configurable by HR/Payroll owners; defaults recommended:
  - LeakageMultiplier = 1.5 (flag), 2.0 (high)
  - OvertimePolicyHoursPerMonth = 40 hours
  - OvertimeOutlierMultiplier = 1.5 (department median)
  - Ghost detection recurrence = 2 consecutive pay periods
- Use a rolling trailing window (3 months) to reduce false positives due to single-month anomalies.

---

## Example business formulas (plain language)

- NetPerAttendanceDay = Net_Salary / max(Attendance_Days, 1)
- Employee flagged for leakage if NetPerAttendanceDay > LeakageMultiplier * Median(NetPerAttendanceDay) for same Department+JobTitle
- Duplicate salary credit if count(Payments in same PayrollMonth for Employee) > 1
- Overtime abuse if Overtime_Hours > max(OvertimePolicyHoursPerMonth, OvertimeOutlierMultiplier * DeptMedianOvertime)

---

## Implementation guidance

- Implement KPI measures in Power BI using DAX and expose thresholds as slicers/parameters.
- Present risk KPIs both as counts and as estimated dollar impact to help leadership prioritize.
- Maintain an investigation log (simple table) to track status, owners and remediation outcomes for each flagged case.
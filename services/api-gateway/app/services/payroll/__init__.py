"""HR/Payroll service package.

Submodules:
    statutory   — Pure-function statutory calculators (no DB).
    seed_data   — Seed global statutory rates / leave types.
    engine      — 13-step monthly payroll calculation engine.
    gl_integration — Posts approved runs to the Finance GL.
    payslip     — Per-employee PDF payslip generator.
    leave       — Leave request workflow + unpaid-leave deductions.
    reports     — On-demand reports (P9, schedules, summaries).
"""

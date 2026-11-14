from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    auth,
    dashboard,
    search,
    patients,
    referrers,
    tests,
    invoices,
    payments,
    assignments,
    refunds,
    reports,
    business_day,
    profile,
    worklist,
    results,
    users,
    audit,
    reference_ranges,
    doctor_approvals,
    settings,
    doctor_balances,
    accounting,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(search.router, prefix="/search", tags=["Global Search"])
api_router.include_router(patients.router, prefix="/patients", tags=["Patients"])
api_router.include_router(referrers.router, prefix="/referrers", tags=["Referrers"])
api_router.include_router(tests.router, prefix="/tests", tags=["Tests & Destinations"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
api_router.include_router(payments.router, prefix="", tags=["Payments & Dues"])
api_router.include_router(assignments.router, prefix="/assignments", tags=["Assignments"])
api_router.include_router(refunds.router, prefix="/refunds", tags=["Refund Requests"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports & Delivery"])
api_router.include_router(business_day.router, prefix="/business-day", tags=["Business Day"])
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])
api_router.include_router(worklist.router, prefix="/worklist", tags=["Technician Worklist"])
api_router.include_router(results.router, prefix="/worklist", tags=["Result Entry & Report Data"])
api_router.include_router(users.router, prefix="/users", tags=["User Management"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Log (read only)"])
api_router.include_router(reference_ranges.router, prefix="/reference-ranges", tags=["Reference Ranges (D24)"])
api_router.include_router(doctor_approvals.router, prefix="/doctor-approvals", tags=["Doctor Sign-off (D22)"])
api_router.include_router(settings.router, prefix="/settings", tags=["Center Settings"])
api_router.include_router(doctor_balances.router, prefix="/doctor-balances", tags=["Doctor Balances (D43)"])
api_router.include_router(accounting.router, prefix="/accounting", tags=["Accounting (Module 21)"])

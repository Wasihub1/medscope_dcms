import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import select, delete
from backend.app.core.database import SessionLocal
from backend.app.core.timezone import utc_now
from backend.app.core.lab_sections import section_from_text
from backend.app.models import (
    Tenant,
    Staff,
    Patient,
    Visit,
    Referrer,
    Test,
    TestDestination,
    Invoice,
    InvoiceLine,
    Payment,
    TestOrder,
    AssignmentHistory,
    Sample,
    ReportVersion,
    ReportDelivery,
    RefundRequest,
    BusinessDay,
    BusinessDayChannelBalance,
    SequenceCounter,
    AuditLog,
)


def seed_development_data():
    db = SessionLocal()
    tenant_id = "center-seba-01"
    print("=" * 60)
    print("Seeding MedScope Receptionist Development Data into PostgreSQL...")
    print(f"Target Tenant: {tenant_id}")

    try:
        # 1. Tenant
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            tenant = Tenant(
                id=tenant_id,
                name="Seba Diagnostic Center (সেবা ডায়াগনস্টিক সেন্টার)",
                slug="seba-diagnostic",
                active=True,
                created_at=utc_now() - timedelta(days=60),
            )
            db.add(tenant)
            db.flush()

        # 2. Staff Identities
        staff_data = [
            {"id": 1, "username": "reception_fatima", "display_name": "Fatima Akter (ফাতিমা আক্তার)", "role": "RECEPTIONIST", "department": "Front Desk", "email": "fatima@sebadiagnostic.com", "phone": "01711000111", "address": "Front Desk Office, Ground Floor"},
            {"id": 2, "username": "admin_tariq", "display_name": "Tariqul Islam (তারিকুল ইসলাম)", "role": "ADMIN", "department": "Administration", "email": "tariq@sebadiagnostic.com", "phone": "01711000222", "address": "Admin Suite 201"},
            {"id": 3, "username": "tech_kamal", "display_name": "Kamal Hossain (কামাল হোসেন)", "role": "LAB_TECH", "department": "Hematology", "email": "kamal@sebadiagnostic.com", "phone": "01711000333", "address": "Pathology Lab 102"},
            {"id": 4, "username": "tech_nasrin", "display_name": "Nasrin Sultana (নাসরিন সুলতানা)", "role": "LAB_TECH", "department": "Biochemical Tests", "email": "nasrin@sebadiagnostic.com", "phone": "01711000444", "address": "Biochemistry Lab 103"},
        ]
        for s in staff_data:
            st = db.get(Staff, s["id"])
            if not st:
                st = Staff(
                    id=s["id"],
                    tenant_id=tenant_id,
                    username=s["username"],
                    display_name=s["display_name"],
                    role=s["role"],
                    department=s["department"],
                    # Prompt 10E: a LAB_TECH always belongs to a lab room
                    lab_section=section_from_text(s["department"]) if s["role"] == "LAB_TECH" else None,
                    email=s["email"],
                    phone=s["phone"],
                    address=s["address"],
                    active=True,
                )
                db.add(st)
            else:
                st.department = s["department"]
                if st.role == "LAB_TECH" and not st.lab_section:
                    st.lab_section = section_from_text(s["department"])
        db.flush()

        # 3. Test Destinations
        destinations = [
            {"name": "Hematology Room 101", "destination_type": "Room", "department": "Hematology"},
            {"name": "Biochemistry Room 102", "destination_type": "Room", "department": "Biochemical Tests"},
            {"name": "Ultrasonography Room 204", "destination_type": "Room", "department": "Ultrasonogram"},
            {"name": "Microbiology Lab 105", "destination_type": "Lab", "department": "Microbiology"},
            {"name": "Kamal Hossain (Tech)", "destination_type": "Technician", "department": "Hematology"},
            {"name": "Nasrin Sultana (Tech)", "destination_type": "Technician", "department": "Biochemical Tests"},
        ]
        for d in destinations:
            exists = db.execute(select(TestDestination).where(TestDestination.tenant_id == tenant_id, TestDestination.name == d["name"])).scalar_one_or_none()
            if not exists:
                db.add(TestDestination(tenant_id=tenant_id, **d))
        db.flush()

        # 4. Master Tests Catalog (25 tests across multiple departments with Prompt 05 readiness fields)
        tests_data = [
            {"code": "CBC", "name": "Complete Blood Count (CBC with ESR)", "short_name": "CBC", "department": "Hematology", "price": 400, "sample_type": "Whole Blood (EDTA)", "default_assignee": "Hematology Room 101", "turnaround_hours": 4, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "HGB", "name": "Hemoglobin (Hb%)", "short_name": "Hb%", "department": "Hematology", "price": 150, "sample_type": "Whole Blood (EDTA)", "default_assignee": "Hematology Room 101", "turnaround_hours": 2, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "BTCT", "name": "Bleeding & Clotting Time (BT/CT)", "short_name": "BT/CT", "department": "Hematology", "price": 200, "sample_type": "Blood", "default_assignee": "Hematology Room 101", "turnaround_hours": 2, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "RBS", "name": "Random Blood Sugar (RBS)", "short_name": "RBS", "department": "Biochemical Tests", "price": 150, "sample_type": "Fluoride Blood", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 2, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "FBS", "name": "Fasting Blood Sugar (FBS)", "short_name": "FBS", "department": "Biochemical Tests", "price": 150, "sample_type": "Fluoride Blood", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 2, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "HBA1C", "name": "Glycated Hemoglobin (HbA1c)", "short_name": "HbA1c", "department": "Biochemical Tests", "price": 800, "sample_type": "Whole Blood (EDTA)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 4, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "LIPID", "name": "Lipid Profile (Fasting)", "short_name": "Lipid Profile", "department": "Biochemical Tests", "price": 900, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 6, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "CREAT", "name": "Serum Creatinine", "short_name": "S. Creatinine", "department": "Biochemical Tests", "price": 350, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 3, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "UREA", "name": "Serum Blood Urea", "short_name": "S. Urea", "department": "Biochemical Tests", "price": 300, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 3, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "SGPT", "name": "Serum ALT / SGPT", "short_name": "SGPT", "department": "Biochemical Tests", "price": 350, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 4, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "SGOT", "name": "Serum AST / SGOT", "short_name": "SGOT", "department": "Biochemical Tests", "price": 350, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 4, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "BILI", "name": "Serum Bilirubin (Total & Direct)", "short_name": "S. Bilirubin", "department": "Biochemical Tests", "price": 300, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 3, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "ELC", "name": "Serum Electrolytes (Na+, K+, Cl-)", "short_name": "S. Electrolytes", "department": "Biochemical Tests", "price": 1000, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 4, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "URINE", "name": "Urine Routine Examination (R/E)", "short_name": "Urine R/E", "department": "Clinical Pathology", "price": 200, "sample_type": "Fresh Midstream Urine", "default_assignee": None, "turnaround_hours": 3, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "STOOL", "name": "Stool Routine Examination (R/E)", "short_name": "Stool R/E", "department": "Clinical Pathology", "price": 200, "sample_type": "Fresh Stool", "default_assignee": None, "turnaround_hours": 3, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "TSH", "name": "Thyroid Stimulating Hormone (TSH)", "short_name": "TSH", "department": "Serology", "price": 600, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 6, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "FT4", "name": "Free Thyroxine (FT4)", "short_name": "FT4", "department": "Serology", "price": 700, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 6, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "HBSAG", "name": "HBsAg (Screening / Rapid)", "short_name": "HBsAg", "department": "Serology", "price": 350, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 4, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "HIV", "name": "HIV I & II (Screening)", "short_name": "HIV", "department": "Serology", "price": 500, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 4, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "WIDAL", "name": "Widal Test (Typhoid)", "short_name": "Widal", "department": "Serology", "price": 350, "sample_type": "Serum (Plain Tube)", "default_assignee": "Biochemistry Room 102", "turnaround_hours": 4, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "NUMERIC_TABLE", "approval_rule": "TECHNICIAN_FINAL"},
            {"code": "USG_W_A", "name": "USG of Whole Abdomen", "short_name": "USG Whole Abdomen", "department": "Ultrasonogram", "price": 1200, "sample_type": None, "default_assignee": "Ultrasonography Room 204", "turnaround_hours": 2, "performing_role": "DOCTOR", "requires_doctor": True, "report_template": "NARRATIVE", "approval_rule": "DOCTOR_REQUIRED"},
            {"code": "USG_L_A", "name": "USG of Lower Abdomen", "short_name": "USG Lower Abdomen", "department": "Ultrasonogram", "price": 800, "sample_type": None, "default_assignee": "Ultrasonography Room 204", "turnaround_hours": 2, "performing_role": "DOCTOR", "requires_doctor": True, "report_template": "NARRATIVE", "approval_rule": "DOCTOR_REQUIRED"},
            {"code": "USG_PREG", "name": "USG of Pregnancy Profile", "short_name": "USG Pregnancy", "department": "Ultrasonogram", "price": 1000, "sample_type": None, "default_assignee": "Ultrasonography Room 204", "turnaround_hours": 2, "performing_role": "DOCTOR", "requires_doctor": True, "report_template": "NARRATIVE", "approval_rule": "DOCTOR_REQUIRED"},
            {"code": "URINE_C_S", "name": "Urine Culture and Sensitivity (C/S)", "short_name": "Urine C/S", "department": "Microbiology", "price": 800, "sample_type": "Sterile Midstream Urine", "default_assignee": "Microbiology Lab 105", "turnaround_hours": 48, "performing_role": "LAB_TECH", "requires_doctor": False, "report_template": "CULTURE_SENSITIVITY", "approval_rule": "BOTH_SIGNATURES"},
            {"code": "XRAY_CHEST", "name": "X-Ray Chest P/A View", "short_name": "CXR P/A", "department": "Radiology & Imaging", "price": 500, "sample_type": None, "default_assignee": None, "turnaround_hours": 4, "performing_role": "DOCTOR", "requires_doctor": True, "report_template": "NARRATIVE", "approval_rule": "DOCTOR_REQUIRED"},
        ]
        test_map = {}
        for t in tests_data:
            existing_t = db.execute(select(Test).where(Test.tenant_id == tenant_id, Test.code == t["code"])).scalar_one_or_none()
            if not existing_t:
                new_t = Test(tenant_id=tenant_id, active=True, **t)
                db.add(new_t)
                db.flush()
                test_map[t["code"]] = new_t
            else:
                for k, v in t.items():
                    setattr(existing_t, k, v)
                test_map[t["code"]] = existing_t
        db.flush()

        # 5. Referrers (10 doctors of varied specialties)
        referrers_data = [
            {"name": "Prof. Dr. M. A. Rahim (অধ্যাপক ডাঃ এম এ রহিম)", "referrer_type": "Professor", "phone": "01819112233", "registration_no": "BMDC-12345", "specialty": "Internal Medicine", "chamber_address": "Seba Diagnostic, Room 201"},
            {"name": "Dr. Anwara Begum (ডাঃ আনোয়ারা বেগম)", "referrer_type": "Consultant", "phone": "01712334455", "registration_no": "BMDC-23456", "specialty": "Gynecology & Obstetrics", "chamber_address": "Popular Medical Center, Floor 2"},
            {"name": "Dr. S. M. Faruk (ডাঃ এস এম ফারুক)", "referrer_type": "Assistant Professor", "phone": "01911556677", "registration_no": "BMDC-34567", "specialty": "Cardiology", "chamber_address": "National Heart Chamber"},
            {"name": "Dr. Kazi Mahbub (ডাঃ কাজী মাহবুব)", "referrer_type": "Medical Officer", "phone": "01611778899", "registration_no": "BMDC-45678", "specialty": "General Medicine", "chamber_address": "Upazila Health Complex"},
            {"name": "Dr. Nusrat Jahan (ডাঃ নুসরাত জাহান)", "referrer_type": "Registrar", "phone": "01715998877", "registration_no": "BMDC-56789", "specialty": "Pediatrics (শিশু বিভাগ)", "chamber_address": "Child Health Care Center"},
            {"name": "Dr. Zahirul Haque (ডাঃ জহিরুল হক)", "referrer_type": "Associate Professor", "phone": "01817665544", "registration_no": "BMDC-67890", "specialty": "Orthopedic Surgery", "chamber_address": "Trauma & Bone Center"},
            {"name": "Dr. Shamsun Nahar (ডাঃ শামসুন নাহার)", "referrer_type": "Consultant", "phone": "01912443322", "registration_no": "BMDC-78901", "specialty": "Sonology & Imaging", "chamber_address": "Seba Ultrasound Wing"},
            {"name": "Dr. Golam Sarwar (ডাঃ গোলাম সারওয়ার)", "referrer_type": "Consultant", "phone": "01511223344", "registration_no": "BMDC-89012", "specialty": "Dermatology (চর্ম ও যৌন)", "chamber_address": "Skin & Laser Center"},
            {"name": "Hospital Self-Referral / Walk-In (সরাসরি আগত রোগী)", "referrer_type": "Institution", "phone": "01700000000", "registration_no": "NONE", "specialty": "General Outpatient", "chamber_address": "Reception Desk"},
            {"name": "Upazila Community Clinic (উপজেলা কমিউনিটি ক্লিনিক)", "referrer_type": "Clinic", "phone": "01800000000", "registration_no": "NONE", "specialty": "Primary Health Referral", "chamber_address": "Sector 4, Ward 2"},
        ]
        referrer_map = {}
        for r in referrers_data:
            existing_r = db.execute(select(Referrer).where(Referrer.tenant_id == tenant_id, Referrer.name == r["name"])).scalar_one_or_none()
            if not existing_r:
                new_r = Referrer(tenant_id=tenant_id, active=True, commission_type="PERCENTAGE", commission_rate=20, **r)
                db.add(new_r)
                db.flush()
                referrer_map[r["name"]] = new_r
            else:
                referrer_map[r["name"]] = existing_r
        db.flush()

        # 6. Patients (12 realistic patients, bilingual, family phone sharing)
        patients_data = [
            {"code": "PID-000001", "name": "Mohammad Rahim Ullah (মোঃ রহিম উল্লাহ)", "phone": "01711223344", "address": "Village: Bagherpara, Thana: Bagherpara, Jashore", "gender": "Male"},
            {"code": "PID-000002", "name": "Rokeya Begum (রোকেয়া বেগম)", "phone": "01711223344", "address": "Village: Bagherpara, Thana: Bagherpara, Jashore", "gender": "Female"}, # Shares family phone
            {"code": "PID-000003", "name": "Master Tanvir Hasan (তানভীর হাসান)", "phone": "01711223344", "address": "Village: Bagherpara, Thana: Bagherpara, Jashore", "gender": "Male"}, # Child shares phone
            {"code": "PID-000004", "name": "Abdul Alim (আব্দুল আলিম)", "phone": "01819556677", "address": "Holding 42, Hospital Road, Sadar, Jashore", "gender": "Male"},
            {"code": "PID-000005", "name": "Sufia Khatun (সুফিয়া খাতুন)", "phone": "01912667788", "address": "Station Road, Railgate, Jashore", "gender": "Female"},
            {"code": "PID-000006", "name": "Kamrul Islam (কামরুল ইসলাম)", "phone": "01611889900", "address": "Chowrasta Bazar, Keshabpur, Jashore", "gender": "Male"},
            {"code": "PID-000007", "name": "Salma Akter (সালমা আক্তার)", "phone": "01715443322", "address": "College Road, Manirampur, Jashore", "gender": "Female"},
            {"code": "PID-000008", "name": "Biplob Chandra Roy (বিপ্লব চন্দ্র রায়)", "phone": "01812334411", "address": "Palpara, Sadar, Jashore", "gender": "Male"},
            {"code": "PID-000009", "name": "Tasnim Farhana (তাসনিম ফারহানা)", "phone": "01911776655", "address": "Housing Estate, Block B, Jashore", "gender": "Female"},
            {"code": "PID-000010", "name": "Nur Mohammad (নুর মোহাম্মদ)", "phone": "01718990011", "address": "Ghonapara, Abhaynagar, Jashore", "gender": "Male"},
            {"code": "PID-000011", "name": "Parvin Sultana (পারভীন সুলতানা)", "phone": "01814223355", "address": "New Market Area, Jashore", "gender": "Female"},
            {"code": "PID-000012", "name": "Abdur Razzak (আব্দুর রাজ্জাক)", "phone": "01915667799", "address": "Dhopapara, Chanchra, Jashore", "gender": "Male"},
        ]
        patient_map = {}
        for p in patients_data:
            existing_p = db.execute(select(Patient).where(Patient.tenant_id == tenant_id, Patient.patient_code == p["code"])).scalar_one_or_none()
            if not existing_p:
                new_p = Patient(
                    tenant_id=tenant_id,
                    patient_code=p["code"],
                    name=p["name"],
                    phone=p["phone"],
                    phone_last4=p["phone"][-4:],
                    address=p["address"],
                    gender=p["gender"],
                    created_at=utc_now() - timedelta(days=15),
                )
                db.add(new_p)
                db.flush()
                patient_map[p["code"]] = new_p
            else:
                patient_map[p["code"]] = existing_p
        db.flush()

        # 7. Sequence Counters
        seq_names = ["invoice", "patient", "visit", "report"]
        for sname in seq_names:
            seq = db.execute(select(SequenceCounter).where(SequenceCounter.tenant_id == tenant_id, SequenceCounter.name == sname)).scalar_one_or_none()
            if not seq:
                init_val = 12 if sname == "patient" else (10 if sname == "invoice" else 15)
                db.add(SequenceCounter(tenant_id=tenant_id, name=sname, current_value=init_val))
        db.flush()

        # 8. Business Day (Active Open Session #14)
        active_day = db.execute(select(BusinessDay).where(BusinessDay.tenant_id == tenant_id, BusinessDay.status == "OPEN")).scalar_one_or_none()
        if not active_day:
            active_day = BusinessDay(
                tenant_id=tenant_id,
                day_number=14,
                opened_at=utc_now() - timedelta(hours=6),
                opened_by_id=1,
                opening_float=5000,
                status="OPEN",
                notes="Morning shift opened by Fatima Akter with Tk 5,000 cash drawer float.",
            )
            db.add(active_day)
            db.flush()
            channels = [
                ("CASH", 5000, 14500),
                ("BKASH", 0, 3200),
                ("NAGAD", 0, 1500),
                ("BANK_TRANSFER", 0, 2800),
                ("POS_CARD", 0, 4500),
            ]
            for ch, op_bal, rec_amt in channels:
                db.add(BusinessDayChannelBalance(
                    tenant_id=tenant_id,
                    business_day_id=active_day.id,
                    channel=ch,
                    opening_balance=op_bal,
                    received_amount=rec_amt,
                ))
            db.flush()

        # 9. Invoices & Workflow Scenarios
        # Scenario A: Invoice SD-000001 (Fully PAID, CBC + RBS + Lipid, Delivered)
        inv1 = db.execute(select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.invoice_no == "SD-000001")).scalar_one_or_none()
        if not inv1:
            p1 = patient_map["PID-000001"]
            ref1 = list(referrer_map.values())[0]
            v1 = Visit(tenant_id=tenant_id, patient_id=p1.id, visit_number="VIS-000001", age_value=48, age_unit="years", age_days=17520.0, gender=p1.gender, created_by_id=1, created_at=utc_now() - timedelta(days=3))
            db.add(v1)
            db.flush()

            inv1 = Invoice(
                tenant_id=tenant_id, visit_id=v1.id, patient_id=p1.id, invoice_no="SD-000001", referrer_id=ref1.id,
                status="CONFIRMED", payment_status="PAID", gross=1450, discount=150, net=1300, paid=1300, due=0, refund_due=0,
                created_at=utc_now() - timedelta(days=3), created_by_id=1
            )
            db.add(inv1)
            db.flush()

            # Lines: CBC (400 - 50 = 350), RBS (150 - 0 = 150), LIPID (900 - 100 = 800) -> Net 1300
            l1 = InvoiceLine(tenant_id=tenant_id, invoice_id=inv1.id, test_id=test_map["CBC"].id, test_code_snapshot="CBC", test_name_snapshot="Complete Blood Count", department_snapshot="Hematology", unit_price_snapshot=400, discount_type="AMOUNT", discount_value=50, discount_amount=50, net_price=350, status="CONFIRMED", created_at=inv1.created_at)
            l2 = InvoiceLine(tenant_id=tenant_id, invoice_id=inv1.id, test_id=test_map["RBS"].id, test_code_snapshot="RBS", test_name_snapshot="Random Blood Sugar", department_snapshot="Biochemical Tests", unit_price_snapshot=150, discount_type="NONE", discount_value=0, discount_amount=0, net_price=150, status="CONFIRMED", created_at=inv1.created_at)
            l3 = InvoiceLine(tenant_id=tenant_id, invoice_id=inv1.id, test_id=test_map["LIPID"].id, test_code_snapshot="LIPID", test_name_snapshot="Lipid Profile", department_snapshot="Biochemical Tests", unit_price_snapshot=900, discount_type="AMOUNT", discount_value=100, discount_amount=100, net_price=800, status="CONFIRMED", created_at=inv1.created_at)
            db.add_all([l1, l2, l3])
            db.flush()

            # Payment
            pmt1 = Payment(tenant_id=tenant_id, invoice_id=inv1.id, business_day_id=active_day.id, amount=1300, method="CASH", received_at=inv1.created_at, received_by_id=1)
            db.add(pmt1)

            # Test Orders & Completed Reports
            for line in [l1, l2, l3]:
                torder = TestOrder(tenant_id=tenant_id, invoice_line_id=line.id, status="COMPLETED", assigned_destination="Biochemistry Room 102", assigned_at=inv1.created_at, assigned_by_id=1)
                db.add(torder)
                db.flush()
                smp = Sample(tenant_id=tenant_id, test_order_id=torder.id, sample_code=f"SMP-SD-000001-{line.id}", sample_type="Blood", status="COLLECTED", collected_at=inv1.created_at + timedelta(minutes=15), collected_by_id=3)
                db.add(smp)
                rep = ReportVersion(tenant_id=tenant_id, test_order_id=torder.id, report_no=f"RPT-SD000001-{line.id}", version=1, status="FINAL_AUTHORIZED", authorized=True, findings_summary="All parameters within normal clinical ranges.", issued_at=inv1.created_at + timedelta(hours=4), issued_by_id=3)
                db.add(rep)
                db.flush()
                # Report Delivered
                deliv = ReportDelivery(tenant_id=tenant_id, report_version_id=rep.id, delivered_to_name="Rahim Ullah", delivered_to_phone="01711223344", delivered_to_relation="Self", delivered_with_due=False, delivered_at=inv1.created_at + timedelta(hours=6), delivered_by_id=1)
                db.add(deliv)

        # Scenario B: Invoice SD-000002 (Partly Paid, DUE Tk 800, Report READY but HELD DUE TO BALANCE)
        inv2 = db.execute(select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.invoice_no == "SD-000002")).scalar_one_or_none()
        if not inv2:
            p2 = patient_map["PID-000004"]
            ref2 = list(referrer_map.values())[1]
            v2 = Visit(tenant_id=tenant_id, patient_id=p2.id, visit_number="VIS-000002", age_value=55, age_unit="years", age_days=20075.0, gender=p2.gender, created_by_id=1, created_at=utc_now() - timedelta(days=1))
            db.add(v2)
            db.flush()

            inv2 = Invoice(
                tenant_id=tenant_id, visit_id=v2.id, patient_id=p2.id, invoice_no="SD-000002", referrer_id=ref2.id,
                status="CONFIRMED", payment_status="PARTLY_PAID", gross=1800, discount=0, net=1800, paid=1000, due=800, refund_due=0,
                created_at=utc_now() - timedelta(days=1), created_by_id=1
            )
            db.add(inv2)
            db.flush()

            l2_1 = InvoiceLine(tenant_id=tenant_id, invoice_id=inv2.id, test_id=test_map["ELC"].id, test_code_snapshot="ELC", test_name_snapshot="Serum Electrolytes", department_snapshot="Biochemical Tests", unit_price_snapshot=1000, discount_type="NONE", discount_value=0, discount_amount=0, net_price=1000, status="CONFIRMED", created_at=inv2.created_at)
            l2_2 = InvoiceLine(tenant_id=tenant_id, invoice_id=inv2.id, test_id=test_map["HBA1C"].id, test_code_snapshot="HBA1C", test_name_snapshot="HbA1c Glycated Hemoglobin", department_snapshot="Biochemical Tests", unit_price_snapshot=800, discount_type="NONE", discount_value=0, discount_amount=0, net_price=800, status="CONFIRMED", created_at=inv2.created_at)
            db.add_all([l2_1, l2_2])
            db.flush()

            pmt2 = Payment(tenant_id=tenant_id, invoice_id=inv2.id, business_day_id=active_day.id, amount=1000, method="BKASH", reference="TRX9876543210", received_at=inv2.created_at, received_by_id=1)
            db.add(pmt2)

            # Orders completed with authorized reports but NO delivery (Held on Due)
            for line in [l2_1, l2_2]:
                torder = TestOrder(tenant_id=tenant_id, invoice_line_id=line.id, status="COMPLETED", assigned_destination="Biochemistry Room 102", assigned_at=inv2.created_at, assigned_by_id=1)
                db.add(torder)
                db.flush()
                smp = Sample(tenant_id=tenant_id, test_order_id=torder.id, sample_code=f"SMP-SD-000002-{line.id}", sample_type="Serum", status="COLLECTED", collected_at=inv2.created_at + timedelta(minutes=20), collected_by_id=4)
                db.add(smp)
                rep = ReportVersion(tenant_id=tenant_id, test_order_id=torder.id, report_no=f"RPT-SD000002-{line.id}", version=1, status="FINAL_AUTHORIZED", authorized=True, findings_summary="HbA1c: 7.2% (Moderate glycemic control).", issued_at=inv2.created_at + timedelta(hours=3), issued_by_id=4)
                db.add(rep)

        # Scenario C: Invoice SD-000003 (UNASSIGNED Orders: Urine R/E and Stool R/E)
        inv3 = db.execute(select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.invoice_no == "SD-000003")).scalar_one_or_none()
        if not inv3:
            p3 = patient_map["PID-000005"]
            v3 = Visit(tenant_id=tenant_id, patient_id=p3.id, visit_number="VIS-000003", age_value=32, age_unit="years", age_days=11680.0, gender=p3.gender, created_by_id=1, created_at=utc_now() - timedelta(hours=4))
            db.add(v3)
            db.flush()

            inv3 = Invoice(
                tenant_id=tenant_id, visit_id=v3.id, patient_id=p3.id, invoice_no="SD-000003", referrer_id=None,
                status="CONFIRMED", payment_status="PAID", gross=400, discount=0, net=400, paid=400, due=0, refund_due=0,
                created_at=utc_now() - timedelta(hours=4), created_by_id=1
            )
            db.add(inv3)
            db.flush()

            l3_1 = InvoiceLine(tenant_id=tenant_id, invoice_id=inv3.id, test_id=test_map["URINE"].id, test_code_snapshot="URINE", test_name_snapshot="Urine Routine Examination", department_snapshot="Clinical Pathology", unit_price_snapshot=200, discount_type="NONE", discount_value=0, discount_amount=0, net_price=200, status="CONFIRMED", created_at=inv3.created_at)
            l3_2 = InvoiceLine(tenant_id=tenant_id, invoice_id=inv3.id, test_id=test_map["STOOL"].id, test_code_snapshot="STOOL", test_name_snapshot="Stool Routine Examination", department_snapshot="Clinical Pathology", unit_price_snapshot=200, discount_type="NONE", discount_value=0, discount_amount=0, net_price=200, status="CONFIRMED", created_at=inv3.created_at)
            db.add_all([l3_1, l3_2])
            db.flush()

            pmt3 = Payment(tenant_id=tenant_id, invoice_id=inv3.id, business_day_id=active_day.id, amount=400, method="CASH", received_at=inv3.created_at, received_by_id=1)
            db.add(pmt3)

            # Orders are explicitly UNASSIGNED (no destination)
            to3_1 = TestOrder(tenant_id=tenant_id, invoice_line_id=l3_1.id, status="UNASSIGNED", assigned_destination=None)
            to3_2 = TestOrder(tenant_id=tenant_id, invoice_line_id=l3_2.id, status="UNASSIGNED", assigned_destination=None)
            db.add_all([to3_1, to3_2])

        # Scenario D: Invoice SD-000004 (Uncollected Test with PENDING Refund Request)
        inv4 = db.execute(select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.invoice_no == "SD-000004")).scalar_one_or_none()
        if not inv4:
            p4 = patient_map["PID-000006"]
            v4 = Visit(tenant_id=tenant_id, patient_id=p4.id, visit_number="VIS-000004", age_value=40, age_unit="years", age_days=14600.0, gender=p4.gender, created_by_id=1, created_at=utc_now() - timedelta(hours=2))
            db.add(v4)
            db.flush()

            inv4 = Invoice(
                tenant_id=tenant_id, visit_id=v4.id, patient_id=p4.id, invoice_no="SD-000004", referrer_id=None,
                status="CONFIRMED", payment_status="PAID", gross=700, discount=0, net=700, paid=700, due=0, refund_due=0,
                created_at=utc_now() - timedelta(hours=2), created_by_id=1
            )
            db.add(inv4)
            db.flush()

            l4_1 = InvoiceLine(tenant_id=tenant_id, invoice_id=inv4.id, test_id=test_map["FT4"].id, test_code_snapshot="FT4", test_name_snapshot="Free Thyroxine (FT4)", department_snapshot="Serology", unit_price_snapshot=700, discount_type="NONE", discount_value=0, discount_amount=0, net_price=700, status="CONFIRMED", created_at=inv4.created_at)
            db.add(l4_1)
            db.flush()

            pmt4 = Payment(tenant_id=tenant_id, invoice_id=inv4.id, business_day_id=active_day.id, amount=700, method="CASH", received_at=inv4.created_at, received_by_id=1)
            db.add(pmt4)

            to4 = TestOrder(tenant_id=tenant_id, invoice_line_id=l4_1.id, status="ASSIGNED", assigned_destination="Biochemistry Room 102", assigned_at=inv4.created_at, assigned_by_id=1)
            db.add(to4)
            db.flush()

            # Refund Request: PENDING_ADMIN_APPROVAL (No sample taken yet)
            ref_req = RefundRequest(
                tenant_id=tenant_id,
                invoice_id=inv4.id,
                invoice_line_id=l4_1.id,
                amount=700,
                reason="Patient informed fasting was broken by breakfast before reporting to lab. Requested test cancellation.",
                status="PENDING_ADMIN_APPROVAL",
                requested_by_id=1,
                requested_at=utc_now() - timedelta(minutes=45),
            )
            db.add(ref_req)

        # Scenario E: Invoice SD-000005 (DUE Tk 1,200 for USG, Ready for Delivery)
        inv5 = db.execute(select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.invoice_no == "SD-000005")).scalar_one_or_none()
        if not inv5:
            p5 = patient_map["PID-000007"]
            ref5 = list(referrer_map.values())[2]
            v5 = Visit(tenant_id=tenant_id, patient_id=p5.id, visit_number="VIS-000005", age_value=27, age_unit="years", age_days=9855.0, gender=p5.gender, created_by_id=1, created_at=utc_now() - timedelta(hours=3))
            db.add(v5)
            db.flush()

            inv5 = Invoice(
                tenant_id=tenant_id, visit_id=v5.id, patient_id=p5.id, invoice_no="SD-000005", referrer_id=ref5.id,
                status="CONFIRMED", payment_status="UNPAID", gross=1200, discount=0, net=1200, paid=0, due=1200, refund_due=0,
                created_at=utc_now() - timedelta(hours=3), created_by_id=1
            )
            db.add(inv5)
            db.flush()

            l5 = InvoiceLine(tenant_id=tenant_id, invoice_id=inv5.id, test_id=test_map["USG_W_A"].id, test_code_snapshot="USG_W_A", test_name_snapshot="USG of Whole Abdomen", department_snapshot="Ultrasonogram", unit_price_snapshot=1200, discount_type="NONE", discount_value=0, discount_amount=0, net_price=1200, status="CONFIRMED", created_at=inv5.created_at)
            db.add(l5)
            db.flush()

            to5 = TestOrder(tenant_id=tenant_id, invoice_line_id=l5.id, status="COMPLETED", assigned_destination="Ultrasonography Room 204", assigned_at=inv5.created_at, assigned_by_id=1)
            db.add(to5)
            db.flush()

            rep5 = ReportVersion(tenant_id=tenant_id, test_order_id=to5.id, report_no=f"RPT-SD000005-{l5.id}", version=1, status="FINAL_AUTHORIZED", authorized=True, findings_summary="Liver: Normal size and echotexture. Gall bladder: Normal, no calculi seen.", issued_at=inv5.created_at + timedelta(hours=1), issued_by_id=3)
            db.add(rep5)

        # Scenario F: Invoice SD-000006 (STAT Urgent CBC for Kamal Hossain - Hematology, Ordered 5h ago with 4h TAT -> Late!)
        inv6 = db.execute(select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.invoice_no == "SD-000006")).scalar_one_or_none()
        if not inv6:
            p6 = patient_map["PID-000008"]
            v6 = Visit(tenant_id=tenant_id, patient_id=p6.id, visit_number="VIS-000006", age_value=35, age_unit="years", age_days=12775.0, gender=p6.gender, created_by_id=1, created_at=utc_now() - timedelta(hours=5))
            db.add(v6)
            db.flush()

            inv6 = Invoice(
                tenant_id=tenant_id, visit_id=v6.id, patient_id=p6.id, invoice_no="SD-000006", referrer_id=None,
                status="CONFIRMED", payment_status="PAID", gross=400, discount=0, net=400, paid=400, due=0, refund_due=0,
                urgent=True, created_at=utc_now() - timedelta(hours=5), created_by_id=1
            )
            db.add(inv6)
            db.flush()

            l6 = InvoiceLine(
                tenant_id=tenant_id, invoice_id=inv6.id, test_id=test_map["CBC"].id,
                test_code_snapshot="CBC", test_name_snapshot="Complete Blood Count (CBC with ESR)",
                department_snapshot="Hematology", unit_price_snapshot=400, discount_type="NONE",
                discount_value=0, discount_amount=0, net_price=400, urgent=True, status="CONFIRMED",
                created_at=inv6.created_at
            )
            db.add(l6)
            db.flush()

            pmt6 = Payment(tenant_id=tenant_id, invoice_id=inv6.id, business_day_id=active_day.id, amount=400, method="CASH", received_at=inv6.created_at, received_by_id=1)
            db.add(pmt6)

            to6 = TestOrder(
                tenant_id=tenant_id, invoice_line_id=l6.id, status="ASSIGNED", urgent=True,
                department="Hematology", performing_role="LAB_TECH", turnaround_hours=4, sample_route="QUICK",
                assigned_to_id=3, assigned_destination="Kamal Hossain (Tech)", assigned_at=inv6.created_at,
                assigned_by_id=1, created_at=inv6.created_at
            )
            db.add(to6)
            db.flush()

            hist6 = AssignmentHistory(
                tenant_id=tenant_id, test_order_id=to6.id, previous_assignee="SYSTEM",
                new_assignee="Kamal Hossain (Tech)", reason="Automatic department routing (Hematology)",
                changed_by_id=1, changed_at=inv6.created_at
            )
            db.add(hist6)

        # Scenario G: Invoice SD-000007 (In Progress RBS & LIPID for Nasrin Sultana - Biochemistry, Sample Collected)
        inv7 = db.execute(select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.invoice_no == "SD-000007")).scalar_one_or_none()
        if not inv7:
            p7 = patient_map["PID-000009"]
            v7 = Visit(tenant_id=tenant_id, patient_id=p7.id, visit_number="VIS-000007", age_value=42, age_unit="years", age_days=15330.0, gender=p7.gender, created_by_id=1, created_at=utc_now() - timedelta(minutes=90))
            db.add(v7)
            db.flush()

            inv7 = Invoice(
                tenant_id=tenant_id, visit_id=v7.id, patient_id=p7.id, invoice_no="SD-000007", referrer_id=None,
                status="CONFIRMED", payment_status="PAID", gross=1050, discount=50, net=1000, paid=1000, due=0, refund_due=0,
                urgent=False, created_at=utc_now() - timedelta(minutes=90), created_by_id=1
            )
            db.add(inv7)
            db.flush()

            l7_1 = InvoiceLine(
                tenant_id=tenant_id, invoice_id=inv7.id, test_id=test_map["RBS"].id,
                test_code_snapshot="RBS", test_name_snapshot="Random Blood Sugar (RBS)",
                department_snapshot="Biochemical Tests", unit_price_snapshot=150, discount_type="NONE",
                discount_value=0, discount_amount=0, net_price=150, urgent=False, status="CONFIRMED",
                created_at=inv7.created_at
            )
            l7_2 = InvoiceLine(
                tenant_id=tenant_id, invoice_id=inv7.id, test_id=test_map["LIPID"].id,
                test_code_snapshot="LIPID", test_name_snapshot="Lipid Profile (Fasting)",
                department_snapshot="Biochemical Tests", unit_price_snapshot=900, discount_type="AMOUNT",
                discount_value=50, discount_amount=50, net_price=850, urgent=False, status="CONFIRMED",
                created_at=inv7.created_at
            )
            db.add_all([l7_1, l7_2])
            db.flush()

            pmt7 = Payment(tenant_id=tenant_id, invoice_id=inv7.id, business_day_id=active_day.id, amount=1000, method="CASH", received_at=inv7.created_at, received_by_id=1)
            db.add(pmt7)

            # Test order 1: RBS
            to7_1 = TestOrder(
                tenant_id=tenant_id, invoice_line_id=l7_1.id, status="IN_PROGRESS", urgent=False,
                department="Biochemical Tests", performing_role="LAB_TECH", turnaround_hours=2, sample_route="QUICK",
                assigned_to_id=4, assigned_destination="Nasrin Sultana (Tech)", assigned_at=inv7.created_at,
                assigned_by_id=1, created_at=inv7.created_at
            )
            # Test order 2: LIPID
            to7_2 = TestOrder(
                tenant_id=tenant_id, invoice_line_id=l7_2.id, status="IN_PROGRESS", urgent=False,
                department="Biochemical Tests", performing_role="LAB_TECH", turnaround_hours=6, sample_route="QUICK",
                assigned_to_id=4, assigned_destination="Nasrin Sultana (Tech)", assigned_at=inv7.created_at,
                assigned_by_id=1, created_at=inv7.created_at
            )
            db.add_all([to7_1, to7_2])
            db.flush()

            # Samples collected 45 mins ago
            smp7_1 = Sample(
                tenant_id=tenant_id, test_order_id=to7_1.id, sample_code=f"SMP-SD-000007-{l7_1.id}",
                sample_type="Fluoride Blood", status="COLLECTED", collected_at=utc_now() - timedelta(minutes=45),
                collected_by_id=4
            )
            smp7_2 = Sample(
                tenant_id=tenant_id, test_order_id=to7_2.id, sample_code=f"SMP-SD-000007-{l7_2.id}",
                sample_type="Serum (Plain Tube)", status="COLLECTED", collected_at=utc_now() - timedelta(minutes=45),
                collected_by_id=4
            )
            db.add_all([smp7_1, smp7_2])

        # Scenario H: Invoice SD-000008 (USG Awaiting Doctor for Visiting Sonologist)
        inv8 = db.execute(select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.invoice_no == "SD-000008")).scalar_one_or_none()
        if not inv8:
            p8 = patient_map["PID-000010"]
            v8 = Visit(tenant_id=tenant_id, patient_id=p8.id, visit_number="VIS-000008", age_value=50, age_unit="years", age_days=18250.0, gender=p8.gender, created_by_id=1, created_at=utc_now() - timedelta(minutes=40))
            db.add(v8)
            db.flush()

            inv8 = Invoice(
                tenant_id=tenant_id, visit_id=v8.id, patient_id=p8.id, invoice_no="SD-000008", referrer_id=None,
                status="CONFIRMED", payment_status="PAID", gross=1000, discount=0, net=1000, paid=1000, due=0, refund_due=0,
                urgent=False, created_at=utc_now() - timedelta(minutes=40), created_by_id=1
            )
            db.add(inv8)
            db.flush()

            l8 = InvoiceLine(
                tenant_id=tenant_id, invoice_id=inv8.id, test_id=test_map["USG_PREG"].id,
                test_code_snapshot="USG_PREG", test_name_snapshot="USG of Pregnancy Profile",
                department_snapshot="Ultrasonogram", unit_price_snapshot=1000, discount_type="NONE",
                discount_value=0, discount_amount=0, net_price=1000, urgent=False, status="CONFIRMED",
                created_at=inv8.created_at
            )
            db.add(l8)
            db.flush()

            pmt8 = Payment(tenant_id=tenant_id, invoice_id=inv8.id, business_day_id=active_day.id, amount=1000, method="CASH", received_at=inv8.created_at, received_by_id=1)
            db.add(pmt8)

            to8 = TestOrder(
                tenant_id=tenant_id, invoice_line_id=l8.id, status="AWAITING_DOCTOR", urgent=False,
                department="Ultrasonogram", performing_role="DOCTOR", turnaround_hours=2, sample_route="QUICK",
                assigned_to_id=None, assigned_destination="Ultrasonography Room 204", assigned_at=inv8.created_at,
                assigned_by_id=1, created_at=inv8.created_at
            )
            db.add(to8)

        db.commit()
        print("Development seed data successfully committed!")
        print("  - 1 Tenant: Seba Diagnostic Center")
        print("  - 4 Staff (Receptionist Fatima Akter, Admin Tariqul Islam, 2 Technicians)")
        print("  - 25 Master Diagnostic Tests")
        print("  - 6 Assignment Destinations")
        print("  - 10 Medical Referrers")
        print("  - 12 Patients (Bilingual with shared family phone)")
        print("  - 1 Active Open Business Day (#14) with channel balances")
        print("  - 5 Rich Invoices spanning Paid, Due, Unassigned, Pending Refund, and Delivery Held scenarios")
        print("=" * 60)
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_development_data()


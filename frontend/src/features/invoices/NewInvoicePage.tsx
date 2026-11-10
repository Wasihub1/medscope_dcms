import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Search,
  UserPlus,
  UserCheck,
  Stethoscope,
  Trash2,
  AlertCircle,
  Receipt,
  Printer,
  CheckCircle2,
  Plus,
  Clock,
  Sparkles,
  Users,
  ShieldCheck,
  ArrowRight,
} from 'lucide-react';
import { api } from '../../api/client';
import { Patient, Referrer, TestItem, Invoice, DiscountType, PaymentChannel, Gender } from '../../types';
import { Modal } from '../../components/common/Modal';
import { Badge } from '../../components/common/Badge';
import { DualCopyInvoiceModal, PreviewInvoiceData } from '../../components/common/DualCopyInvoiceModal';
import { useToast } from '../../context/ToastContext';

interface SelectedTestLine {
  test: TestItem;
  price: number;
  is_urgent: boolean;
  urgent_fee: number;
  discount_type: DiscountType;
  discount_value: number;
}

export const NewInvoicePage: React.FC = () => {
  const navigate = useNavigate();
  const { showToast } = useToast();

  // 1. Patient State
  const [patientSearch, setPatientSearch] = useState('');
  const [patientResults, setPatientResults] = useState<Patient[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [patientModalOpen, setPatientModalOpen] = useState(false);
  const [newPatient, setNewPatient] = useState<{
    full_name: string;
    phone: string;
    alternate_phone: string;
    gender: Gender;
    age_years: number | '';
    age_months: number | '';
    address: string;
    blood_group: string;
  }>({
    full_name: '',
    phone: '',
    alternate_phone: '',
    gender: 'MALE',
    age_years: '',
    age_months: '',
    address: '',
    blood_group: '',
  });

  // 2. Prescribed By (Doctor Only) State
  const [prescribedBySearch, setPrescribedBySearch] = useState('');
  const [prescribedByResults, setPrescribedByResults] = useState<Referrer[]>([]);
  const [selectedPrescribedBy, setSelectedPrescribedBy] = useState<Referrer | null>(null);
  const [doctorModalOpen, setDoctorModalOpen] = useState(false);
  const [newDoctor, setNewDoctor] = useState({
    name: '',
    degree: '',
    specialty: '',
    phone: '',
    institution: '',
    type: 'Doctor',
    commission_rate: '' as number | '',
    commission_type: 'PERCENT',
  });

  // 3. Referred By (Doctor / Third Party) State
  const [referrerSearch, setReferrerSearch] = useState('');
  const [referrerResults, setReferrerResults] = useState<Referrer[]>([]);
  const [selectedReferrer, setSelectedReferrer] = useState<Referrer | null>(null);
  const [referrerModalOpen, setReferrerModalOpen] = useState(false);
  const [newReferrer, setNewReferrer] = useState({
    name: '',
    type: 'Agent',
    degree: '',
    specialty: '',
    phone: '',
    institution: '',
    commission_rate: '' as number | '',
    commission_type: 'PERCENT',
  });

  // 4. Tests Catalogue State
  const [testSearch, setTestSearch] = useState('');
  const [testCategory, setTestCategory] = useState<string>('ALL');
  const [testCatalog, setTestCatalog] = useState<TestItem[]>([]);
  const [selectedLines, setSelectedLines] = useState<SelectedTestLine[]>([]);

  // 5. Master Discount State
  const [masterDiscountType, setMasterDiscountType] = useState<DiscountType>('NONE');
  const [masterDiscountValue, setMasterDiscountValue] = useState<number>(0);

  // 6. Payment Intake State — Item 05: Default Paid Amount = 0
  const [paymentChannel, setPaymentChannel] = useState<PaymentChannel>('CASH');
  const [paidAmount, setPaidAmount] = useState<number>(0);
  const [tenderedAmount, setTenderedAmount] = useState<number>(0);
  const [referenceNo, setReferenceNo] = useState<string>('');
  const [notes, setNotes] = useState<string>('');

  // 7. Preview & Save Modal State (Item 06 & Item 07)
  const [previewOpen, setPreviewOpen] = useState(false);
  const [savedModalOpen, setSavedModalOpen] = useState(false);
  const [previewData, setPreviewData] = useState<PreviewInvoiceData | null>(null);
  const [savedInvoice, setSavedInvoice] = useState<Invoice | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Load Test Catalog
  useEffect(() => {
    const loadTests = async () => {
      try {
        const tests = await api.getTests();
        setTestCatalog(tests);
      } catch (err: any) {
        showToast({ type: 'error', title: 'Failed to load test catalog', message: err.message });
      }
    };
    loadTests();
  }, []);

  // Search Patients Debounce
  useEffect(() => {
    if (!patientSearch.trim()) {
      setPatientResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.getPatients(patientSearch.trim());
        setPatientResults(res);
      } catch (err) {
        console.error('Patient search failed:', err);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [patientSearch]);

  // Search Prescribed By (Doctor only) Debounce
  useEffect(() => {
    if (!prescribedBySearch.trim()) {
      setPrescribedByResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.getReferrers(prescribedBySearch.trim(), 'Doctor');
        setPrescribedByResults(res);
      } catch (err) {
        console.error('Prescriber search failed:', err);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [prescribedBySearch]);

  // Search Referred By (Doctor or Third Party) Debounce
  useEffect(() => {
    if (!referrerSearch.trim()) {
      setReferrerResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.getReferrers(referrerSearch.trim());
        setReferrerResults(res);
      } catch (err) {
        console.error('Referrer search failed:', err);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [referrerSearch]);

  // Financial Calculations
  const grossAmount = selectedLines.reduce((sum, line) => sum + line.price, 0);
  const urgentFeesTotal = selectedLines.reduce((sum, line) => sum + (line.is_urgent ? line.urgent_fee : 0), 0);

  // Line discounts - capped at test price (up to 100%), no negative line payable
  const calculatedLineDiscounts = selectedLines.map((line) => {
    if (masterDiscountType !== 'NONE') return 0; // Superseded if master discount active
    if (line.discount_type === 'PERCENT') {
      const pct = Math.min(Math.max(0, line.discount_value), 100);
      return Math.min(line.price, Math.round((line.price * pct) / 100));
    } else if (line.discount_type === 'FIXED') {
      return Math.min(Math.max(0, line.discount_value), line.price);
    }
    return 0;
  });

  const lineDiscountTotal =
    masterDiscountType === 'NONE' ? calculatedLineDiscounts.reduce((sum, val) => sum + val, 0) : 0;

  // Master discount - capped at grossAmount (up to 100%)
  let masterDiscountAmount = 0;
  if (masterDiscountType === 'PERCENT') {
    const pct = Math.min(Math.max(0, masterDiscountValue), 100);
    masterDiscountAmount = Math.round((grossAmount * pct) / 100);
  } else if (masterDiscountType === 'FIXED') {
    masterDiscountAmount = Math.min(Math.max(0, masterDiscountValue), grossAmount);
  }

  const totalDiscount = masterDiscountType !== 'NONE' ? masterDiscountAmount : lineDiscountTotal;
  const netPayable = Math.max(0, grossAmount + urgentFeesTotal - totalDiscount);
  const dueAmount = Math.max(0, netPayable - paidAmount);
  const changeAmount = Math.max(0, tenderedAmount - paidAmount);

  // URL parameters handling
  const [searchParams] = useSearchParams();
  const patientIdParam = searchParams.get('patient_id');
  const testIdParam = searchParams.get('test_id');

  useEffect(() => {
    if (patientIdParam && !selectedPatient) {
      api.getPatient(patientIdParam).then((p) => {
        if (p) setSelectedPatient(p);
      }).catch((err) => console.error('Failed to preselect patient:', err));
    }
  }, [patientIdParam]);

  useEffect(() => {
    if (testIdParam && testCatalog.length > 0) {
      const match = testCatalog.find((t) => String(t.id) === String(testIdParam));
      if (match) {
        handleAddTest(match);
      }
    }
  }, [testIdParam, testCatalog]);

  // Handle Add Test
  const handleAddTest = (test: TestItem) => {
    if (selectedLines.some((l) => l.test.id === test.id)) {
      showToast({ type: 'warning', title: 'Already Added', message: `${test.name} is already in the invoice.` });
      return;
    }
    const testPrice = test.default_price || (test as any).price || 0;
    const newLine: SelectedTestLine = {
      test: {
        ...test,
        default_price: testPrice,
        discount_cap_percent: 100,
      },
      price: testPrice,
      is_urgent: false,
      urgent_fee: 0,
      discount_type: 'NONE',
      discount_value: 0,
    };
    setSelectedLines((prev) => [...prev, newLine]);
    setTestSearch('');
  };

  const handleToggleUrgent = (index: number) => {
    setSelectedLines((prev) =>
      prev.map((line, idx) => {
        if (idx !== index) return line;
        const nextUrgent = !line.is_urgent;
        const fee = nextUrgent ? Math.max(100, Math.round(line.price * 0.2)) : 0;
        return { ...line, is_urgent: nextUrgent, urgent_fee: fee };
      })
    );
  };

  // Synchronized discount helpers for line items (Item 04: Distinct % and ৳ inputs)
  const handleLinePercentChange = (index: number, rawVal: string) => {
    setSelectedLines((prev) =>
      prev.map((line, idx) => {
        if (idx !== index) return line;
        const trimmed = (rawVal ?? '').toString().trim();
        if (trimmed === '') {
          return { ...line, discount_type: 'NONE', discount_value: 0 };
        }
        const num = Number(trimmed);
        if (isNaN(num) || num <= 0) {
          return { ...line, discount_type: 'NONE', discount_value: 0 };
        }
        const maxPct = line.test?.discount_cap_percent ?? 100;
        const pct = Math.min(maxPct, Math.max(0, Math.round(num)));
        return { ...line, discount_type: 'PERCENT', discount_value: pct };
      })
    );
  };

  const handleLineAmountChange = (index: number, rawVal: string) => {
    setSelectedLines((prev) =>
      prev.map((line, idx) => {
        if (idx !== index) return line;
        const trimmed = (rawVal ?? '').toString().trim();
        if (trimmed === '') {
          return { ...line, discount_type: 'NONE', discount_value: 0 };
        }
        const num = Number(trimmed);
        if (isNaN(num) || num <= 0) {
          return { ...line, discount_type: 'NONE', discount_value: 0 };
        }
        const maxPct = line.test?.discount_cap_percent ?? 100;
        const maxAmt = Math.min(line.price, Math.round((line.price * maxPct) / 100));
        const amt = Math.min(maxAmt, Math.max(0, Math.round(num)));
        return { ...line, discount_type: 'FIXED', discount_value: amt };
      })
    );
  };

  const getLineDisplayDiscounts = (line: SelectedTestLine) => {
    if (line.discount_type === 'PERCENT') {
      const pct = line.discount_value;
      const amt = line.price > 0 ? Math.min(line.price, Math.round((line.price * pct) / 100)) : 0;
      return {
        pct: pct > 0 ? String(pct) : '',
        amt: amt > 0 ? String(amt) : '',
      };
    } else if (line.discount_type === 'FIXED') {
      const amt = line.discount_value;
      const pct = line.price > 0 ? Math.min(100, Math.round((amt / line.price) * 100)) : 0;
      return {
        pct: pct > 0 ? String(pct) : '',
        amt: amt > 0 ? String(amt) : '',
      };
    }
    return { pct: '', amt: '' };
  };

  // Synchronized discount mode change for Master Discount (Item 04)
  const handleMasterDiscountTypeChange = (newType: DiscountType) => {
    if (newType === 'NONE') {
      setMasterDiscountType('NONE');
      setMasterDiscountValue(0);
      return;
    }
    let newValue = masterDiscountValue;
    if (masterDiscountType === 'PERCENT' && newType === 'FIXED') {
      const pct = Math.min(100, Math.max(0, masterDiscountValue));
      newValue = Math.min(grossAmount, Math.round((grossAmount * pct) / 100));
    } else if (masterDiscountType === 'FIXED' && newType === 'PERCENT') {
      const amt = Math.min(grossAmount, Math.max(0, masterDiscountValue));
      newValue = grossAmount > 0 ? Math.min(100, Math.round((amt / grossAmount) * 100)) : 0;
    }
    setMasterDiscountType(newType);
    setMasterDiscountValue(newValue);
  };

  const handleMasterDiscountValueChange = (val: number) => {
    let safeVal = Math.max(0, val);
    if (masterDiscountType === 'PERCENT') {
      safeVal = Math.min(100, safeVal);
    } else if (masterDiscountType === 'FIXED') {
      safeVal = Math.min(grossAmount, safeVal);
    }
    setMasterDiscountValue(safeVal);
  };

  const handleRemoveLine = (index: number) => {
    setSelectedLines((prev) => prev.filter((_, idx) => idx !== index));
  };

  // Quick Payment buttons (Item 05)
  const handleSetFullPayment = () => {
    setPaidAmount(netPayable);
    setTenderedAmount(netPayable);
  };

  const handleSetZeroPayment = () => {
    setPaidAmount(0);
    setTenderedAmount(0);
  };

  // Create Patient Handler
  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPatient.full_name || !newPatient.phone) {
      showToast({ type: 'error', title: 'Missing fields', message: 'Name and phone are required.' });
      return;
    }
    try {
      const created = await api.createPatient({
        full_name: newPatient.full_name,
        phone: newPatient.phone,
        alternate_phone: newPatient.alternate_phone || null,
        gender: newPatient.gender,
        age_years: newPatient.age_years ? Number(newPatient.age_years) : null,
        age_months: newPatient.age_months ? Number(newPatient.age_months) : null,
        address: newPatient.address || null,
        blood_group: newPatient.blood_group || null,
      });
      setSelectedPatient(created);
      setPatientModalOpen(false);
      showToast({ type: 'success', title: 'Patient Created', message: `${created.full_name} (${created.mrn})` });
    } catch (err: any) {
      showToast({ type: 'error', title: 'Creation Failed', message: err.message });
    }
  };

  // Create Doctor (Prescriber) Handler with write-only commission
  const handleCreateDoctor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDoctor.name) {
      showToast({ type: 'error', title: 'Missing fields', message: 'Doctor name is required.' });
      return;
    }
    try {
      const payload: any = {
        name: newDoctor.name,
        degree: newDoctor.degree || null,
        specialty: newDoctor.specialty || null,
        phone: newDoctor.phone || null,
        institution: newDoctor.institution || null,
        type: 'Doctor',
      };
      if (newDoctor.commission_rate !== '') {
        payload.commission_rate = Number(newDoctor.commission_rate);
        payload.commission_type = newDoctor.commission_type;
      }
      const created = await api.createReferrer(payload);
      setSelectedPrescribedBy(created);
      setDoctorModalOpen(false);
      showToast({
        type: 'success',
        title: 'Doctor Added',
        message: `${created.name} (${created.code}) selected as Prescriber.`,
      });
      setNewDoctor({
        name: '',
        degree: '',
        specialty: '',
        phone: '',
        institution: '',
        type: 'Doctor',
        commission_rate: '',
        commission_type: 'PERCENT',
      });
    } catch (err: any) {
      showToast({ type: 'error', title: 'Doctor Creation Failed', message: err.message });
    }
  };

  // Create Referrer (Third Party / Doctor) Handler with write-only commission
  const handleCreateReferrer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newReferrer.name) {
      showToast({ type: 'error', title: 'Missing fields', message: 'Referrer name is required.' });
      return;
    }
    try {
      const payload: any = {
        name: newReferrer.name,
        type: newReferrer.type,
        degree: newReferrer.degree || null,
        specialty: newReferrer.specialty || null,
        phone: newReferrer.phone || null,
        institution: newReferrer.institution || null,
      };
      if (newReferrer.commission_rate !== '') {
        payload.commission_rate = Number(newReferrer.commission_rate);
        payload.commission_type = newReferrer.commission_type;
      }
      const created = await api.createReferrer(payload);
      setSelectedReferrer(created);
      setReferrerModalOpen(false);
      showToast({
        type: 'success',
        title: 'Referrer Added',
        message: `${created.name} (${created.code}) selected as Referrer.`,
      });
      setNewReferrer({
        name: '',
        type: 'Agent',
        degree: '',
        specialty: '',
        phone: '',
        institution: '',
        commission_rate: '',
        commission_type: 'PERCENT',
      });
    } catch (err: any) {
      showToast({ type: 'error', title: 'Referrer Creation Failed', message: err.message });
    }
  };

  // Item 06: Generate Preview (non-final, does not submit or allocate bill #)
  const handleGeneratePreview = () => {
    if (!selectedPatient) {
      showToast({ type: 'warning', title: 'Missing Patient', message: 'Please select or register a patient.' });
      return;
    }
    if (selectedLines.length === 0) {
      showToast({ type: 'warning', title: 'No Tests Selected', message: 'Please add at least one investigation.' });
      return;
    }
    if (paidAmount < 0 || paidAmount > netPayable) {
      showToast({ type: 'error', title: 'Invalid Payment', message: 'Paid amount cannot exceed Net Payable.' });
      return;
    }

    const linesPreview = selectedLines.map((line, idx) => {
      const disc = calculatedLineDiscounts[idx] || 0;
      return {
        test_id: Number(line.test.id),
        test_name: line.test.name || (line.test as any).test_name || (line.test as any).test_name_snapshot || 'Investigation',
        department: line.test.department || (line.test as any).department_snapshot || '',
        price: line.price,
        is_urgent: line.is_urgent,
        urgent_fee: line.is_urgent ? line.urgent_fee : 0,
        discount_amount: disc,
        net_amount: Math.max(0, line.price + (line.is_urgent ? line.urgent_fee : 0) - disc),
      };
    });

    const preview: PreviewInvoiceData = {
      patient_name: selectedPatient.full_name,
      patient_mrn: selectedPatient.mrn,
      patient_phone: selectedPatient.phone,
      patient_gender: selectedPatient.gender,
      patient_age_display: selectedPatient.age_years ? `${selectedPatient.age_years}y` : undefined,
      prescribed_by_name: selectedPrescribedBy?.name || 'Self / Walk-in',
      referrer_name: selectedReferrer?.name || 'Self / Walk-in',
      lines: linesPreview,
      gross_amount: grossAmount,
      urgent_fee_total: urgentFeesTotal,
      line_discount_total: lineDiscountTotal,
      master_discount_amount: masterDiscountAmount,
      total_discount: totalDiscount,
      net_amount: netPayable,
      paid_amount: paidAmount,
      due_amount: dueAmount,
      payment_channel: paymentChannel,
      reference_no: referenceNo,
      notes: notes,
    };

    setPreviewData(preview);
    setPreviewOpen(true);
  };

  // Item 06 & Item 07: Save / Save & Print Invoice (final persistence + clean reset)
  const handleCommitInvoice = async (triggerPrintAfterSave: boolean) => {
    if (!selectedPatient || selectedLines.length === 0) return;
    setSubmitting(true);
    try {
      const payload = {
        patient_id: Number(selectedPatient.id),
        prescribed_by_id: selectedPrescribedBy ? Number(selectedPrescribedBy.id) : null,
        referrer_id: selectedReferrer ? Number(selectedReferrer.id) : null,
        notes: notes || null,
        master_discount_type: masterDiscountType,
        master_discount_value: masterDiscountValue,
        lines: selectedLines.map((line) => ({
          test_id: Number(line.test.id),
          is_urgent: line.is_urgent,
          discount_type: line.discount_type,
          discount_value: line.discount_value,
        })),
        initial_payment:
          paidAmount > 0
            ? {
                amount: paidAmount,
                channel: paymentChannel,
                reference_no: referenceNo || null,
                notes: 'Reception desk initial payment',
              }
            : null,
      };

      const result = await api.createInvoice(payload);
      setSavedInvoice(result);
      setPreviewOpen(false);
      setSavedModalOpen(true);

      showToast({
        type: 'success',
        title: 'Invoice Created!',
        message: `Bill #${result.invoice_number} saved successfully.`,
      });

      // Item 07: Clean reset of invoice form ONLY after successful persistence
      setSelectedPatient(null);
      setSelectedPrescribedBy(null);
      setSelectedReferrer(null);
      setSelectedLines([]);
      setMasterDiscountType('NONE');
      setMasterDiscountValue(0);
      setPaidAmount(0);
      setTenderedAmount(0);
      setReferenceNo('');
      setNotes('');

      if (triggerPrintAfterSave) {
        setTimeout(() => {
          window.print();
        }, 300);
      }
    } catch (err: any) {
      showToast({ type: 'error', title: 'Invoice Creation Failed', message: err.message });
      // On failure, preserve current state intact
    } finally {
      setSubmitting(false);
    }
  };

  // Item 03: Selected test filtering — Once added, removed from autocomplete / suggestions
  const selectedTestIds = new Set(selectedLines.map((l) => l.test.id));
  const filteredTests = testCatalog.filter((t) => {
    // Deduplication rule: exclude if already selected
    if (selectedTestIds.has(t.id)) return false;
    const matchesSearch =
      !testSearch ||
      t.name.toLowerCase().includes(testSearch.toLowerCase()) ||
      t.code.toLowerCase().includes(testSearch.toLowerCase());
    const matchesCategory = testCategory === 'ALL' || t.department.toUpperCase() === testCategory.toUpperCase();
    return matchesSearch && matchesCategory;
  });

  const departments = ['ALL', ...Array.from(new Set(testCatalog.map((t) => t.department)))];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1B1B0E]">New Patient Diagnostic Intake</h1>
          <p className="text-xs text-[#6D6A60]">
            Generate invoice, configure independent prescriber/referrer, apply discounts, and record payments.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/invoices')}
            className="px-3 py-1.5 text-xs font-semibold text-[#54524A] bg-[#FAF9F6] border border-[#DCDAD4] hover:bg-[#F4F3F0] rounded-xl transition-colors cursor-pointer"
          >
            Cancel / Back to Invoices
          </button>
        </div>
      </div>

      {/* Main 2-Column Intake Grid: First column truncated by 10% to 48%, space granted to second column (52%) */}
      <div className="grid grid-cols-1 lg:grid-cols-[48%_1fr] gap-5">
        {/* Left Column: Patient, Prescriber & Referrer, and Test Catalog (48%) */}
        <div className="space-y-4">
          {/* 1. Patient Selection Box */}
          <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-4.5 shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#525333] flex items-center gap-1.5">
                <UserCheck className="w-4 h-4 text-[#CF8852]" />
                1. Patient Information *
              </span>
              <button
                type="button"
                data-testid="new-patient-btn"
                onClick={() => setPatientModalOpen(true)}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-[#FAF3EC] text-[#96572A] border border-[#E6C4A7] hover:bg-[#F3E4D6] rounded-lg transition-colors cursor-pointer"
              >
                <UserPlus className="w-3.5 h-3.5 text-[#CF8852]" />
                New Patient
              </button>
            </div>

            {selectedPatient ? (
              <div className="flex items-center justify-between p-3 bg-[#F2F3EC] border border-[#C2C6A4] rounded-xl">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-[#1B1B0E]" data-testid="selected-patient-name">
                      {selectedPatient.full_name}
                    </span>
                    <Badge variant="neutral" size="sm">
                      {selectedPatient.mrn}
                    </Badge>
                  </div>
                  <p className="text-xs text-[#444529] mt-0.5">
                    Phone: {selectedPatient.phone} | Gender: {selectedPatient.gender} | Age:{' '}
                    {selectedPatient.age_years ? `${selectedPatient.age_years}y` : '-'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedPatient(null)}
                  className="text-xs text-[#9C2417] hover:underline font-semibold cursor-pointer"
                >
                  Change
                </button>
              </div>
            ) : (
              <div className="relative">
                <div className="flex items-center gap-2 px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
                  <Search className="w-4 h-4 text-[#8E8A7E]" />
                  <input
                    type="text"
                    data-testid="patient-search-input"
                    value={patientSearch}
                    onChange={(e) => setPatientSearch(e.target.value)}
                    placeholder="Search existing patient by Name, Phone, or MRN..."
                    className="w-full text-xs bg-transparent border-none outline-none text-[#1B1B0E]"
                  />
                </div>
                {patientResults.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-[#DCDAD4] rounded-xl shadow-lg z-30 divide-y divide-[#E8E7E3]">
                    {patientResults.map((p) => (
                      <div
                        key={p.id}
                        data-testid={`patient-result-${p.id}`}
                        onClick={() => {
                          setSelectedPatient(p);
                          setPatientSearch('');
                          setPatientResults([]);
                        }}
                        className="p-2.5 hover:bg-[#FAF3EC] cursor-pointer text-xs flex justify-between items-center"
                      >
                        <div>
                          <span className="font-semibold text-[#1B1B0E]">{p.full_name}</span>
                          <span className="text-[#6D6A60] ml-2">({p.phone})</span>
                        </div>
                        <Badge variant="neutral" size="sm">
                          {p.mrn}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Merged 2. Prescribed By & 3. Referred By Consolidated Box (Aligned Controls) */}
          <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-3.5 shadow-xs">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
              {/* Left Sub-form: 2. Prescribed By (Doctor Only) */}
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 h-5">
                  <Stethoscope className="w-3.5 h-3.5 text-[#CF8852]" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#525333]">
                    2. Prescribed By (Doctor Only)
                  </span>
                </div>

                {selectedPrescribedBy ? (
                  <div className="flex items-center justify-between px-3 h-9 bg-white border border-[#DCDAD4] rounded-xl shadow-2xs">
                    <div className="flex items-center gap-2 min-w-0 pr-2">
                      <span className="font-semibold text-xs text-[#1B1B0E] truncate" data-testid="selected-prescriber-name">
                        {selectedPrescribedBy.name}
                      </span>
                      <Badge variant="neutral" size="sm">Doctor</Badge>
                      <span className="text-[10px] text-[#6D6A60] truncate hidden lg:inline">
                        ({selectedPrescribedBy.degree || selectedPrescribedBy.specialty || selectedPrescribedBy.institution || 'Doctor'})
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedPrescribedBy(null)}
                      className="text-xs text-[#9C2417] hover:underline font-semibold cursor-pointer shrink-0"
                    >
                      Clear
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <div className="flex items-center gap-2 px-2.5 h-9 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs focus-within:border-[#CF8852] focus-within:ring-1 focus-within:ring-[#CF8852]">
                        <Search className="w-3.5 h-3.5 text-[#8E8A7E] shrink-0" />
                        <input
                          type="text"
                          data-testid="prescriber-search-input"
                          value={prescribedBySearch}
                          onChange={(e) => setPrescribedBySearch(e.target.value)}
                          placeholder="Search doctor (blank for Self/Walk-in)..."
                          className="w-full text-xs bg-transparent border-none outline-none text-[#1B1B0E]"
                        />
                      </div>
                      {prescribedByResults.length > 0 && (
                        <div className="absolute top-full left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-[#DCDAD4] rounded-xl shadow-lg z-30 divide-y divide-[#E8E7E3]">
                          {prescribedByResults.map((r) => (
                            <div
                              key={r.id}
                              data-testid={`prescriber-result-${r.id}`}
                              onClick={() => {
                                setSelectedPrescribedBy(r);
                                setPrescribedBySearch('');
                                setPrescribedByResults([]);
                              }}
                              className="p-2 hover:bg-[#FAF3EC] cursor-pointer text-xs flex justify-between items-center"
                            >
                              <div className="min-w-0 pr-2">
                                <span className="font-semibold text-[#1B1B0E] truncate block">{r.name}</span>
                                <span className="text-[#6D6A60] text-[10px]">({r.specialty || r.degree || 'Doctor'})</span>
                              </div>
                              <span className="text-[10px] text-[#8E8A7E] font-mono shrink-0">{r.code}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <button
                      type="button"
                      data-testid="add-doctor-btn"
                      onClick={() => setDoctorModalOpen(true)}
                      className="inline-flex items-center justify-center gap-1 px-2.5 h-9 text-xs font-semibold bg-[#F4F3F0] text-[#54524A] border border-[#CAC7BE] hover:bg-[#E8E7E3] rounded-xl transition-colors cursor-pointer shrink-0"
                    >
                      <Plus className="w-3.5 h-3.5 text-[#525333]" />
                      Add Doctor
                    </button>
                  </div>
                )}
              </div>

              {/* Right Sub-form: 3. Referred By (Doctor / Third Party / Broker) */}
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 h-5">
                  <Users className="w-3.5 h-3.5 text-[#CF8852]" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#525333]">
                    3. Referred By (Doctor / Third Party)
                  </span>
                </div>

                {selectedReferrer ? (
                  <div className="flex items-center justify-between px-3 h-9 bg-white border border-[#DCDAD4] rounded-xl shadow-2xs">
                    <div className="flex items-center gap-2 min-w-0 pr-2">
                      <span className="font-semibold text-xs text-[#1B1B0E] truncate" data-testid="selected-referrer-name">
                        {selectedReferrer.name}
                      </span>
                      <Badge variant="neutral" size="sm">
                        {selectedReferrer.referrer_type || (selectedReferrer as any).type || 'Referrer'}
                      </Badge>
                      <span className="text-[10px] text-[#6D6A60] truncate hidden lg:inline">
                        ({selectedReferrer.specialty || selectedReferrer.institution || selectedReferrer.phone || 'Referrer'})
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedReferrer(null)}
                      className="text-xs text-[#9C2417] hover:underline font-semibold cursor-pointer shrink-0"
                    >
                      Clear
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <div className="flex items-center gap-2 px-2.5 h-9 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs focus-within:border-[#CF8852] focus-within:ring-1 focus-within:ring-[#CF8852]">
                        <Search className="w-3.5 h-3.5 text-[#8E8A7E] shrink-0" />
                        <input
                          type="text"
                          data-testid="referrer-search-input"
                          value={referrerSearch}
                          onChange={(e) => setReferrerSearch(e.target.value)}
                          placeholder="Search doctor or agent (blank for Walk-in)..."
                          className="w-full text-xs bg-transparent border-none outline-none text-[#1B1B0E]"
                        />
                      </div>
                      {referrerResults.length > 0 && (
                        <div className="absolute top-full left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-[#DCDAD4] rounded-xl shadow-lg z-30 divide-y divide-[#E8E7E3]">
                          {referrerResults.map((r) => (
                            <div
                              key={r.id}
                              data-testid={`referrer-result-${r.id}`}
                              onClick={() => {
                                setSelectedReferrer(r);
                                setReferrerSearch('');
                                setReferrerResults([]);
                              }}
                              className="p-2 hover:bg-[#FAF3EC] cursor-pointer text-xs flex justify-between items-center"
                            >
                              <div className="min-w-0 pr-2">
                                <span className="font-semibold text-[#1B1B0E] truncate block">{r.name}</span>
                                <span className="text-[#6D6A60] text-[10px]">
                                  ({(r as any).type || r.referrer_type || 'Referrer'})
                                </span>
                              </div>
                              <span className="text-[10px] text-[#8E8A7E] font-mono shrink-0">{r.code}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <button
                      type="button"
                      data-testid="add-referrer-btn"
                      onClick={() => setReferrerModalOpen(true)}
                      className="inline-flex items-center justify-center gap-1 px-2.5 h-9 text-xs font-semibold bg-[#F4F3F0] text-[#54524A] border border-[#CAC7BE] hover:bg-[#E8E7E3] rounded-xl transition-colors cursor-pointer shrink-0"
                    >
                      <Plus className="w-3.5 h-3.5 text-[#525333]" />
                      Add Referrer
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 4. Investigation Catalog (Item 03: Suggestions filtered when selected) */}
          <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-4.5 shadow-xs">
            <span className="text-xs font-bold uppercase tracking-wider text-[#525333] block mb-3">
              4. Investigation Catalog
            </span>

            {/* Department chips */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              {departments.map((dept) => (
                <button
                  key={dept}
                  type="button"
                  onClick={() => setTestCategory(dept)}
                  className={`px-2.5 py-1 text-xs rounded-lg font-medium transition-colors cursor-pointer ${
                    testCategory === dept
                      ? 'bg-[#525333] text-white shadow-xs'
                      : 'bg-[#F4F3F0] text-[#6D6A60] hover:bg-[#E8E7E3]'
                  }`}
                >
                  {dept}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div className="flex items-center gap-2 px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs mb-3">
              <Search className="w-4 h-4 text-[#8E8A7E]" />
              <input
                type="text"
                data-testid="test-search-input"
                value={testSearch}
                onChange={(e) => setTestSearch(e.target.value)}
                placeholder="Search test name or code (e.g., CBC, Lipid, Dengue, USG)..."
                className="w-full text-xs bg-transparent border-none outline-none text-[#1B1B0E]"
              />
            </div>

            {/* Test list grid — Selected tests are completely filtered out (Item 03) */}
            <div className="max-h-80 overflow-y-auto space-y-1.5 pr-1">
              {filteredTests.length === 0 ? (
                <div className="py-6 text-center text-xs text-[#8E8A7E]">
                  {selectedLines.length > 0 && !testSearch
                    ? 'All matching tests in this category are already selected.'
                    : 'No investigations found.'}
                </div>
              ) : (
                filteredTests.map((test) => (
                  <div
                    key={test.id}
                    data-testid={`catalog-test-${test.id}`}
                    onClick={() => handleAddTest(test)}
                    className="flex items-center justify-between p-2.5 rounded-xl border border-[#DCDAD4] bg-white hover:border-[#CF8852] hover:bg-[#FAF3EC] cursor-pointer shadow-2xs transition-all"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-[#1B1B0E]">{test.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 bg-[#F4F3F0] text-[#6D6A60] rounded border border-[#E8E7E3]">
                          {test.department}
                        </span>
                      </div>
                      <span className="text-[11px] text-[#8E8A7E] font-mono">{test.code}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[#1B1B0E]">
                        ৳{(test.default_price || (test as any).price || 0).toLocaleString()}
                      </span>
                      <Plus className="w-4 h-4 text-[#CF8852]" />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Billing Summary & Payment Intake (52% Expanded) */}
        <div className="space-y-4">
          <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-[#E8E7E3] pb-3 mb-4">
                <span className="text-sm font-bold text-[#1B1B0E] flex items-center gap-2">
                  <Receipt className="w-4 h-4 text-[#CF8852]" />
                  Selected Investigations ({selectedLines.length})
                </span>
                {selectedLines.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setSelectedLines([])}
                    className="text-xs text-[#9C2417] hover:underline cursor-pointer"
                  >
                    Clear All
                  </button>
                )}
              </div>

              {/* Selected Lines List */}
              {selectedLines.length === 0 ? (
                <div className="py-8 text-center text-xs text-[#8E8A7E]">
                  No investigations selected yet. Choose tests from the left catalog.
                </div>
              ) : (
                <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1 mb-4 divide-y divide-[#E8E7E3]">
                  {selectedLines.map((line, idx) => {
                    const displayDiscounts = getLineDisplayDiscounts(line);
                    const lineDiscountAmt = calculatedLineDiscounts[idx] || 0;
                    return (
                      <div key={line.test.id} className="pt-2 first:pt-0" data-testid={`selected-line-${line.test.id}`}>
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-[#1B1B0E]">{line.test.name}</span>
                          <div className="flex items-center gap-2">
                            {lineDiscountAmt > 0 && masterDiscountType === 'NONE' ? (
                              <div className="flex items-center gap-1.5">
                                <span className="text-[11px] text-[#8E8A7E] line-through">৳{line.price}</span>
                                <span className="font-bold text-[#1B1B0E]">৳{line.price - lineDiscountAmt}</span>
                              </div>
                            ) : (
                              <span className="font-bold">৳{line.price}</span>
                            )}
                            <button
                              type="button"
                              data-testid={`remove-line-${line.test.id}`}
                              onClick={() => handleRemoveLine(idx)}
                              className="text-[#9C2417] hover:text-[#582E12] cursor-pointer"
                              title="Remove test (will reappear in catalog)"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>

                        {/* Line controls: Urgent & Line Discount (Item 04: Distinct % and ৳ inputs) */}
                        <div className="flex items-center justify-between mt-1.5 text-[11px]">
                          <label className="flex items-center gap-1.5 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={line.is_urgent}
                              onChange={() => handleToggleUrgent(idx)}
                              className="rounded text-[#CF8852] focus:ring-0 cursor-pointer"
                            />
                            <span className={line.is_urgent ? 'text-red-700 font-bold' : 'text-[#6D6A60]'}>
                              Urgent (+৳{line.urgent_fee})
                            </span>
                          </label>

                          {/* Individual Discount: Distinct % and ৳ Inputs */}
                          {masterDiscountType === 'NONE' ? (
                            <div className="flex items-center gap-1.5">
                              <span className="text-[#8E8A7E]">Disc:</span>
                              {/* % discount input */}
                              <div className="inline-flex items-center bg-white border border-[#CAC7BE] rounded px-1.5 py-0.5 focus-within:border-[#CF8852] focus-within:ring-1 focus-within:ring-[#CF8852]/30 transition-colors">
                                <input
                                  type="number"
                                  min="0"
                                  max={line.test?.discount_cap_percent ?? 100}
                                  value={displayDiscounts.pct}
                                  onChange={(e) => handleLinePercentChange(idx, e.target.value)}
                                  placeholder="0"
                                  className="w-8 text-[11px] bg-transparent text-right font-semibold text-[#1B1B0E] focus:outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                  title="Discount Percentage (%)"
                                  data-testid={`line-discount-percent-${line.test.id}`}
                                />
                                <span className="text-[11px] text-[#8E8A7E] ml-0.5 font-medium select-none">%</span>
                              </div>

                              {/* ৳ discount input */}
                              <div className="inline-flex items-center bg-white border border-[#CAC7BE] rounded px-1.5 py-0.5 focus-within:border-[#CF8852] focus-within:ring-1 focus-within:ring-[#CF8852]/30 transition-colors">
                                <input
                                  type="number"
                                  min="0"
                                  max={line.price}
                                  value={displayDiscounts.amt}
                                  onChange={(e) => handleLineAmountChange(idx, e.target.value)}
                                  placeholder="0"
                                  className="w-12 text-[11px] bg-transparent text-right font-semibold text-[#1B1B0E] focus:outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                  title="Discount Amount (৳)"
                                  data-testid={`line-discount-fixed-${line.test.id}`}
                                />
                                <span className="text-[11px] text-[#8E8A7E] ml-0.5 font-medium select-none">৳</span>
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5 opacity-60">
                              <span className="text-[#8E8A7E]">Disc:</span>
                              <div className="inline-flex items-center bg-[#F4F3F0] border border-[#CAC7BE] rounded px-1.5 py-0.5 cursor-not-allowed">
                                <span className="w-8 text-[11px] text-right font-semibold text-[#8E8A7E]">{displayDiscounts.pct || '0'}</span>
                                <span className="text-[11px] text-[#8E8A7E] ml-0.5 font-medium select-none">%</span>
                              </div>
                              <div className="inline-flex items-center bg-[#F4F3F0] border border-[#CAC7BE] rounded px-1.5 py-0.5 cursor-not-allowed">
                                <span className="w-12 text-[11px] text-right font-semibold text-[#8E8A7E]">{displayDiscounts.amt || '0'}</span>
                                <span className="text-[11px] text-[#8E8A7E] ml-0.5 font-medium select-none">৳</span>
                              </div>
                              <span className="text-[10px] text-amber-700 italic font-medium">(Master Active)</span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Master Discount Section (Item 04: % and ৳ mode synchronized) */}
              <div className="p-3 bg-[#F4F3F0] border border-[#E8E7E3] rounded-xl text-xs mb-4">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#54524A]">Master Invoice Discount</span>
                  <div className="flex items-center gap-1.5">
                    <select
                      value={masterDiscountType}
                      onChange={(e) => handleMasterDiscountTypeChange(e.target.value as DiscountType)}
                      className="text-xs bg-white border border-[#CAC7BE] rounded-lg px-2 py-1 cursor-pointer"
                    >
                      <option value="NONE">No Master Discount</option>
                      <option value="PERCENT">Percentage (%)</option>
                      <option value="FIXED">Fixed Taka (৳)</option>
                    </select>
                    {masterDiscountType !== 'NONE' && (
                      <input
                        type="number"
                        min="0"
                        max={masterDiscountType === 'PERCENT' ? 100 : grossAmount}
                        value={masterDiscountValue || ''}
                        onChange={(e) => handleMasterDiscountValueChange(Number(e.target.value))}
                        placeholder="Value"
                        className="w-16 text-xs bg-white border border-[#CAC7BE] rounded-lg px-2 py-1 text-right font-semibold"
                      />
                    )}
                  </div>
                </div>
                {masterDiscountType !== 'NONE' && (
                  <p className="text-[10px] text-[#CF8852] mt-1 font-medium">
                    Line discounts are superseded while Master Discount is active.
                  </p>
                )}
              </div>

              {/* Financial Calculation Breakdown */}
              <div className="space-y-1.5 border-t border-[#E8E7E3] pt-3 text-xs">
                <div className="flex justify-between text-[#6D6A60]">
                  <span>Gross Subtotal:</span>
                  <span>৳{grossAmount.toLocaleString()}</span>
                </div>
                {urgentFeesTotal > 0 && (
                  <div className="flex justify-between text-red-600 font-medium">
                    <span>Urgent Surcharges:</span>
                    <span>+৳{urgentFeesTotal.toLocaleString()}</span>
                  </div>
                )}
                {totalDiscount > 0 && (
                  <div className="flex justify-between text-[#1E6327] font-medium">
                    <span>Discount Applied:</span>
                    <span>-৳{totalDiscount.toLocaleString()}</span>
                  </div>
                )}
                <div className="flex justify-between text-base font-extrabold text-[#1B1B0E] pt-2 border-t border-[#E8E7E3]">
                  <span>Net Payable:</span>
                  <span>৳{netPayable.toLocaleString()}</span>
                </div>
              </div>

              {/* Payment Section (Item 05: Default ৳0 paid) */}
              <div className="mt-4 p-3.5 bg-white border border-[#DCDAD4] rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#525333] uppercase tracking-wider">
                    Payment Intake
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      data-testid="full-pay-btn"
                      onClick={handleSetFullPayment}
                      className="px-2 py-0.5 text-[10px] font-semibold bg-[#EDF7EE] text-[#1E6327] border border-[#C3E6C7] rounded hover:bg-[#D5EED8] cursor-pointer"
                    >
                      Full Pay (৳{netPayable})
                    </button>
                    <button
                      type="button"
                      data-testid="zero-pay-btn"
                      onClick={handleSetZeroPayment}
                      className="px-2 py-0.5 text-[10px] font-semibold bg-[#FDF2F0] text-[#9C2417] border border-[#F8CBC6] rounded hover:bg-[#FCE3E0] cursor-pointer"
                    >
                      ৳0 (Unpaid)
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <label className="text-[11px] text-[#6D6A60] block mb-1">Payment Method</label>
                    <select
                      value={paymentChannel}
                      onChange={(e) => setPaymentChannel(e.target.value as PaymentChannel)}
                      className="w-full bg-[#FAF9F6] border border-[#CAC7BE] rounded-lg px-2.5 py-1.5 font-semibold text-xs text-[#1B1B0E] cursor-pointer"
                    >
                      <option value="CASH">Cash</option>
                      <option value="BKASH">bKash</option>
                      <option value="NAGAD">Nagad</option>
                      <option value="ROCKET">Rocket</option>
                      <option value="CARD">Debit / Credit Card</option>
                      <option value="BANK_TRANSFER">Bank Transfer</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] text-[#6D6A60] block mb-1">Paid Amount (৳)</label>
                    <input
                      type="number"
                      min="0"
                      max={netPayable}
                      data-testid="paid-amount-input"
                      value={paidAmount}
                      onChange={(e) => setPaidAmount(Math.min(netPayable, Math.max(0, Number(e.target.value))))}
                      className="w-full bg-[#FAF9F6] border border-[#CAC7BE] rounded-lg px-2.5 py-1.5 font-bold text-xs text-right text-[#1E6327]"
                    />
                  </div>
                </div>

                {paymentChannel === 'CASH' && paidAmount > 0 && (
                  <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-[#E8E7E3]">
                    <div>
                      <label className="text-[11px] text-[#6D6A60] block mb-1">Tendered (৳)</label>
                      <input
                        type="number"
                        min={paidAmount}
                        value={tenderedAmount}
                        onChange={(e) => setTenderedAmount(Number(e.target.value))}
                        className="w-full bg-[#FAF9F6] border border-[#CAC7BE] rounded-lg px-2.5 py-1.5 font-semibold text-xs text-right"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] text-[#6D6A60] block mb-1">Change Return</label>
                      <div className="px-2.5 py-1.5 bg-[#FAF3EC] border border-[#E6C4A7] rounded-lg font-bold text-xs text-right text-[#96572A]">
                        ৳{changeAmount.toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}

                {paymentChannel !== 'CASH' && paidAmount > 0 && (
                  <div>
                    <label className="text-[11px] text-[#6D6A60] block mb-1">Reference / TrxID / Approval Code *</label>
                    <input
                      type="text"
                      value={referenceNo}
                      onChange={(e) => setReferenceNo(e.target.value)}
                      placeholder="e.g. TrxID 9K28JA"
                      className="w-full bg-[#FAF9F6] border border-[#CAC7BE] rounded-lg px-2.5 py-1.5 text-xs"
                    />
                  </div>
                )}

                <div className="p-2 bg-[#F4F3F0] border border-[#E8E7E3] rounded-lg text-xs flex justify-between font-bold">
                  <span className="text-[#6D6A60]">Outstanding Due:</span>
                  <span data-testid="due-status-indicator" className={dueAmount > 0 ? 'text-[#9C2417]' : 'text-[#1E6327]'}>
                    ৳{dueAmount.toLocaleString()} {paidAmount === 0 ? '(Unpaid)' : dueAmount > 0 ? '(Partial Due)' : '(Fully Paid)'}
                  </span>
                </div>
              </div>
            </div>

            {/* Item 06: Generate Preview Button (Two-stage creation flow) */}
            <button
              type="button"
              data-testid="generate-preview-btn"
              onClick={handleGeneratePreview}
              disabled={selectedLines.length === 0 || !selectedPatient}
              className={`w-full mt-4 py-3 rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-md transition-all cursor-pointer ${
                selectedLines.length === 0 || !selectedPatient
                  ? 'bg-[#CAC7BE] text-[#6D6A60] cursor-not-allowed'
                  : 'bg-[#CF8852] hover:bg-[#B7703B] text-white'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              <span>Generate Invoice Preview (A4 Dual-Copy)</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </button>
          </div>
        </div>
      </div>

      {/* New Patient Modal */}
      <Modal
        isOpen={patientModalOpen}
        onClose={() => setPatientModalOpen(false)}
        title="Register New Patient"
        subtitle="Intake form with automatic phone & MRN registration"
        maxWidth="lg"
      >
        <form onSubmit={handleCreatePatient} className="space-y-4">
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="col-span-2">
              <label className="block text-[#54524A] font-semibold mb-1">Patient Full Name *</label>
              <input
                type="text"
                required
                data-testid="patient-form-fullname"
                value={newPatient.full_name}
                onChange={(e) => setNewPatient({ ...newPatient, full_name: e.target.value })}
                placeholder="e.g. Mohammad Rahim"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Phone Number *</label>
              <input
                type="tel"
                required
                data-testid="patient-form-phone"
                value={newPatient.phone}
                onChange={(e) => setNewPatient({ ...newPatient, phone: e.target.value })}
                placeholder="01711000000"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Alternate Phone</label>
              <input
                type="tel"
                value={newPatient.alternate_phone}
                onChange={(e) => setNewPatient({ ...newPatient, alternate_phone: e.target.value })}
                placeholder="Optional"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Gender *</label>
              <select
                value={newPatient.gender}
                onChange={(e) => setNewPatient({ ...newPatient, gender: e.target.value as Gender })}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              >
                <option value="MALE">Male</option>
                <option value="FEMALE">Female</option>
                <option value="OTHER">Other</option>
              </select>
            </div>

            <div className="flex gap-2">
              <div className="flex-1">
                <label className="block text-[#54524A] font-semibold mb-1">Age (Years)</label>
                <input
                  type="number"
                  min="0"
                  max="125"
                  value={newPatient.age_years}
                  onChange={(e) =>
                    setNewPatient({ ...newPatient, age_years: e.target.value ? Number(e.target.value) : '' })
                  }
                  placeholder="Y"
                  className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
                />
              </div>
              <div className="w-16">
                <label className="block text-[#54524A] font-semibold mb-1">Months</label>
                <input
                  type="number"
                  min="0"
                  max="11"
                  value={newPatient.age_months}
                  onChange={(e) =>
                    setNewPatient({ ...newPatient, age_months: e.target.value ? Number(e.target.value) : '' })
                  }
                  placeholder="M"
                  className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Blood Group</label>
              <select
                value={newPatient.blood_group}
                onChange={(e) => setNewPatient({ ...newPatient, blood_group: e.target.value })}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              >
                <option value="">Unknown</option>
                <option value="A+">A+</option>
                <option value="A-">A-</option>
                <option value="B+">B+</option>
                <option value="B-">B-</option>
                <option value="AB+">AB+</option>
                <option value="AB-">AB-</option>
                <option value="O+">O+</option>
                <option value="O-">O-</option>
              </select>
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Address</label>
              <input
                type="text"
                value={newPatient.address}
                onChange={(e) => setNewPatient({ ...newPatient, address: e.target.value })}
                placeholder="Area, Thana, City"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setPatientModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              data-testid="save-patient-submit-btn"
              className="px-5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              Save & Select Patient
            </button>
          </div>
        </form>
      </Modal>

      {/* Item 01: Add Doctor (Prescriber) Modal with Write-Only Commission Input */}
      <Modal
        isOpen={doctorModalOpen}
        onClose={() => setDoctorModalOpen(false)}
        title="Add Prescribing Doctor"
        subtitle="Doctor entry with confidential write-only commission setup"
        maxWidth="md"
      >
        <form onSubmit={handleCreateDoctor} className="space-y-4 text-xs">
          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Doctor Name *</label>
            <input
              type="text"
              required
              data-testid="doctor-form-name"
              value={newDoctor.name}
              onChange={(e) => setNewDoctor({ ...newDoctor, name: e.target.value })}
              placeholder="e.g. Prof. Dr. AKM Fazlul Haque"
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Degree / Qualification</label>
              <input
                type="text"
                value={newDoctor.degree}
                onChange={(e) => setNewDoctor({ ...newDoctor, degree: e.target.value })}
                placeholder="MBBS, FCPS, MD"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Specialty</label>
              <input
                type="text"
                value={newDoctor.specialty}
                onChange={(e) => setNewDoctor({ ...newDoctor, specialty: e.target.value })}
                placeholder="Cardiology / Internal Med"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Phone</label>
              <input
                type="tel"
                value={newDoctor.phone}
                onChange={(e) => setNewDoctor({ ...newDoctor, phone: e.target.value })}
                placeholder="01711..."
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Institution</label>
              <input
                type="text"
                value={newDoctor.institution}
                onChange={(e) => setNewDoctor({ ...newDoctor, institution: e.target.value })}
                placeholder="BSMMU / DMC"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
          </div>

          {/* Write-only commission input */}
          <div className="p-3 bg-[#FAF3EC] border border-[#E6C4A7] rounded-xl space-y-2">
            <div className="flex items-center gap-1.5 text-[#96572A] font-semibold text-[11px]">
              <ShieldCheck className="w-4 h-4 text-[#CF8852]" />
              <span>Initial Commission Setup (Confidential / Write-Only)</span>
            </div>
            <p className="text-[10px] text-[#6D6A60] leading-tight">
              Stored confidentially. Receptionists cannot inspect existing commission rates or ledgers afterwards.
            </p>
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div>
                <label className="block text-[10px] text-[#54524A] font-medium mb-0.5">Rate (%)</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  data-testid="doctor-commission-rate"
                  value={newDoctor.commission_rate}
                  onChange={(e) =>
                    setNewDoctor({
                      ...newDoctor,
                      commission_rate: e.target.value ? Number(e.target.value) : '',
                    })
                  }
                  placeholder="0 - 100"
                  className="w-full p-2 bg-white border border-[#CAC7BE] rounded-lg outline-none text-right font-semibold"
                />
              </div>
              <div>
                <label className="block text-[10px] text-[#54524A] font-medium mb-0.5">Type</label>
                <select
                  value={newDoctor.commission_type}
                  onChange={(e) => setNewDoctor({ ...newDoctor, commission_type: e.target.value })}
                  className="w-full p-2 bg-white border border-[#CAC7BE] rounded-lg outline-none"
                >
                  <option value="PERCENT">Percentage (%)</option>
                  <option value="FLAT">Flat Taka</option>
                </select>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setDoctorModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              data-testid="save-doctor-submit-btn"
              className="px-5 py-2 text-xs font-bold bg-[#525333] hover:bg-[#444529] text-white rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              Save & Select Doctor
            </button>
          </div>
        </form>
      </Modal>

      {/* Item 01: Add Referrer (Third Party / Doctor) Modal with Write-Only Commission */}
      <Modal
        isOpen={referrerModalOpen}
        onClose={() => setReferrerModalOpen(false)}
        title="Add Referrer (Doctor / Third Party)"
        subtitle="Commercial referrer entry with write-only commission"
        maxWidth="md"
      >
        <form onSubmit={handleCreateReferrer} className="space-y-4 text-xs">
          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Referrer Name *</label>
            <input
              type="text"
              required
              data-testid="referrer-form-name"
              value={newReferrer.name}
              onChange={(e) => setNewReferrer({ ...newReferrer, name: e.target.value })}
              placeholder="e.g. Dr. Rafiq / Palli Chikitsak Rahim / Al-Madina Clinic"
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Referrer Category *</label>
              <select
                value={newReferrer.type}
                onChange={(e) => setNewReferrer({ ...newReferrer, type: e.target.value })}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              >
                <option value="Doctor">Doctor</option>
                <option value="Agent">Agent / Broker</option>
                <option value="Clinic">Clinic / Partner Hospital</option>
                <option value="Other">Other Third Party</option>
              </select>
            </div>
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Phone</label>
              <input
                type="tel"
                value={newReferrer.phone}
                onChange={(e) => setNewReferrer({ ...newReferrer, phone: e.target.value })}
                placeholder="01711..."
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Specialty / Designation</label>
              <input
                type="text"
                value={newReferrer.specialty}
                onChange={(e) => setNewReferrer({ ...newReferrer, specialty: e.target.value })}
                placeholder="e.g. Village Doctor / Liaison"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Organization / Area</label>
              <input
                type="text"
                value={newReferrer.institution}
                onChange={(e) => setNewReferrer({ ...newReferrer, institution: e.target.value })}
                placeholder="e.g. Savar / Mirpur-10"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
          </div>

          {/* Write-only commission input */}
          <div className="p-3 bg-[#FAF3EC] border border-[#E6C4A7] rounded-xl space-y-2">
            <div className="flex items-center gap-1.5 text-[#96572A] font-semibold text-[11px]">
              <ShieldCheck className="w-4 h-4 text-[#CF8852]" />
              <span>Commission Rate Setup (Confidential / Write-Only)</span>
            </div>
            <p className="text-[10px] text-[#6D6A60] leading-tight">
              Values are strictly write-only and omitted from all receptionist search and detail views.
            </p>
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div>
                <label className="block text-[10px] text-[#54524A] font-medium mb-0.5">Rate (%)</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  data-testid="referrer-commission-rate"
                  value={newReferrer.commission_rate}
                  onChange={(e) =>
                    setNewReferrer({
                      ...newReferrer,
                      commission_rate: e.target.value ? Number(e.target.value) : '',
                    })
                  }
                  placeholder="0 - 100"
                  className="w-full p-2 bg-white border border-[#CAC7BE] rounded-lg outline-none text-right font-semibold"
                />
              </div>
              <div>
                <label className="block text-[10px] text-[#54524A] font-medium mb-0.5">Type</label>
                <select
                  value={newReferrer.commission_type}
                  onChange={(e) => setNewReferrer({ ...newReferrer, commission_type: e.target.value })}
                  className="w-full p-2 bg-white border border-[#CAC7BE] rounded-lg outline-none"
                >
                  <option value="PERCENT">Percentage (%)</option>
                  <option value="FLAT">Flat Taka</option>
                </select>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setReferrerModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              data-testid="save-referrer-submit-btn"
              className="px-5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              Save & Select Referrer
            </button>
          </div>
        </form>
      </Modal>

      {/* Item 06: Dual-Copy Preview Modal (Non-final draft) */}
      <DualCopyInvoiceModal
        isOpen={previewOpen}
        onClose={() => setPreviewOpen(false)}
        isPreview={true}
        invoiceData={previewData}
        onBack={() => setPreviewOpen(false)}
        onSave={() => handleCommitInvoice(false)}
        onSaveAndPrint={() => handleCommitInvoice(true)}
        saving={submitting}
      />

      {/* Item 06 & Item 07: Saved Invoice Dual-Copy View / Print */}
      <DualCopyInvoiceModal
        isOpen={savedModalOpen}
        onClose={() => setSavedModalOpen(false)}
        isPreview={false}
        savedInvoice={savedInvoice}
      />
    </div>
  );
};

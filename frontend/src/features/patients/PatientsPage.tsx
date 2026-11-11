import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Search,
  UserPlus,
  Phone,
  Calendar,
  Eye,
  FileText,
  CreditCard,
  Droplet,
  MapPin,
  Clock,
  Activity,
  PlusCircle,
  FlaskConical,
} from 'lucide-react';
import { api } from '../../api/client';
import { Patient, PatientHistory, Gender, Invoice } from '../../types';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { DualCopyInvoiceModal } from '../../components/common/DualCopyInvoiceModal';
import { PatientHistoryModal } from '../../components/common/PatientHistoryModal';
import { formatPaymentStatus, getPaymentStatusBadgeVariant } from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';

export const PatientsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const idParam = searchParams.get('id');
  const searchParam = searchParams.get('search');

  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState(searchParam || '');

  // Patient History Drawer/Modal State
  const [selectedPatientId, setSelectedPatientId] = useState<string | number | null>(null);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);

  // New Patient Modal State
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newPatient, setNewPatient] = useState<{
    full_name: string;
    phone: string;
    alternate_phone: string;
    gender: Gender;
    age_years: number | '';
    age_months: number | '';
    address: string;
    blood_group: string;
    notes: string;
  }>({
    full_name: '',
    phone: '',
    alternate_phone: '',
    gender: 'MALE',
    age_years: '',
    age_months: '',
    address: '',
    blood_group: '',
    notes: '',
  });

  const { showToast } = useToast();

  const fetchPatients = async () => {
    try {
      setLoading(true);
      const res = await api.getPatients(searchTerm.trim() || undefined);
      setPatients(res);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load patients', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPatients();
    }, 250);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    if (idParam) {
      handleOpenHistory(idParam);
    }
  }, [idParam]);

  const handleOpenHistory = (patientId: string | number) => {
    setSelectedPatientId(patientId);
    setHistoryModalOpen(true);
  };

  const handleCloseHistory = () => {
    setHistoryModalOpen(false);
    setSelectedPatientId(null);
    if (idParam) {
      const next = new URLSearchParams(searchParams);
      next.delete('id');
      setSearchParams(next, { replace: true });
    }
  };

  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPatient.full_name || !newPatient.phone) {
      showToast({ type: 'error', title: 'Required Fields', message: 'Name and Phone are mandatory.' });
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
        notes: newPatient.notes || null,
      });

      showToast({
        type: 'success',
        title: 'Patient Registered',
        message: `${created.full_name} assigned MRN: ${created.mrn}`,
      });
      setCreateModalOpen(false);
      setNewPatient({
        full_name: '',
        phone: '',
        alternate_phone: '',
        gender: 'MALE',
        age_years: '',
        age_months: '',
        address: '',
        blood_group: '',
        notes: '',
      });
      fetchPatients();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Registration Failed', message: err.message });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#1B1B0E]">Patient Registry & History</h1>
          <p className="text-xs text-[#6D6A60]">
            Search patients by name, phone, or MRN. View longitudinal visit and diagnostic billing records.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
            <Search className="w-4 h-4 text-[#8E8A7E]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by name, phone, MRN..."
              className="text-xs bg-transparent border-none outline-none w-52 text-[#1B1B0E]"
            />
          </div>

          <button
            onClick={() => setCreateModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors cursor-pointer"
          >
            <UserPlus className="w-4 h-4" />
            <span>Register Patient</span>
          </button>
        </div>
      </div>

      {/* Patient List Card */}
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">MRN</th>
                <th className="pb-3">Patient Full Name</th>
                <th className="pb-3">Primary Phone</th>
                <th className="pb-3">Gender / Age</th>
                <th className="pb-3">Blood Group</th>
                <th className="pb-3">Address</th>
                <th className="pb-3">Registered On</th>
                <th className="pb-3 text-right pr-2">History</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {patients.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-[#8E8A7E]">
                    No patient records found.
                  </td>
                </tr>
              )}
              {patients.map((p) => (
                <tr key={p.id} className="hover:bg-[#F4F3F0] transition-colors">
                  <td className="py-3 pl-2 font-mono font-bold text-[#1B1B0E]">{p.mrn}</td>
                  <td className="py-3 font-semibold text-[#1B1B0E]">{p.full_name}</td>
                  <td className="py-3 text-[#54524A]">
                    <div className="flex items-center gap-1.5">
                      <Phone className="w-3.5 h-3.5 text-[#8E8A7E]" />
                      <span>{p.phone}</span>
                    </div>
                  </td>
                  <td className="py-3 text-[#6D6A60]">
                    {p.gender} {p.age_years ? `(${p.age_years}y)` : ''}
                  </td>
                  <td className="py-3">
                    {p.blood_group ? (
                      <span className="font-bold text-red-700 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded text-[11px]">
                        {p.blood_group}
                      </span>
                    ) : (
                      <span className="text-[#8E8A7E]">-</span>
                    )}
                  </td>
                  <td className="py-3 text-[#6D6A60] truncate max-w-xs">{p.address || '-'}</td>
                  <td className="py-3 text-[#6D6A60]">{new Date(p.created_at).toLocaleDateString('en-GB')}</td>
                  <td className="py-3 text-right pr-2">
                    <button
                      onClick={() => handleOpenHistory(p.id)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-[#525333] hover:bg-[#E8E7E3] rounded-lg border border-[#CAC7BE] transition-colors cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>History</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Patient History Modal */}
      <PatientHistoryModal
        isOpen={historyModalOpen}
        onClose={handleCloseHistory}
        patientId={selectedPatientId || idParam}
      />

      {/* Register New Patient Modal */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Register New Patient"
        subtitle="Intake form with phone duplication check"
        maxWidth="lg"
      >
        <form onSubmit={handleCreatePatient} className="space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-[#54524A] font-semibold mb-1">Patient Full Name *</label>
              <input
                type="text"
                required
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
              onClick={() => setCreateModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors"
            >
              Register Patient
            </button>
          </div>
        </form>
      </Modal>

    </div>
  );
};


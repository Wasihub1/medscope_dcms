import React, { useState, useEffect } from 'react';
import {
  UserCircle,
  Phone,
  Mail,
  MapPin,
  Shield,
  Save,
  CheckCircle2,
  Building,
} from 'lucide-react';
import { api } from '../../api/client';
import { Badge } from '../../components/common/Badge';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

export const ProfilePage: React.FC = () => {
  const { role, staffName, tenantName } = useAuth();
  const { showToast } = useToast();

  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [formData, setFormData] = useState({
    full_name: '',
    phone: '',
    email: '',
    address: '',
  });

  const fetchProfile = async () => {
    try {
      setLoading(true);
      const data = await api.getProfile();
      setProfile(data);
      setFormData({
        full_name: data.full_name || '',
        phone: data.phone || '',
        email: data.email || '',
        address: data.address || '',
      });
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load profile', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const updated = await api.updateProfile(formData);
      setProfile(updated);
      showToast({
        type: 'success',
        title: 'Profile Updated',
        message: 'Your personal staff details have been saved successfully.',
      });
    } catch (err: any) {
      showToast({ type: 'error', title: 'Update Failed', message: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[#1B1B0E]">Staff Profile & Security</h1>
        <p className="text-xs text-[#6D6A60]">
          Manage your receptionist identity, contact information, and view assigned tenant permissions.
        </p>
      </div>

      {/* Profile Card */}
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-6 shadow-xs space-y-6">
        {/* User Identity Banner */}
        <div className="flex items-center gap-4 border-b border-[#E8E7E3] pb-5">
          <div className="w-16 h-16 rounded-2xl bg-[#525333] text-white flex items-center justify-center font-bold text-2xl shadow-md border border-[#373720]">
            {formData.full_name ? formData.full_name.charAt(0).toUpperCase() : 'R'}
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-lg font-bold text-[#1B1B0E]">{formData.full_name || staffName}</h2>
              <Badge variant="orange" size="sm">
                {profile?.role || role}
              </Badge>
            </div>
            <p className="text-xs text-[#6D6A60] mt-0.5">
              Staff Code: <span className="font-mono font-semibold">{profile?.code || 'STF-002'}</span> |{' '}
              {tenantName}
            </p>
          </div>
        </div>

        {/* Profile Update Form */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Full Legal Name *</label>
              <input
                type="text"
                required
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Phone Number</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Official Email Address</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Residential Address</label>
              <input
                type="text"
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                placeholder="Area, Thana, City"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
          </div>

          <div className="p-3 bg-[#F4F3F0] border border-[#E8E7E3] rounded-xl text-xs space-y-1">
            <span className="font-semibold text-[#54524A] block">Permission Scope:</span>
            <p className="text-[11px] text-[#6D6A60] leading-relaxed">
              Assigned to Reception & Patient Intake counter. Can register patients, generate invoices, receive upfront
              fees and due settlements, route investigations to workstations, submit pre-sample refund requests, and deliver authorized reports.
              Administrative actions such as commission edits, test cost configurations, and financial ledger modifications are strictly isolated.
            </p>
          </div>

          <div className="flex justify-end pt-3 border-t border-[#E8E7E3]">
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2.5 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Save className="w-4 h-4" />
              <span>{submitting ? 'Saving Changes...' : 'Save Profile Changes'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};


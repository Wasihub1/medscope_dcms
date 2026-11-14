import React, { useState, useEffect } from 'react';
import {
  CalendarDays,
  CreditCard,
  Lock,
  Unlock,
  AlertCircle,
  TrendingUp,
  RotateCcw,
  CheckCircle2,
  Clock,
  Coins,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../../api/client';
import { BusinessDay, PaymentChannel } from '../../types';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { DayClosePanel } from './DayClosePanel';

export const BusinessDayPage: React.FC = () => {
  const [businessDay, setBusinessDay] = useState<BusinessDay | null>(null);
  const [loading, setLoading] = useState(true);

  // Open Day Modal
  const [openModalVisible, setOpenModalVisible] = useState(false);
  const [openingBalance, setOpeningBalance] = useState<number>(5000);
  const [channelInputs, setChannelInputs] = useState<Record<string, number>>({
    CASH: 5000,
    BKASH: 0,
    NAGAD: 0,
    CARD: 0,
  });
  const [notes, setNotes] = useState('');
  const [submittingOpen, setSubmittingOpen] = useState(false);

  const { role, refreshBusinessDay } = useAuth();
  const { showToast } = useToast();

  const fetchCurrentDay = async () => {
    try {
      setLoading(true);
      const day = await api.getCurrentBusinessDay();
      setBusinessDay(day);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to fetch business day', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCurrentDay();
  }, []);

  const handleOpenDay = async (e: React.FormEvent) => {
    e.preventDefault();
    if (openingBalance < 0) {
      showToast({ type: 'error', title: 'Invalid Float', message: 'Opening balance cannot be negative.' });
      return;
    }

    setSubmittingOpen(true);
    try {
      const channelBalances = Object.entries(channelInputs).map(([ch, bal]) => ({
        channel: ch,
        opening_balance: bal,
      }));

      const newDay = await api.openBusinessDay({
        opening_balance: openingBalance,
        channel_balances: channelBalances,
        notes: notes || undefined,
      });

      showToast({
        type: 'success',
        title: 'Business Day Opened',
        message: `Business Day #${newDay.day_number} (${newDay.business_date}) is now active.`,
      });

      setOpenModalVisible(false);
      setBusinessDay(newDay);
      refreshBusinessDay();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to Open Day', message: err.message });
    } finally {
      setSubmittingOpen(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#1B1B0E]">Business Day & Drawer Reconciliation</h1>
          <p className="text-xs text-[#6D6A60]">
            Review drawer float, channel balances, intake volume, and operational lifecycle status.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {!businessDay || businessDay.status === 'CLOSED' ? (
            <button
              data-testid="open-day-btn"
              onClick={() => setOpenModalVisible(true)}
              className="px-4 py-2 bg-[#CF8852] hover:bg-[#B7703B] text-white font-bold rounded-xl shadow-xs transition-colors cursor-pointer text-xs inline-flex items-center gap-1.5"
            >
              <Unlock className="w-4 h-4" />
              <span>Open Business Day</span>
            </button>
          ) : role === 'ADMIN' || role === 'OWNER' ? null : (
            <button
              disabled
              data-testid="receptionist-close-day-disabled"
              className="px-3.5 py-2 bg-[#F4F3F0] text-[#8E8A7E] border border-[#CAC7BE] font-semibold rounded-xl cursor-not-allowed text-xs inline-flex items-center gap-1.5 opacity-70"
              title="Receptionists cannot close business days. Switch role to Admin to close."
            >
              <Lock className="w-4 h-4 text-[#8E8A7E]" />
              <span>Close Day (Admin/Owner Only)</span>
            </button>
          )}
        </div>
      </div>

      {/* Role and Boundary Notice */}
      <div className="p-3.5 bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl flex items-start gap-3 shadow-2xs">
        <ShieldAlert className="w-5 h-5 text-[#CF8852] shrink-0 mt-0.5" />
        <div className="text-xs leading-relaxed text-[#54524A]">
          <span className="font-bold text-[#1B1B0E]">Receptionist Lifecycle Boundary:</span>{' '}
          Receptionists can open a business day at the start of shift with initial cash float. However, closing
          the financial day requires drawer cash counting and cashier/admin reconciliation, which is strictly
          forbidden for the Receptionist role.
        </div>
      </div>

      {(role === 'ADMIN' || role === 'OWNER') && <DayClosePanel onChanged={() => { fetchCurrentDay(); refreshBusinessDay(); }} />}

      {businessDay ? (
        <div className="space-y-6">
          {/* Main Stat Card */}
          <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-6 shadow-xs">
            <div className="flex items-center justify-between border-b border-[#E8E7E3] pb-4 mb-4">
              <div>
                <div className="flex items-center gap-2.5">
                  <h2 className="text-lg font-bold text-[#1B1B0E]">
                    Business Day #{businessDay.day_number}
                  </h2>
                  <Badge variant="success" dot>
                    Active Open
                  </Badge>
                </div>
                <p className="text-xs text-[#6D6A60] mt-0.5">
                  Date: <span className="font-semibold text-[#1B1B0E]">{businessDay.business_date}</span> |
                  Opened at{' '}
                  <span className="font-semibold text-[#1B1B0E]">
                    {new Date(businessDay.opened_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>{' '}
                  by {businessDay.opened_by_name || 'Staff'}
                </p>
              </div>

              <div className="text-right">
                <span className="text-[11px] text-[#6D6A60] block">Current Drawer Balance</span>
                <span className="text-2xl font-extrabold text-[#525333]">
                  ৳{businessDay.current_balance.toLocaleString()}
                </span>
              </div>
            </div>

            {/* Float vs Collections vs Refunds */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-white border border-[#DCDAD4] p-4 rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#6D6A60]">Opening Float</span>
                  <Coins className="w-4 h-4 text-[#CF8852]" />
                </div>
                <div className="mt-2">
                  <span className="text-xl font-bold text-[#1B1B0E]">
                    ৳{businessDay.opening_balance.toLocaleString()}
                  </span>
                  <span className="block text-[11px] text-[#8E8A7E] mt-0.5">Physical start cash</span>
                </div>
              </div>

              <div className="bg-white border border-[#DCDAD4] p-4 rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#6D6A60]">Total Collections</span>
                  <TrendingUp className="w-4 h-4 text-[#1E6327]" />
                </div>
                <div className="mt-2">
                  <span className="text-xl font-bold text-[#1E6327]">
                    ৳{businessDay.total_collections.toLocaleString()}
                  </span>
                  <span className="block text-[11px] text-[#1E6327] mt-0.5">All payment channels</span>
                </div>
              </div>

              <div className="bg-white border border-[#DCDAD4] p-4 rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#6D6A60]">Disbursed Refunds</span>
                  <RotateCcw className="w-4 h-4 text-[#9C2417]" />
                </div>
                <div className="mt-2">
                  <span className="text-xl font-bold text-[#9C2417]">
                    ৳{businessDay.total_refunds.toLocaleString()}
                  </span>
                  <span className="block text-[11px] text-[#9C2417] mt-0.5">Approved payouts</span>
                </div>
              </div>
            </div>
          </div>

          {/* Payment Channels Breakdown */}
          <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
            <h3 className="text-sm font-bold text-[#1B1B0E] mb-3 uppercase tracking-wider text-[#525333]">
              Channel Balance Breakdown
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {businessDay.channel_balances.map((ch) => (
                <div key={ch.channel} className="bg-white border border-[#DCDAD4] p-3.5 rounded-xl">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs text-[#1B1B0E]">{ch.channel}</span>
                    <Badge variant="neutral" size="sm">
                      {ch.collections_count} txns
                    </Badge>
                  </div>
                  <div className="mt-2">
                    <span className="text-base font-bold text-[#1B1B0E]">
                      ৳{ch.current_balance.toLocaleString()}
                    </span>
                    <span className="block text-[10px] text-[#8E8A7E]">
                      Opening: ৳{ch.opening_balance.toLocaleString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-12 text-center shadow-xs">
          <CalendarDays className="w-12 h-12 text-[#CF8852] mx-auto mb-3 opacity-80" />
          <h2 className="text-lg font-bold text-[#1B1B0E]">No Active Business Day</h2>
          <p className="text-xs text-[#6D6A60] max-w-md mx-auto mt-1 mb-6 leading-relaxed">
            The diagnostic center has not opened a business day yet. Please open a day to begin registering
            patients, issuing invoices, and receiving cash.
          </p>
          <button
            onClick={() => setOpenModalVisible(true)}
            className="px-5 py-2.5 bg-[#CF8852] hover:bg-[#B7703B] text-white font-bold rounded-xl shadow-xs transition-colors cursor-pointer text-xs inline-flex items-center gap-2"
          >
            <Unlock className="w-4 h-4" />
            <span>Open Business Day Now</span>
          </button>
        </div>
      )}

      {/* Open Business Day Modal */}
      <Modal
        isOpen={openModalVisible}
        onClose={() => setOpenModalVisible(false)}
        title="Open Diagnostic Business Day"
        subtitle="Establish physical cash drawer float and channel opening balances"
        maxWidth="md"
      >
        <form onSubmit={handleOpenDay} className="space-y-4 text-xs">
          <div>
            <label className="block text-[#54524A] font-semibold mb-1">
              Opening Cash Float in Drawer (৳) *
            </label>
            <input
              type="number"
              min="0"
              required
              value={openingBalance}
              onChange={(e) => {
                const val = Number(e.target.value);
                setOpeningBalance(val);
                setChannelInputs((prev) => ({ ...prev, CASH: val }));
              }}
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-bold text-sm text-[#525333]"
            />
            <span className="text-[10px] text-[#8E8A7E]">
              Physical petty cash available for change return.
            </span>
          </div>

          <div className="space-y-2 pt-2 border-t border-[#E8E7E3]">
            <span className="font-semibold text-[#54524A] block">Digital Channel Starting Balances</span>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[#6D6A60] text-[11px] mb-1">bKash Merchant</label>
                <input
                  type="number"
                  min="0"
                  value={channelInputs.BKASH || 0}
                  onChange={(e) =>
                    setChannelInputs({ ...channelInputs, BKASH: Number(e.target.value) })
                  }
                  className="w-full p-2 bg-white border border-[#CAC7BE] rounded-xl text-right font-medium"
                />
              </div>
              <div>
                <label className="block text-[#6D6A60] text-[11px] mb-1">Nagad Merchant</label>
                <input
                  type="number"
                  min="0"
                  value={channelInputs.NAGAD || 0}
                  onChange={(e) =>
                    setChannelInputs({ ...channelInputs, NAGAD: Number(e.target.value) })
                  }
                  className="w-full p-2 bg-white border border-[#CAC7BE] rounded-xl text-right font-medium"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Shift Notes (Optional)</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Morning shift intake started"
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setOpenModalVisible(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submittingOpen}
              className="px-5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors"
            >
              {submittingOpen ? 'Opening...' : 'Confirm & Open Day'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};


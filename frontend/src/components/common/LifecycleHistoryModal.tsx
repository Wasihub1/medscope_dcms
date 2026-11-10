import React, { useState, useEffect } from 'react';
import { X, History, Clock, CheckCircle2, AlertTriangle, Droplet, Send, UserCheck, RefreshCw } from 'lucide-react';
import { api } from '../../api/client';
import { TestOrderEvent, TechnicianWorklistItem } from '../../types';

interface LifecycleHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: TechnicianWorklistItem | null;
}

export const LifecycleHistoryModal: React.FC<LifecycleHistoryModalProps> = ({
  isOpen,
  onClose,
  order,
}) => {
  const [events, setEvents] = useState<TestOrderEvent[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && order) {
      setLoading(true);
      api
        .getOrderEvents(order.test_order_id)
        .then((res) => setEvents(res))
        .catch((err) => console.error('Failed to load lifecycle events:', err))
        .finally(() => setLoading(false));
    } else {
      setEvents([]);
    }
  }, [isOpen, order]);

  if (!isOpen || !order) return null;

  const getEventIcon = (eventType: string) => {
    if (eventType.includes('COLLECTED')) return <Droplet className="w-3.5 h-3.5 text-emerald-600" />;
    if (eventType.includes('REJECTED') || eventType.includes('SPOILED'))
      return <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />;
    if (eventType.includes('COMPLETED')) return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />;
    if (eventType.includes('OUTSOURCED')) return <Send className="w-3.5 h-3.5 text-blue-600" />;
    if (eventType.includes('PATIENT_CONTACTED')) return <UserCheck className="w-3.5 h-3.5 text-amber-600" />;
    return <Clock className="w-3.5 h-3.5 text-[#525333]" />;
  };

  const getEventBadgeClass = (eventType: string) => {
    if (eventType.includes('COLLECTED')) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (eventType.includes('REJECTED') || eventType.includes('SPOILED'))
      return 'bg-rose-50 text-rose-700 border-rose-200';
    if (eventType.includes('COMPLETED')) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (eventType.includes('OUTSOURCED')) return 'bg-blue-50 text-blue-700 border-blue-200';
    if (eventType.includes('PATIENT_CONTACTED')) return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-[#F4F3F0] text-[#54524A] border-[#DCDAD4]';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#1B1B0E]/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-white border border-[#DCDAD4] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-[#F4F3F0] border-b border-[#E8E7E3]">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-[#525333]" />
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#1B1B0E]">
                Operational Lifecycle Timeline
              </h2>
              <span className="text-[11px] text-[#6D6A60]">
                Order #{order.test_order_id} • {order.test_name} ({order.test_code})
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-[#6D6A60] hover:text-[#1B1B0E] hover:bg-[#E8E7E3] rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-4">
          {/* Summary Box */}
          <div className="p-3 bg-[#FAF9F6] border border-[#E8E7E3] rounded-xl flex items-center justify-between text-xs">
            <div>
              <span className="text-[#6D6A60] block text-[10px]">Patient</span>
              <strong className="text-[#1B1B0E]">{order.patient_name}</strong> ({order.patient_code})
            </div>
            <div>
              <span className="text-[#6D6A60] block text-[10px]">Current Status</span>
              <span className="font-semibold text-[#525333]">{order.status.replace('_', ' ')}</span>
            </div>
            {order.sample_code && (
              <div>
                <span className="text-[#6D6A60] block text-[10px]">Sample Code</span>
                <span className="font-mono font-semibold text-emerald-800">{order.sample_code}</span>
              </div>
            )}
          </div>

          {/* Timeline List */}
          {loading ? (
            <div className="py-12 text-center text-xs text-[#6D6A60]">
              <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-[#525333]" />
              Loading event history...
            </div>
          ) : events.length === 0 ? (
            <div className="py-10 text-center text-xs text-[#8E8A7E]">
              No operational events recorded yet for this order.
            </div>
          ) : (
            <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#E8E7E3]">
              {events.map((ev) => (
                <div key={ev.id} className="relative group">
                  {/* Timeline Node Icon */}
                  <div className="absolute -left-6 top-0.5 w-5 h-5 rounded-full bg-white border border-[#CAC7BE] flex items-center justify-center shadow-xs">
                    {getEventIcon(ev.event_type)}
                  </div>

                  {/* Event Details Card */}
                  <div className="bg-[#FAF9F6] border border-[#E8E7E3] rounded-xl p-3 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getEventBadgeClass(
                          ev.event_type
                        )}`}
                      >
                        {ev.stage || ev.event_type.replace('_', ' ')}
                      </span>
                      <span className="text-[10px] font-mono text-[#8E8A7E]">
                        {new Date(ev.created_at).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </span>
                    </div>

                    <p className="text-xs text-[#1B1B0E] font-medium leading-relaxed">{ev.description}</p>

                    {ev.notes && (
                      <p className="text-[11px] text-[#6D6A60] italic bg-white p-2 rounded-lg border border-[#E8E7E3]">
                        "{ev.notes}"
                      </p>
                    )}

                    <div className="text-[10px] text-[#8E8A7E] pt-0.5 flex items-center gap-1.5">
                      <span>Logged by:</span>
                      <strong className="text-[#54524A]">{ev.actor_name || 'System'}</strong>
                      {ev.actor_role && <span>({ev.actor_role})</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-[#F4F3F0] border-t border-[#E8E7E3] flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold bg-white border border-[#CAC7BE] rounded-xl hover:bg-[#E8E7E3] text-[#1B1B0E] transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};


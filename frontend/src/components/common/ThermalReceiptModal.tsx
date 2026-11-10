import React from 'react';
import { Printer, Download, X } from 'lucide-react';
import { Invoice } from '../../types';

interface ThermalReceiptModalProps {
  isOpen: boolean;
  onClose: () => void;
  invoice: Invoice | null;
  isReprint?: boolean;
}

export const ThermalReceiptModal: React.FC<ThermalReceiptModalProps> = ({
  isOpen,
  onClose,
  invoice,
  isReprint = false,
}) => {
  if (!isOpen || !invoice) return null;

  const handlePrint = () => {
    window.print();
  };

  const showWatermark = isReprint || invoice.is_reprint;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#1B1B0E]/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-white border border-[#DCDAD4] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Modal Controls (No Print) */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-[#F4F3F0] border-b border-[#E8E7E3] no-print">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#6D6A60]">
            Thermal Receipt Preview (80mm)
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-lg transition-colors shadow-xs"
            >
              <Printer className="w-3.5 h-3.5" />
              Print Receipt
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-[#6D6A60] hover:text-[#1B1B0E] hover:bg-[#E8E7E3] rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Printable Area (80mm Thermal paper simulation) */}
        <div className="p-6 overflow-y-auto bg-white font-mono text-xs text-black leading-relaxed relative print:p-0 print:m-0">
          {showWatermark && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-15 rotate-[-30deg]">
              <span className="text-6xl font-black tracking-widest text-red-600 border-4 border-red-600 px-6 py-2 rounded-xl">
                DUPLICATE
              </span>
            </div>
          )}

          {/* Diagnostic Center Header */}
          <div className="text-center border-b border-dashed border-gray-400 pb-3 mb-3">
            <h2 className="text-base font-bold tracking-tight uppercase">MedScope Central Diagnostics</h2>
            <p className="text-[11px] text-gray-600">House 42, Road 11, Dhanmondi, Dhaka</p>
            <p className="text-[11px] text-gray-600">Hotline: +880 1700-000000 | Reg: DGHS-2024-8891</p>
            <div className="mt-2 inline-block px-2.5 py-0.5 bg-gray-100 border border-gray-300 rounded font-sans text-[11px] font-semibold">
              MONEY RECEIPT {showWatermark && '(REPRINT)'}
            </div>
          </div>

          {/* Invoice & Patient Meta */}
          <div className="space-y-1 border-b border-dashed border-gray-400 pb-3 mb-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Bill No:</span>
              <span className="font-bold">{invoice.invoice_number}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Date:</span>
              <span>{new Date(invoice.created_at).toLocaleString('en-GB')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">MRN:</span>
              <span className="font-semibold">{invoice.patient_mrn}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Patient:</span>
              <span className="font-semibold">{invoice.patient_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Contact:</span>
              <span>{invoice.patient_phone}</span>
            </div>
            {invoice.patient_age_display && (
              <div className="flex justify-between">
                <span className="text-gray-600">Age / Gender:</span>
                <span>{invoice.patient_age_display} / {invoice.patient_gender || '-'}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-gray-600">Ref. By:</span>
              <span className="truncate max-w-[200px] text-right">{invoice.referrer_name || 'Self / Walk-in'}</span>
            </div>
          </div>

          {/* Test Items Table */}
          <div className="border-b border-dashed border-gray-400 pb-3 mb-3">
            <div className="grid grid-cols-12 font-bold border-b border-gray-300 pb-1 mb-1">
              <span className="col-span-1">#</span>
              <span className="col-span-7">Investigation</span>
              <span className="col-span-4 text-right">Amount (৳)</span>
            </div>
            <div className="space-y-1">
              {invoice.lines.map((line, idx) => (
                <div key={line.id} className="grid grid-cols-12 text-[11px]">
                  <span className="col-span-1 text-gray-500">{idx + 1}</span>
                  <div className="col-span-7 pr-1">
                    <span className="font-medium">{line.test_name}</span>
                    {line.is_urgent && (
                      <span className="ml-1 text-[9px] px-1 bg-red-100 text-red-700 font-bold rounded">
                        URGENT
                      </span>
                    )}
                    {line.discount_amount > 0 && (
                      <div className="text-[10px] text-gray-500">
                        Disc: -৳{line.discount_amount}
                      </div>
                    )}
                  </div>
                  <span className="col-span-4 text-right">{line.net_amount.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Financial Breakdown */}
          <div className="space-y-1 border-b border-dashed border-gray-400 pb-3 mb-3">
            <div className="flex justify-between">
              <span>Gross Total:</span>
              <span>৳{invoice.gross_amount.toLocaleString()}</span>
            </div>
            {invoice.urgent_fee_total > 0 && (
              <div className="flex justify-between text-red-600">
                <span>Urgent Fees:</span>
                <span>+৳{invoice.urgent_fee_total.toLocaleString()}</span>
              </div>
            )}
            {(invoice.line_discount_total > 0 || invoice.master_discount_amount > 0) && (
              <div className="flex justify-between text-green-700">
                <span>Total Discount:</span>
                <span>
                  -৳{(invoice.line_discount_total + invoice.master_discount_amount).toLocaleString()}
                </span>
              </div>
            )}
            <div className="flex justify-between font-bold text-sm pt-1 border-t border-gray-300">
              <span>Net Payable:</span>
              <span>৳{invoice.net_amount.toLocaleString()}</span>
            </div>
            <div className="flex justify-between font-semibold">
              <span>Paid Amount:</span>
              <span>৳{invoice.paid_amount.toLocaleString()}</span>
            </div>
            <div className={`flex justify-between font-bold ${invoice.due_amount > 0 ? 'text-red-700' : 'text-gray-800'}`}>
              <span>Due Balance:</span>
              <span>৳{invoice.due_amount.toLocaleString()}</span>
            </div>
          </div>

          {/* Payment Receipts Breakdown */}
          {invoice.payments && invoice.payments.length > 0 && (
            <div className="border-b border-dashed border-gray-400 pb-3 mb-3 text-[10px]">
              <p className="font-bold mb-1">Payment Transactions:</p>
              {invoice.payments.map((p) => (
                <div key={p.id} className="flex justify-between text-gray-700">
                  <span>{p.channel} ({new Date(p.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})</span>
                  <span>৳{p.amount.toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}

          {/* Simulated Barcode */}
          <div className="text-center py-2">
            <div className="inline-block tracking-[0.3em] font-mono text-xl font-black bg-gray-100 px-4 py-1.5 rounded border border-gray-300">
              * {invoice.invoice_number} *
            </div>
            <p className="text-[10px] text-gray-500 mt-1">Present this receipt at the delivery counter</p>
          </div>

          {/* Footer Notes */}
          <div className="text-center text-[10px] text-gray-500 pt-2 border-t border-gray-200">
            <p>Served by: {invoice.created_by_name || 'Reception Desk'}</p>
            <p className="italic">Thank you for trusting MedScope Diagnostics.</p>
          </div>
        </div>
      </div>
    </div>
  );
};


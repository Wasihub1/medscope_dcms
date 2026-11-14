import React from 'react';
import { Printer, X, ArrowLeft, CheckCircle2, AlertTriangle, FileText, Scissors } from 'lucide-react';
import { Invoice } from '../../types';
import { channelLabel } from '../../utils/paymentChannels';

export interface PreviewInvoiceData {
  patient_name: string;
  patient_mrn?: string;
  patient_phone: string;
  patient_gender?: string;
  patient_age_display?: string;
  prescribed_by_name?: string | null;
  referrer_name?: string | null;
  lines: Array<{
    test_id: number;
    test_name: string;
    department: string;
    price: number;
    is_urgent: boolean;
    urgent_fee: number;
    discount_amount: number;
    net_amount: number;
  }>;
  gross_amount: number;
  urgent_fee_total: number;
  line_discount_total: number;
  master_discount_amount: number;
  total_discount: number;
  net_amount: number;
  paid_amount: number;
  due_amount: number;
  payment_channel?: string;
  /** Prompt 10E: channel name typed for OTHER */
  payment_channel_detail?: string;
  reference_no?: string;
  notes?: string;
}

interface DualCopyInvoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  isPreview?: boolean;
  isReprint?: boolean;
  invoiceData?: PreviewInvoiceData | null;
  savedInvoice?: Invoice | null;
  onBack?: () => void;
  onSave?: () => void;
  onSaveAndPrint?: () => void;
  /** Prompt 10D: saves the form as a DRAFT (no invoice number, no operational effect). */
  onSaveDraft?: () => void;
  /** Prompt 10D: placeholder number of an already saved draft (e.g. DRAFT-1A2B3C4D5E). */
  draftLabel?: string | null;
  saving?: boolean;
}

export const DualCopyInvoiceModal: React.FC<DualCopyInvoiceModalProps> = ({
  isOpen,
  onClose,
  isPreview = false,
  isReprint = false,
  invoiceData,
  savedInvoice,
  onBack,
  onSave,
  onSaveAndPrint,
  saving = false,
  onSaveDraft,
  draftLabel = null,
}) => {
  if (!isOpen) return null;

  const handlePrint = () => {
    window.print();
  };

  // Harmonize data source between Preview and Saved Invoice
  const sourceIsPreview = isPreview && Boolean(invoiceData);
  const data = sourceIsPreview && invoiceData
    ? {
        invoice_number: 'PENDING (PREVIEW)',
        created_at: new Date().toLocaleString('en-GB'),
        patient_name: invoiceData.patient_name,
        patient_mrn: invoiceData.patient_mrn || 'NEW REGISTRATION',
        patient_phone: invoiceData.patient_phone,
        patient_gender: invoiceData.patient_gender,
        patient_age_display: invoiceData.patient_age_display,
        prescribed_by_name: invoiceData.prescribed_by_name || 'Self / Walk-in',
        referrer_name: invoiceData.referrer_name || 'Self / Walk-in',
        lines: (invoiceData.lines || []).map((l: any) => ({
          test_name: l.test_name || l.name || l.test_name_snapshot || (l.test && (l.test.name || l.test.test_name)) || 'Investigation',
          department: l.department || l.department_snapshot || (l.test && l.test.department) || '',
          price: l.price ?? l.unit_price_snapshot ?? (l.test && l.test.price) ?? 0,
          is_urgent: l.is_urgent ?? l.urgent ?? false,
          urgent_fee: l.urgent_fee ?? 0,
          discount_amount: l.discount_amount ?? 0,
          net_amount: l.net_amount ?? l.net_price ?? (l.price ?? 0),
        })),
        gross_amount: invoiceData.gross_amount,
        urgent_fee_total: invoiceData.urgent_fee_total,
        total_discount: invoiceData.total_discount,
        net_amount: invoiceData.net_amount,
        paid_amount: invoiceData.paid_amount,
        due_amount: invoiceData.due_amount,
        payment_text: invoiceData.paid_amount > 0 ? channelLabel(invoiceData.payment_channel, invoiceData.payment_channel_detail) : '',
        created_by_name: 'Reception Desk',
        is_duplicate: false,
        reprint_count: 0,
      }
    : savedInvoice
    ? {
        invoice_number: savedInvoice.invoice_number,
        created_at: new Date(savedInvoice.created_at).toLocaleString('en-GB'),
        patient_name: savedInvoice.patient_name,
        patient_mrn: savedInvoice.patient_mrn,
        patient_phone: savedInvoice.patient_phone,
        patient_gender: savedInvoice.visit_gender || savedInvoice.patient_gender || undefined,
        patient_age_display:
          savedInvoice.age_value !== undefined && savedInvoice.age_value !== null
            ? `${savedInvoice.age_value} ${savedInvoice.age_unit || 'years'}`
            : savedInvoice.patient_age_display || undefined,
        prescribed_by_name: savedInvoice.prescribed_by_name || 'Self / Walk-in',
        referrer_name: savedInvoice.referrer_name || 'Self / Walk-in',
        lines: (savedInvoice.lines || []).map((l: any) => ({
          test_name: l.test_name || l.test_name_snapshot || l.name || (l.test && (l.test.name || l.test.test_name)) || 'Investigation',
          department: l.department || l.department_snapshot || (l.test && l.test.department) || '',
          price: l.price ?? l.unit_price_snapshot ?? (l.test && l.test.price) ?? 0,
          is_urgent: l.is_urgent ?? l.urgent ?? false,
          urgent_fee: l.line_urgent_fee ?? l.urgent_fee ?? 0,
          discount_amount: l.discount_amount ?? 0,
          net_amount: (l.net_amount ?? l.net_price ?? 0) + (l.line_urgent_fee ?? 0),
        })),
        gross_amount: savedInvoice.gross_amount,
        urgent_fee_total: savedInvoice.urgent_fee ?? savedInvoice.urgent_fee_total ?? 0,
        total_discount:
          (savedInvoice as any).discount_amount ??
          (savedInvoice.line_discount_total || 0) + (savedInvoice.master_discount_amount || 0),
        net_amount: savedInvoice.net_amount,
        paid_amount: savedInvoice.paid_amount,
        due_amount: savedInvoice.due_amount,
        payment_text: (savedInvoice.payments || [])
          .map((p: any) => channelLabel(p.method || p.channel, p.channel_detail))
          .filter((v, i, arr) => v && arr.indexOf(v) === i)
          .join(', '),
        created_by_name: savedInvoice.created_by_name || 'Front Desk Staff',
        is_duplicate: isReprint || savedInvoice.is_duplicate_reprint,
        reprint_count: savedInvoice.reprint_count || 1,
      }
    : invoiceData
    ? {
        invoice_number: 'PENDING (PREVIEW)',
        created_at: new Date().toLocaleString('en-GB'),
        patient_name: invoiceData.patient_name,
        patient_mrn: invoiceData.patient_mrn || 'NEW REGISTRATION',
        patient_phone: invoiceData.patient_phone,
        patient_gender: invoiceData.patient_gender,
        patient_age_display: invoiceData.patient_age_display,
        prescribed_by_name: invoiceData.prescribed_by_name || 'Self / Walk-in',
        referrer_name: invoiceData.referrer_name || 'Self / Walk-in',
        lines: (invoiceData.lines || []).map((l: any) => ({
          test_name: l.test_name || l.name || l.test_name_snapshot || (l.test && (l.test.name || l.test.test_name)) || 'Investigation',
          department: l.department || l.department_snapshot || (l.test && l.test.department) || '',
          price: l.price ?? l.unit_price_snapshot ?? (l.test && l.test.price) ?? 0,
          is_urgent: l.is_urgent ?? l.urgent ?? false,
          urgent_fee: l.urgent_fee ?? 0,
          discount_amount: l.discount_amount ?? 0,
          net_amount: l.net_amount ?? l.net_price ?? (l.price ?? 0),
        })),
        gross_amount: invoiceData.gross_amount,
        urgent_fee_total: invoiceData.urgent_fee_total,
        total_discount: invoiceData.total_discount,
        net_amount: invoiceData.net_amount,
        paid_amount: invoiceData.paid_amount,
        due_amount: invoiceData.due_amount,
        payment_text: invoiceData.paid_amount > 0 ? channelLabel(invoiceData.payment_channel, invoiceData.payment_channel_detail) : '',
        created_by_name: 'Reception Desk',
        is_duplicate: false,
        reprint_count: 0,
      }
    : null;

  if (!data) return null;

  const renderSingleCopy = (copyLabel: string) => (
    <div className="flex-1 p-4 bg-white border border-[#DCDAD4] rounded-xl flex flex-col justify-between text-[11px] relative print:border-none print:p-2">
      {/* Watermarks */}
      {isPreview && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-10 select-none rotate-[-25deg]">
          <span className="text-4xl font-extrabold tracking-widest text-[#9C2417] border-4 border-[#9C2417] px-6 py-2 rounded-2xl">
            PREVIEW ONLY
          </span>
        </div>
      )}
      {data.is_duplicate && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-15 select-none rotate-[-25deg]">
          <span className="text-4xl font-extrabold tracking-widest text-[#9C2417] border-4 border-[#9C2417] px-6 py-2 rounded-2xl">
            DUPLICATE
          </span>
        </div>
      )}

      <div>
        {/* Header */}
        <div className="border-b border-gray-400 pb-2 mb-2 text-center">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 bg-[#FAF3EC] text-[#96572A] border border-[#E6C4A7] rounded">
              {copyLabel}
            </span>
            <span className="text-[10px] text-gray-500 font-mono">
              Bill: <strong className="text-black">{data.invoice_number}</strong>
            </span>
          </div>
          <h2 className="text-sm font-black tracking-tight text-black mt-1 uppercase">
            MedScope Central Diagnostics
          </h2>
          <p className="text-[10px] text-gray-600">House 42, Road 11, Dhanmondi, Dhaka-1209 | Hotline: +880 1700-000000</p>
          <p className="text-[9px] text-gray-500">DGHS Reg: DGHS-2024-8891 | ISO 15189 Accredited</p>
        </div>

        {/* Patient & Prescription Info */}
        <div className="bg-[#FAF9F6] border border-gray-300 rounded p-2 mb-2 grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
          <div>
            <span className="text-gray-500">Patient: </span>
            <span className="font-bold text-black">{data.patient_name}</span>
          </div>
          <div>
            <span className="text-gray-500">MRN: </span>
            <span className="font-mono font-semibold text-black">{data.patient_mrn}</span>
          </div>
          <div>
            <span className="text-gray-500">Age / Gender: </span>
            <span className="text-black">
              {data.patient_age_display || '-'} / {data.patient_gender || '-'}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Contact: </span>
            <span className="font-mono text-black">{data.patient_phone}</span>
          </div>
          <div className="col-span-2 border-t border-dashed border-gray-300 pt-1 mt-0.5">
            <span className="text-gray-500">Prescribed By: </span>
            <span className="font-semibold text-black">{data.prescribed_by_name}</span>
          </div>
          <div className="col-span-2">
            <span className="text-gray-500">Referred By: </span>
            <span className="text-gray-800">{data.referrer_name}</span>
          </div>
        </div>

        {/* Itemized Investigations Table */}
        <table className="w-full text-left text-[10px] border-collapse mb-2">
          <thead>
            <tr className="border-b border-t border-gray-400 bg-gray-100 font-bold text-gray-700">
              <th className="py-1 px-1 w-6">#</th>
              <th className="py-1 px-1">Investigation</th>
              <th className="py-1 px-1">Dept</th>
              <th className="py-1 px-1 text-right">Price</th>
              <th className="py-1 px-1 text-right">Disc</th>
              <th className="py-1 px-1 text-right">Net</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {data.lines.map((line, idx) => (
              <tr key={idx}>
                <td className="py-0.5 px-1 text-gray-500">{idx + 1}</td>
                <td className="py-0.5 px-1 font-medium text-black">
                  {line.test_name || (line as any).test_name_snapshot || (line as any).name || 'Investigation'}
                  {line.is_urgent && (
                    <span className="ml-1 text-[8px] px-1 bg-red-100 text-red-700 font-bold rounded">
                      URGENT
                    </span>
                  )}
                </td>
                <td className="py-0.5 px-1 text-gray-500 text-[9px]">{line.department}</td>
                <td className="py-0.5 px-1 text-right text-gray-700">৳{line.price}</td>
                <td className="py-0.5 px-1 text-right text-green-700">
                  {line.discount_amount > 0 ? `-৳${line.discount_amount}` : '-'}
                </td>
                <td className="py-0.5 px-1 text-right font-semibold text-black">৳{line.net_amount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Financials & Signatures */}
      <div>
        <div className="border-t border-gray-400 pt-1.5 space-y-0.5 text-[10px]">
          <div className="flex justify-between text-gray-600">
            <span>Gross Amount:</span>
            <span>৳{data.gross_amount.toLocaleString()}</span>
          </div>
          {data.urgent_fee_total > 0 && (
            <div className="flex justify-between text-red-600">
              <span>Urgent Surcharges:</span>
              <span>+৳{data.urgent_fee_total.toLocaleString()}</span>
            </div>
          )}
          {data.total_discount > 0 && (
            <div className="flex justify-between text-green-700">
              <span>Total Discount:</span>
              <span>-৳{data.total_discount.toLocaleString()}</span>
            </div>
          )}
          <div className="flex justify-between font-bold text-xs pt-1 border-t border-gray-300 text-black">
            <span>Net Payable:</span>
            <span>৳{data.net_amount.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-green-800 font-semibold">
            <span>Paid Amount:</span>
            <span>৳{data.paid_amount.toLocaleString()}</span>
          </div>
          {data.payment_text && (
            <div className="flex justify-between text-gray-600" data-testid="invoice-payment-channel">
              <span>Paid via:</span>
              <span>{data.payment_text}</span>
            </div>
          )}
          <div
            className={`flex justify-between font-bold ${
              data.due_amount > 0 ? 'text-red-700' : 'text-gray-700'
            }`}
          >
            <span>Due Balance:</span>
            <span>৳{data.due_amount.toLocaleString()}</span>
          </div>
        </div>

        {/* Simulated Barcode */}
        <div className="text-center my-2 border-t border-dashed border-gray-300 pt-1.5">
          <div className="inline-block tracking-[0.25em] font-mono text-[11px] font-bold bg-gray-100 px-3 py-0.5 rounded border border-gray-300">
            * {data.invoice_number} *
          </div>
          <div className="text-[8px] text-gray-500 mt-0.5">
            Served by: {data.created_by_name} | {data.created_at}
          </div>
        </div>

        {/* Signature lines */}
        <div className="grid grid-cols-2 gap-4 pt-3 mt-1 border-t border-gray-300 text-[9px] text-gray-500 text-center">
          <div>
            <div className="border-b border-gray-400 mb-1 w-24 mx-auto"></div>
            <span>Patient / Attendant</span>
          </div>
          <div>
            <div className="border-b border-gray-400 mb-1 w-24 mx-auto"></div>
            <span>Authorized Signatory</span>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#1B1B0E]/60 backdrop-blur-xs animate-in fade-in duration-200"
      data-testid="dual-copy-invoice-modal"
    >
      <div className="relative w-full max-w-5xl bg-white border border-[#DCDAD4] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[95vh]">
        {/* Modal Controls Header (Hidden in Print) */}
        <div className="flex items-center justify-between px-6 py-3.5 bg-[#FAF9F6] border-b border-[#DCDAD4] no-print">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-[#525333] flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-[#CF8852]" />
              {isPreview ? 'Invoice Preview (Non-Final Draft)' : `Diagnostic Bill #${data.invoice_number}`}
            </span>
            {isPreview && (
              <span
                data-testid="invoice-draft-tag"
                className="px-2 py-0.5 text-[10px] font-bold bg-[#FEF7EC] text-[#8A5608] border border-[#FBE0B2] rounded-full"
              >
                {draftLabel ? `Saved Draft ${draftLabel}` : 'Unsaved Draft'}
              </span>
            )}
            {isPreview && onSaveDraft && (
              <button
                type="button"
                onClick={onSaveDraft}
                disabled={saving}
                data-testid="invoice-preview-save-draft-btn"
                className="inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-semibold text-[#525333] bg-white border border-[#CAC7BE] hover:bg-[#F4F3F0] rounded-xl transition-colors cursor-pointer disabled:opacity-50"
              >
                <FileText className="w-3.5 h-3.5 text-[#525333]" />
                <span>{saving ? 'Saving...' : 'Save Draft'}</span>
              </button>
            )}
            {data.is_duplicate && (
              <span className="px-2 py-0.5 text-[10px] font-bold bg-[#FDF2F0] text-[#9C2417] border border-[#F8CBC6] rounded-full">
                Duplicate Reprint (#{data.reprint_count})
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {isPreview ? (
              <>
                <button
                  type="button"
                  onClick={onBack}
                  disabled={saving}
                  data-testid="invoice-preview-back-btn"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#54524A] bg-white border border-[#CAC7BE] hover:bg-[#F4F3F0] rounded-xl transition-colors cursor-pointer"
                >
                  <ArrowLeft className="w-3.5 h-3.5 text-[#54524A]" />
                  <span>Back & Correct</span>
                </button>

                <button
                  type="button"
                  onClick={onSave}
                  disabled={saving}
                  data-testid="invoice-preview-finalize-btn"
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold text-white bg-[#525333] hover:bg-[#444529] rounded-xl transition-colors shadow-xs cursor-pointer disabled:opacity-50"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{saving ? 'Finalizing...' : 'Finalize'}</span>
                </button>

                <button
                  type="button"
                  onClick={onSaveAndPrint}
                  disabled={saving}
                  data-testid="invoice-preview-finalize-print-btn"
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold text-white bg-[#CF8852] hover:bg-[#B7703B] rounded-xl transition-colors shadow-xs cursor-pointer disabled:opacity-50"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>{saving ? 'Finalizing...' : 'Finalize & Print'}</span>
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={handlePrint}
                data-testid="invoice-print-btn"
                className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold text-white bg-[#CF8852] hover:bg-[#B7703B] rounded-xl transition-colors shadow-xs cursor-pointer"
              >
                <Printer className="w-3.5 h-3.5" />
                <span>Print Dual Copy (A4 Landscape)</span>
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              data-testid="invoice-preview-close-btn"
              className="p-1.5 text-[#6D6A60] hover:text-[#1B1B0E] hover:bg-[#E8E7E3] rounded-lg transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Dual Copy Printable Area */}
        <div className="p-5 overflow-y-auto bg-[#F4F3F0] flex-1 print:bg-white print:p-0 print:m-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative print:grid-cols-2 print:gap-4 print:w-full">
            {/* Cut line indicator for screen view */}
            <div className="hidden md:flex absolute top-0 bottom-0 left-1/2 -ml-2 items-center justify-center pointer-events-none no-print">
              <div className="h-full border-r border-dashed border-gray-400 flex flex-col justify-around py-4">
                <Scissors className="w-3.5 h-3.5 text-gray-400 rotate-90 my-auto" />
              </div>
            </div>

            {/* Left: Patient Copy */}
            <div className="print:pr-2">
              {renderSingleCopy('Patient Copy')}
            </div>

            {/* Right: Office / Lab Copy */}
            <div className="print:pl-2">
              {renderSingleCopy('Office / Lab Copy')}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

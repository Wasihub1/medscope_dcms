import React from 'react';
import { Printer, X, CheckCircle, FileText } from 'lucide-react';
import { DeliverableReportItem } from '../../types';
import { api } from '../../api/client';

interface PrintableReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  report: DeliverableReportItem | null;
}

export const PrintableReportModal: React.FC<PrintableReportModalProps> = ({
  isOpen,
  onClose,
  report,
}) => {
  if (!isOpen || !report) return null;

  const handlePrint = async () => {
    try {
      await api.getPrintableReport(report.id);
    } catch {
      // non-blocking print audit
    }
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#1B1B0E]/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-white border border-[#DCDAD4] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Controls */}
        <div className="flex items-center justify-between px-6 py-3.5 bg-[#F4F3F0] border-b border-[#E8E7E3] no-print">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-[#CF8852]" />
            <span className="text-xs font-semibold uppercase tracking-wider text-[#6D6A60]">
              Diagnostic Report Preview — v{report.version_number}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium bg-[#525333] hover:bg-[#444529] text-white rounded-lg transition-colors shadow-xs"
            >
              <Printer className="w-3.5 h-3.5" />
              Print Report
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-[#6D6A60] hover:text-[#1B1B0E] hover:bg-[#E8E7E3] rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Printable Report Document (A4 format preview) */}
        <div className="p-8 overflow-y-auto bg-white font-sans text-gray-900 leading-normal print:p-0 print:m-0">
          {/* Header */}
          <div className="border-b-2 border-moss-500 pb-4 mb-5 flex justify-between items-start">
            <div>
              <h1 className="text-xl font-bold text-moss-800 tracking-tight">MEDSCOPE CENTRAL DIAGNOSTICS</h1>
              <p className="text-xs text-gray-600">Department of {report.department}</p>
              <p className="text-[11px] text-gray-500">House 42, Road 11, Dhanmondi, Dhaka | Tel: 01700-000000</p>
            </div>
            <div className="text-right">
              <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-green-100 text-green-800 text-xs font-semibold rounded-md border border-green-200">
                <CheckCircle className="w-3.5 h-3.5" />
                AUTHORIZED FINAL
              </span>
              <p className="text-[10px] text-gray-400 mt-1">Version: {report.version_number}.0</p>
            </div>
          </div>

          {/* Patient Details Grid */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3.5 text-xs grid grid-cols-2 gap-y-2 gap-x-4 mb-6">
            <div>
              <span className="text-gray-500 font-medium">Patient Name: </span>
              <span className="font-semibold text-gray-800">{report.patient_name}</span>
            </div>
            <div>
              <span className="text-gray-500 font-medium">Invoice No: </span>
              <span className="font-semibold text-gray-800">{report.invoice_number}</span>
            </div>
            <div>
              <span className="text-gray-500 font-medium">MRN: </span>
              <span className="font-medium text-gray-800">{report.patient_mrn}</span>
            </div>
            <div>
              <span className="text-gray-500 font-medium">Contact: </span>
              <span className="text-gray-800">{report.patient_phone}</span>
            </div>
            <div>
              <span className="text-gray-500 font-medium">Authorized Date: </span>
              <span className="text-gray-800">
                {report.authorized_at ? new Date(report.authorized_at).toLocaleString('en-GB') : '-'}
              </span>
            </div>
            <div>
              <span className="text-gray-500 font-medium">Authorized By: </span>
              <span className="text-gray-800">{report.authorized_by_name || 'Dr. Anisur Rahman'}</span>
            </div>
          </div>

          {/* Test Name & Result Simulation */}
          <div className="mb-8">
            <h2 className="text-sm font-bold text-gray-800 border-b border-gray-300 pb-1.5 mb-3 uppercase tracking-wide">
              Investigation: {report.test_name}
            </h2>

            <div className="border border-gray-200 rounded-md overflow-hidden text-xs">
              <div className="bg-gray-100 font-semibold text-gray-700 grid grid-cols-12 p-2.5 border-b border-gray-200">
                <span className="col-span-5">Parameter</span>
                <span className="col-span-3 text-center">Observed Result</span>
                <span className="col-span-2 text-center">Unit</span>
                <span className="col-span-2 text-right">Reference Range</span>
              </div>
              <div className="divide-y divide-gray-100">
                <div className="grid grid-cols-12 p-2.5 hover:bg-gray-50">
                  <span className="col-span-5 font-medium">{report.test_name} Index</span>
                  <span className="col-span-3 text-center font-bold text-gray-900">Normal / Reactive</span>
                  <span className="col-span-2 text-center text-gray-500">-</span>
                  <span className="col-span-2 text-right text-gray-600">Negative / Non-reactive</span>
                </div>
                <div className="grid grid-cols-12 p-2.5 hover:bg-gray-50">
                  <span className="col-span-5 font-medium">Clinical Interpretation</span>
                  <span className="col-span-7 font-normal text-gray-700 italic">
                    Within accepted biological reference interval. Correlate clinically.
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Delivery Status Tag */}
          <div className="bg-[#FAF9F6] border border-[#E8E7E3] rounded-lg p-3 text-xs mb-8 flex justify-between items-center">
            <div>
              <span className="text-gray-500">Delivery Status: </span>
              {report.is_delivered ? (
                <span className="text-green-700 font-semibold">
                  Delivered to {report.delivered_to_name} ({report.delivered_to_relation}) on{' '}
                  {report.delivered_at ? new Date(report.delivered_at).toLocaleDateString('en-GB') : ''}
                </span>
              ) : (
                <span className="text-orange-700 font-semibold">Ready for Counter Delivery</span>
              )}
            </div>
            {report.due_amount > 0 && (
              <span className="text-red-700 font-bold px-2 py-0.5 bg-red-50 border border-red-200 rounded">
                Outstanding Due: ৳{report.due_amount.toLocaleString()}
              </span>
            )}
          </div>

          {/* Signatures */}
          <div className="mt-12 pt-6 border-t border-gray-300 grid grid-cols-3 text-center text-xs">
            <div>
              <div className="h-10"></div>
              <p className="font-semibold text-gray-800">Medical Technologist</p>
              <p className="text-[10px] text-gray-500">Department of {report.department}</p>
            </div>
            <div>
              <div className="h-10"></div>
              <p className="font-semibold text-gray-800">Quality Manager</p>
              <p className="text-[10px] text-gray-500">MedScope Central</p>
            </div>
            <div>
              <div className="h-10"></div>
              <p className="font-semibold text-gray-800">{report.authorized_by_name || 'Consultant Pathologist'}</p>
              <p className="text-[10px] text-gray-500">MBBS, FCPS, M.Phil</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};


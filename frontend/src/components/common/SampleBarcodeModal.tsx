import React from 'react';
import { Printer, X, Tag } from 'lucide-react';
import { BarcodeLabelData } from '../../types';

interface SampleBarcodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  labelData: BarcodeLabelData | null;
}

export const SampleBarcodeModal: React.FC<SampleBarcodeModalProps> = ({
  isOpen,
  onClose,
  labelData,
}) => {
  if (!isOpen || !labelData) return null;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#1B1B0E]/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-white border border-[#DCDAD4] rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Modal Controls (Hidden in Print) */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-[#F4F3F0] border-b border-[#E8E7E3] no-print">
          <div className="flex items-center gap-2">
            <Tag className="w-4 h-4 text-[#525333]" />
            <span className="text-xs font-semibold uppercase tracking-wider text-[#54524A]">
              Specimen Barcode Label (50mm × 30mm)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              data-testid="print-barcode-btn"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-[#525333] hover:bg-[#3E3F27] text-white rounded-xl transition-colors shadow-xs"
            >
              <Printer className="w-3.5 h-3.5" />
              Print Label
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-[#6D6A60] hover:text-[#1B1B0E] hover:bg-[#E8E7E3] rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Printable Area (Simulating 50mm x 30mm diagnostic center thermal sticker) */}
        <div className="p-8 flex justify-center bg-[#F9F8F5]">
          <div
            id="printable-barcode-label"
            className="w-[260px] bg-white border border-gray-400 p-2.5 rounded-sm shadow-md font-sans text-black select-none print:shadow-none print:border-none print:m-0 print:p-1"
          >
            {/* Header: Center Name & Specimen Type */}
            <div className="flex items-center justify-between border-b border-black pb-0.5 mb-1 text-[10px] leading-tight">
              <span className="font-extrabold uppercase tracking-tight">MedScope Lab</span>
              <span className="font-semibold text-[9px] uppercase px-1 bg-gray-100 rounded">
                {labelData.sample_type || 'Specimen'}
              </span>
            </div>

            {/* Patient Demographic Line */}
            <div className="text-[10px] leading-tight font-bold truncate">
              {labelData.patient_name}
            </div>
            <div className="flex items-center justify-between text-[9px] text-gray-800 leading-tight">
              <span>{labelData.patient_code}</span>
              <span>
                {labelData.patient_gender || 'U'}
                {labelData.patient_age ? ` / ${labelData.patient_age}` : ''}
              </span>
            </div>

            {/* Investigation Code & Name */}
            <div className="mt-1 pt-0.5 border-t border-dotted border-gray-300 text-[9px] font-semibold flex items-center justify-between">
              <span className="truncate max-w-[170px]">{labelData.test_name}</span>
              <span className="font-mono font-bold bg-gray-100 px-1 rounded">{labelData.test_code}</span>
            </div>

            {/* Vector Barcode Container */}
            <div className="my-1.5 flex flex-col items-center justify-center">
              <div
                className="w-full flex justify-center [&_svg]:max-w-full [&_svg]:h-auto"
                dangerouslySetInnerHTML={{ __html: labelData.barcode_svg }}
              />
            </div>

            {/* Footer: Date & Sample ID */}
            <div className="flex items-center justify-between text-[8px] text-gray-700 leading-tight border-t border-gray-200 pt-0.5">
              <span>
                {labelData.collected_at
                  ? new Date(labelData.collected_at).toLocaleString([], {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : 'Pending'}
              </span>
              <span className="font-mono font-bold">{labelData.sample_code}</span>
            </div>
          </div>
        </div>

        {/* Informational Guidance Footer */}
        <div className="px-5 py-3 bg-white border-t border-[#E8E7E3] text-[11px] text-[#6D6A60] flex items-center justify-between no-print">
          <span>Standard format: Code 128 (Thermal roll 50×30mm / 50×25mm)</span>
          <span className="font-mono text-[10px] text-[#525333] font-semibold">Strictly Financial-Free</span>
        </div>
      </div>
    </div>
  );
};


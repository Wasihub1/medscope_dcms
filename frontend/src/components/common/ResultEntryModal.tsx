import React, { useState, useEffect } from 'react';
import {
  X,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Save,
  Send,
  Loader2,
  Stethoscope,
  Activity,
  AlertCircle,
} from 'lucide-react';
import { Modal } from './Modal';
import { api } from '../../api/client';
import { TechnicianWorklistItem, ResultTemplateData, ComponentResultInput } from '../../types';

interface ResultEntryModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: TechnicianWorklistItem | null;
  onSuccess: () => void;
  showToast: (toast: { type: 'success' | 'error' | 'warning'; title: string; message: string }) => void;
}

export const ResultEntryModal: React.FC<ResultEntryModalProps> = ({
  isOpen,
  onClose,
  order,
  onSuccess,
  showToast,
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [template, setTemplate] = useState<ResultTemplateData | null>(null);

  // Form states
  const [componentValues, setComponentValues] = useState<{ [key: string]: { value: string; comment: string } }>({});
  const [findings, setFindings] = useState<string>('');
  const [impression, setImpression] = useState<string>('');
  const [comments, setComments] = useState<string>('');

  // Structured USG fields
  const [usgLiver, setUsgLiver] = useState<string>('Normal in size and echotexture. No focal lesion noted.');
  const [usgGallbladder, setUsgGallbladder] = useState<string>('Normal in size and wall thickness. Lumen is clear of calculi.');
  const [usgSpleen, setUsgSpleen] = useState<string>('Normal in size and parenchymal echogenicity.');
  const [usgPancreas, setUsgPancreas] = useState<string>('Visualized portions appear normal.');
  const [usgKidneys, setUsgKidneys] = useState<string>('Both kidneys are normal in size, shape and position. Cortical thickness preserved. No calculus or hydronephrosis.');
  const [usgBladder, setUsgBladder] = useState<string>('Well filled, wall thickness is normal. No calculus or mass.');
  const [usgPelvis, setUsgPelvis] = useState<string>('Prostate/Pelvic organs appear unremarkable for age.');

  useEffect(() => {
    if (isOpen && order) {
      setLoading(true);
      api
        .getResultTemplate(order.test_order_id)
        .then((data: ResultTemplateData) => {
          setTemplate(data);

          // Populate existing values if available
          const initialValues: { [key: string]: { value: string; comment: string } } = {};
          if (data.existing_result && data.existing_result.items) {
            data.existing_result.items.forEach((it) => {
              const key = it.test_component_id ? `comp_${it.test_component_id}` : `code_${it.component_code}`;
              initialValues[key] = {
                value: it.value,
                comment: it.comment || '',
              };
            });
            setFindings(data.existing_result.findings || '');
            setImpression(data.existing_result.impression || '');
            setComments(data.existing_result.comments || '');

            if (data.existing_result.structured_data) {
              const sd = data.existing_result.structured_data;
              if (sd.liver) setUsgLiver(sd.liver);
              if (sd.gallbladder) setUsgGallbladder(sd.gallbladder);
              if (sd.spleen) setUsgSpleen(sd.spleen);
              if (sd.pancreas) setUsgPancreas(sd.pancreas);
              if (sd.kidneys) setUsgKidneys(sd.kidneys);
              if (sd.bladder) setUsgBladder(sd.bladder);
              if (sd.pelvis) setUsgPelvis(sd.pelvis);
            }
          } else {
            // Default blank values
            data.components.forEach((c) => {
              initialValues[`comp_${c.id}`] = { value: '', comment: '' };
            });
            setFindings('');
            setImpression('');
            setComments('');
          }
          setComponentValues(initialValues);
        })
        .catch((err: any) => {
          showToast({
            type: 'error',
            title: 'Failed to Load Template',
            message: err.message || 'Could not fetch result entry template.',
          });
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, order]);

  // Handle numeric component input change
  const handleComponentChange = (key: string, value: string) => {
    setComponentValues((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        value,
      },
    }));
  };

  const handleCommentChange = (key: string, comment: string) => {
    setComponentValues((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        comment,
      },
    }));
  };

  // Helper to calculate live flag preview
  const getLiveFlag = (c: any, valStr: string) => {
    if (!valStr || !valStr.trim()) return null;
    const v = parseFloat(valStr.trim());
    if (isNaN(v)) return null;

    if (c.impossible_min !== null && c.impossible_min !== undefined && v < c.impossible_min) {
      return { flag: 'IMPOSSIBLE_LOW', label: 'IMPOSSIBLE LOW', color: 'bg-red-600 text-white animate-pulse' };
    }
    if (c.impossible_max !== null && c.impossible_max !== undefined && v > c.impossible_max) {
      return { flag: 'IMPOSSIBLE_HIGH', label: 'IMPOSSIBLE HIGH', color: 'bg-red-600 text-white animate-pulse' };
    }
    if (c.critical_min !== null && c.critical_min !== undefined && v < c.critical_min) {
      return { flag: 'CRITICAL', label: 'CRITICAL LOW', color: 'bg-rose-100 text-rose-800 border-rose-300 font-bold' };
    }
    if (c.critical_max !== null && c.critical_max !== undefined && v > c.critical_max) {
      return { flag: 'CRITICAL', label: 'CRITICAL HIGH', color: 'bg-rose-100 text-rose-800 border-rose-300 font-bold' };
    }
    if (c.ref_min !== null && c.ref_min !== undefined && v < c.ref_min) {
      return { flag: 'LOW', label: 'LOW', color: 'bg-amber-100 text-amber-800 border-amber-300' };
    }
    if (c.ref_max !== null && c.ref_max !== undefined && v > c.ref_max) {
      return { flag: 'HIGH', label: 'HIGH', color: 'bg-orange-100 text-orange-800 border-orange-300' };
    }
    if (c.ref_min !== null || c.ref_max !== null) {
      return { flag: 'NORMAL', label: 'NORMAL', color: 'bg-emerald-100 text-emerald-800 border-emerald-300' };
    }
    return null;
  };

  const handleSubmit = async (submitStatus: 'DRAFT' | 'ENTERED') => {
    if (!order || !template) return;

    // Check impossible values on client
    for (const c of template.components) {
      const val = componentValues[`comp_${c.id}`]?.value;
      if (val && val.trim()) {
        const num = parseFloat(val.trim());
        if (!isNaN(num)) {
          if (c.impossible_min !== null && c.impossible_min !== undefined && num < c.impossible_min) {
            showToast({
              type: 'error',
              title: 'Impossible Value Detected',
              message: `Entered value ${num} for ${c.name} is below impossible minimum of ${c.impossible_min} ${c.unit || ''}.`,
            });
            return;
          }
          if (c.impossible_max !== null && c.impossible_max !== undefined && num > c.impossible_max) {
            showToast({
              type: 'error',
              title: 'Impossible Value Detected',
              message: `Entered value ${num} for ${c.name} exceeds impossible maximum of ${c.impossible_max} ${c.unit || ''}.`,
            });
            return;
          }
        }
      }
    }

    // Build payload items
    const items: ComponentResultInput[] = template.components.map((c) => {
      const field = componentValues[`comp_${c.id}`] || { value: '', comment: '' };
      return {
        component_id: c.id,
        component_name: c.name,
        component_code: c.code,
        value: field.value,
        unit: c.unit,
        reference_range: c.reference_range_text,
        ref_min: c.ref_min,
        ref_max: c.ref_max,
        critical_min: c.critical_min,
        critical_max: c.critical_max,
        impossible_min: c.impossible_min,
        impossible_max: c.impossible_max,
        comment: field.comment,
        sort_order: c.sort_order,
      };
    });

    const isUsg = template.report_template === 'ULTRASOUND' || template.test_code.startsWith('USG');
    const structuredData = isUsg
      ? {
          liver: usgLiver,
          gallbladder: usgGallbladder,
          spleen: usgSpleen,
          pancreas: usgPancreas,
          kidneys: usgKidneys,
          bladder: usgBladder,
          pelvis: usgPelvis,
        }
      : undefined;

    setSubmitting(true);
    try {
      await api.saveResult(order.test_order_id, {
        status: submitStatus,
        findings: findings.trim() || undefined,
        impression: impression.trim() || undefined,
        comments: comments.trim() || undefined,
        structured_data: structuredData,
        items,
      });

      showToast({
        type: 'success',
        title: submitStatus === 'DRAFT' ? 'Draft Saved' : 'Results Recorded',
        message:
          submitStatus === 'DRAFT'
            ? 'Result draft saved successfully.'
            : `Results successfully entered for Order #${order.test_order_id}.`,
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Result Submission Failed',
        message: err.message || 'Could not record clinical results.',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const isUsg = template?.report_template === 'ULTRASOUND' || template?.test_code.startsWith('USG');
  const isNarrative = template?.report_template === 'NARRATIVE' && !isUsg;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Clinical Result Entry — Order #${order?.test_order_id || ''}`}
      maxWidth="xl"
    >
      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center gap-2">
          <Loader2 className="w-8 h-8 animate-spin text-[#CF8852]" />
          <span className="text-xs text-[#6D6A60]">Loading test configuration and reference ranges...</span>
        </div>
      ) : !template ? (
        <div className="py-8 text-center text-rose-700 text-xs">
          Unable to load result entry template. Please check test configuration.
        </div>
      ) : (
        <div className="space-y-4">
          {/* Patient Demographics & Test Meta (Strict Financial Privacy: No prices or dues) */}
          <div className="bg-[#FAF9F5] border border-[#E8E7E3] rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="space-y-0.5">
              <span className="font-bold text-[#1B1B0E] text-sm block">{template.patient_name}</span>
              <span className="text-[#6D6A60] block">
                MRN: <strong className="text-[#1B1B0E]">{template.patient_code}</strong> | {template.patient_gender} |{' '}
                {template.patient_age}
              </span>
            </div>

            <div className="space-y-0.5 text-right">
              <span className="font-bold text-[#1B1B0E] block">{template.test_name}</span>
              <span className="text-[11px] text-[#6D6A60] block">
                Invoice: <strong>{template.invoice_no}</strong> | Sample:{' '}
                <strong className="text-[#525333]">{template.sample_code || 'N/A (Imaging)'}</strong>
              </span>
            </div>
          </div>

          {/* Test Status Banner */}
          <div className="flex items-center justify-between text-xs px-3 py-1.5 bg-[#F5F4F0] rounded-lg border border-[#E8E7E3]">
            <span className="text-[#54524A]">
              Template: <strong className="text-[#1B1B0E]">{template.report_template}</strong> | Department:{' '}
              <strong className="text-[#1B1B0E]">{template.department}</strong>
            </span>
            {template.existing_result && (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#525333]">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Saved Status: {template.existing_result.status}
              </span>
            )}
          </div>

          {/* Form Content: Numeric Table */}
          {template.components.length > 0 && (
            <div className="border border-[#E8E7E3] rounded-xl overflow-hidden shadow-xs">
              <div className="bg-[#F4F3F0] px-3 py-2 border-b border-[#E8E7E3] flex items-center justify-between">
                <span className="text-xs font-bold text-[#1B1B0E] flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-[#525333]" />
                  Numeric Investigation Parameters
                </span>
                <span className="text-[10px] text-[#8E8A7E]">
                  Flags calculated automatically against clinical limits
                </span>
              </div>

              <div className="overflow-x-auto max-h-72">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-[#FAF9F5] text-[#54524A] font-semibold sticky top-0 border-b border-[#E8E7E3]">
                    <tr>
                      <th className="py-2 px-3">Investigation Component</th>
                      <th className="py-2 px-3 w-36">Result Value *</th>
                      <th className="py-2 px-2 w-20">Unit</th>
                      <th className="py-2 px-3 w-40">Reference Range</th>
                      <th className="py-2 px-2 w-28 text-center">Auto Flag</th>
                      <th className="py-2 px-3 w-44">Observation / Note</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E8E7E3]">
                    {template.components.map((c) => {
                      const field = componentValues[`comp_${c.id}`] || { value: '', comment: '' };
                      const flagObj = getLiveFlag(c, field.value);
                      const isImp =
                        flagObj?.flag === 'IMPOSSIBLE_LOW' || flagObj?.flag === 'IMPOSSIBLE_HIGH';

                      return (
                        <tr
                          key={c.id}
                          className={`hover:bg-[#FFFAF5] transition-colors ${isImp ? 'bg-red-50' : ''}`}
                        >
                          <td className="py-2 px-3">
                            <span className="font-semibold text-[#1B1B0E] block">{c.name}</span>
                            {c.code && (
                              <span className="text-[10px] text-[#8E8A7E] font-mono block">{c.code}</span>
                            )}
                          </td>
                          <td className="py-2 px-3">
                            <input
                              type="text"
                              value={field.value}
                              onChange={(e) => handleComponentChange(`comp_${c.id}`, e.target.value)}
                              placeholder="Enter value..."
                              className={`w-full px-2.5 py-1.5 text-xs font-semibold rounded-lg border focus:outline-none ${
                                isImp
                                  ? 'border-red-600 bg-red-100 text-red-900 focus:border-red-700'
                                  : 'border-[#CAC7BE] focus:border-[#525333] bg-white'
                              }`}
                            />
                            {c.impossible_max !== null && c.impossible_max !== undefined && (
                              <span className="text-[9px] text-[#8E8A7E] block mt-0.5">
                                Limit: {c.impossible_min ?? 0}–{c.impossible_max}
                              </span>
                            )}
                          </td>
                          <td className="py-2 px-2 text-[#6D6A60] font-mono text-[11px]">{c.unit || '-'}</td>
                          <td className="py-2 px-3 text-[#54524A] text-[11px]">
                            {c.reference_range_text || '-'}
                          </td>
                          <td className="py-2 px-2 text-center">
                            {flagObj ? (
                              <span
                                className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${flagObj.color}`}
                              >
                                {flagObj.label}
                              </span>
                            ) : (
                              <span className="text-[#8E8A7E] text-[10px]">-</span>
                            )}
                          </td>
                          <td className="py-2 px-3">
                            <input
                              type="text"
                              value={field.comment}
                              onChange={(e) => handleCommentChange(`comp_${c.id}`, e.target.value)}
                              placeholder="Optional note..."
                              className="w-full px-2 py-1 text-xs rounded border border-[#E8E7E3] focus:border-[#525333] bg-white"
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Structured Ultrasound Template */}
          {isUsg && (
            <div className="border border-purple-200 bg-purple-50/30 rounded-xl p-3.5 space-y-3">
              <div className="flex items-center gap-1.5 text-xs font-bold text-purple-950 border-b border-purple-200 pb-2">
                <Stethoscope className="w-4 h-4 text-purple-800" />
                <span>Ultrasound Structured Examination Findings (Module 13.6)</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block font-semibold text-[#1B1B0E] mb-1">Liver</label>
                  <input
                    type="text"
                    value={usgLiver}
                    onChange={(e) => setUsgLiver(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-[#CAC7BE] rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-[#1B1B0E] mb-1">Gallbladder & Biliary Tree</label>
                  <input
                    type="text"
                    value={usgGallbladder}
                    onChange={(e) => setUsgGallbladder(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-[#CAC7BE] rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-[#1B1B0E] mb-1">Spleen</label>
                  <input
                    type="text"
                    value={usgSpleen}
                    onChange={(e) => setUsgSpleen(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-[#CAC7BE] rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-[#1B1B0E] mb-1">Pancreas</label>
                  <input
                    type="text"
                    value={usgPancreas}
                    onChange={(e) => setUsgPancreas(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-[#CAC7BE] rounded-lg text-xs"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block font-semibold text-[#1B1B0E] mb-1">Kidneys (Both)</label>
                  <input
                    type="text"
                    value={usgKidneys}
                    onChange={(e) => setUsgKidneys(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-[#CAC7BE] rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-[#1B1B0E] mb-1">Urinary Bladder</label>
                  <input
                    type="text"
                    value={usgBladder}
                    onChange={(e) => setUsgBladder(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-[#CAC7BE] rounded-lg text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-[#1B1B0E] mb-1">Prostate / Pelvis</label>
                  <input
                    type="text"
                    value={usgPelvis}
                    onChange={(e) => setUsgPelvis(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-white border border-[#CAC7BE] rounded-lg text-xs"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Narrative / Impression Fields (Section 3.5 & 3.6) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-semibold text-[#1B1B0E] mb-1">
                Clinical Findings / Detailed Observations
              </label>
              <textarea
                value={findings}
                onChange={(e) => setFindings(e.target.value)}
                placeholder="Enter narrative findings or macroscopic observations..."
                rows={3}
                className="w-full px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl text-xs focus:outline-none focus:border-[#525333]"
              />
            </div>

            <div>
              <label className="block font-semibold text-[#1B1B0E] mb-1">Impression / Conclusion</label>
              <textarea
                value={impression}
                onChange={(e) => setImpression(e.target.value)}
                placeholder="Diagnostic impression or summary..."
                rows={3}
                className="w-full px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl text-xs focus:outline-none focus:border-[#525333]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
              General Comments / Method Remarks
            </label>
            <input
              type="text"
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder="e.g. Test performed by Automated Analyzer Cobas c311. Repeat run confirmed."
              className="w-full px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl text-xs focus:outline-none focus:border-[#525333]"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-3 border-t border-[#E8E7E3]">
            <span className="text-[11px] text-[#6D6A60] italic">
              Saving results records operational progress. Final report authorization belongs to Module 14.
            </span>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-medium text-[#54524A] hover:bg-[#F4F3F0] rounded-xl cursor-pointer"
              >
                Close
              </button>

              <button
                type="button"
                disabled={submitting}
                onClick={() => handleSubmit('DRAFT')}
                className="px-3.5 py-2 text-xs font-semibold text-[#525333] bg-[#E8E7E3] hover:bg-[#DCDAD4] border border-[#CAC7BE] rounded-xl transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <Save className="w-3.5 h-3.5" />
                {submitting ? 'Saving...' : 'Save Draft'}
              </button>

              <button
                type="button"
                disabled={submitting}
                onClick={() => handleSubmit('ENTERED')}
                className="px-4 py-2 text-xs font-bold text-white bg-[#525333] hover:bg-[#3E3F27] rounded-xl transition-colors shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <Send className="w-3.5 h-3.5" />
                {submitting ? 'Submitting...' : 'Submit Results'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
};

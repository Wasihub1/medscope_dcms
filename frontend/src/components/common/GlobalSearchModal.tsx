import React, { useState, useEffect, useRef } from 'react';
import { Search, User, FileText, Activity, ArrowRight, Loader2, X, FlaskConical, Droplet } from 'lucide-react';
import { api } from '../../api/client';
import { GlobalSearchResult } from '../../types';

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectResult: (result: GlobalSearchResult) => void;
}

export const GlobalSearchModal: React.FC<GlobalSearchModalProps> = ({
  isOpen,
  onClose,
  onSelectResult,
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GlobalSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.searchGlobal(query.trim());
        setResults(res);
        setSelectedIndex(0);
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < results.length - 1 ? prev + 1 : prev));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (results[selectedIndex]) {
        onSelectResult(results[selectedIndex]);
        onClose();
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-[#1B1B0E]/40 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="w-full max-w-2xl bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-[#E8E7E3] bg-white">
          <Search className="w-5 h-5 text-[#8E8A7E] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search patients by name/phone/MRN, invoices by bill #, reports..."
            className="w-full text-base bg-transparent border-none outline-none text-[#1B1B0E] placeholder:text-[#B1ADA2]"
          />
          {loading ? (
            <Loader2 className="w-5 h-5 text-[#CF8852] animate-spin shrink-0" />
          ) : query ? (
            <button
              onClick={() => setQuery('')}
              className="p-1 text-[#8E8A7E] hover:text-[#1B1B0E] rounded-md transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          ) : (
            <kbd className="hidden sm:inline-block px-2 py-0.5 text-[10px] font-mono text-[#8E8A7E] bg-[#E8E7E3] rounded border border-[#CAC7BE]">
              ESC
            </kbd>
          )}
        </div>

        {/* Results List */}
        <div className="max-h-[60vh] overflow-y-auto p-2 divide-y divide-[#E8E7E3]/60">
          {query.length >= 2 && results.length === 0 && !loading && (
            <div className="p-8 text-center text-sm text-[#8E8A7E]">
              No records found matching "<span className="font-semibold text-[#54524A]">{query}</span>"
            </div>
          )}

          {query.length < 2 && (
            <div className="p-6 text-center text-xs text-[#8E8A7E]">
              Type at least 2 characters to search across Patients, Invoices, Tests, Reports, and Samples...
            </div>
          )}

          {results.map((result, idx) => {
            const isSelected = idx === selectedIndex;
            const Icon = {
              PATIENT: User,
              INVOICE: FileText,
              REPORT: Activity,
              TEST: FlaskConical,
              SAMPLE: Droplet,
            }[result.category] || Activity;

            const categoryLabel = {
              PATIENT: 'Patient',
              INVOICE: 'Invoice',
              REPORT: 'Report',
              TEST: 'Test',
              SAMPLE: 'Sample',
            }[result.category] || 'Item';

            const categoryStyle = {
              PATIENT: 'bg-[#EDF5F7] text-[#185B68] border-[#C4E2E7]',
              INVOICE: 'bg-[#FAF3EC] text-[#96572A] border-[#E6C4A7]',
              REPORT: 'bg-[#EDF7EE] text-[#1E6327] border-[#C3E6C7]',
              TEST: 'bg-[#F4F1FA] text-[#55388A] border-[#D9CEEB]',
              SAMPLE: 'bg-[#FEF6E9] text-[#8C5815] border-[#FCE1BD]',
            }[result.category] || 'bg-gray-100 text-gray-800 border-gray-200';

            return (
              <div
                key={`${result.category}-${result.id}-${idx}`}
                onClick={() => {
                  onSelectResult(result);
                  onClose();
                }}
                onMouseEnter={() => setSelectedIndex(idx)}
                className={`flex items-center justify-between p-3.5 rounded-xl cursor-pointer transition-colors ${
                  isSelected ? 'bg-[#E8E7E3]/80' : 'hover:bg-[#F4F3F0]'
                }`}
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="p-2 bg-white rounded-lg border border-[#DCDAD4] shadow-xs text-[#525333]">
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-[#1B1B0E] truncate">{result.title}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${categoryStyle}`}>
                        {categoryLabel}
                      </span>
                    </div>
                    <p className="text-xs text-[#6D6A60] truncate mt-0.5">{result.subtitle}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 pl-3 shrink-0">
                  {result.status && (
                    <span className="text-[11px] font-medium px-2 py-0.5 bg-white border border-[#DCDAD4] rounded-md text-[#54524A]">
                      {result.status}
                    </span>
                  )}
                  <ArrowRight className={`w-4 h-4 text-[#8E8A7E] transition-transform ${isSelected ? 'translate-x-1 text-[#CF8852]' : ''}`} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer info */}
        <div className="px-4 py-2.5 bg-[#F4F3F0] border-t border-[#E8E7E3] text-[11px] text-[#8E8A7E] flex justify-between items-center">
          <div className="flex items-center gap-3">
            <span>
              Navigate <kbd className="px-1.5 py-0.5 bg-white rounded border border-[#CAC7BE]">↑</kbd>{' '}
              <kbd className="px-1.5 py-0.5 bg-white rounded border border-[#CAC7BE]">↓</kbd>
            </span>
            <span>
              Select <kbd className="px-1.5 py-0.5 bg-white rounded border border-[#CAC7BE]">↵</kbd>
            </span>
          </div>
          <span>MedScope Global Search</span>
        </div>
      </div>
    </div>
  );
};


import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  User,
  FileText,
  Activity,
  ArrowRight,
  Loader2,
  X,
  FlaskConical,
  Droplet,
  UserCheck,
  Shield,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Badge } from '../common/Badge';
import { api } from '../../api/client';
import { GlobalSearchResult } from '../../types';

export const Header: React.FC = () => {
  const { role, actorMode, staffName, department, businessDay, toggleRole } = useAuth();
  const navigate = useNavigate();

  // Inline Search State
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GlobalSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounced Search Query
  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setResults([]);
      setDropdownOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.searchGlobal(query.trim());
        setResults(res);
        setSelectedIndex(0);
        setDropdownOpen(true);
      } catch (err) {
        console.error('Inline search failed:', err);
      } finally {
        setLoading(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query]);

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectResult = (result: GlobalSearchResult) => {
    setDropdownOpen(false);
    setQuery('');
    if (result.category === 'PATIENT') {
      navigate(`/patients?search=${encodeURIComponent(result.title)}&id=${result.id}`);
    } else if (result.category === 'INVOICE') {
      navigate(`/invoices?search=${encodeURIComponent(result.title)}&id=${result.id}`);
    } else if (result.category === 'REPORT') {
      navigate(`/reports?search=${encodeURIComponent(result.title)}&id=${result.id}`);
    } else if (result.category === 'TEST') {
      navigate(`/invoices/new?test_id=${result.id}`);
    } else if (result.category === 'SAMPLE') {
      navigate(`/reports?search=${encodeURIComponent(result.title)}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!dropdownOpen && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      if (results.length > 0) setDropdownOpen(true);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < results.length - 1 ? prev + 1 : prev));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (results[selectedIndex]) {
        handleSelectResult(results[selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      setDropdownOpen(false);
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'PATIENT':
        return <User className="w-4 h-4 text-[#525333]" />;
      case 'INVOICE':
        return <FileText className="w-4 h-4 text-[#CF8852]" />;
      case 'REPORT':
        return <Activity className="w-4 h-4 text-emerald-600" />;
      case 'TEST':
        return <FlaskConical className="w-4 h-4 text-indigo-600" />;
      case 'SAMPLE':
        return <Droplet className="w-4 h-4 text-rose-600" />;
      default:
        return <Search className="w-4 h-4 text-[#8E8A7E]" />;
    }
  };

  // Group results by category
  const categories = ['PATIENT', 'INVOICE', 'REPORT', 'TEST', 'SAMPLE'] as const;
  const categoryLabels = {
    PATIENT: 'Patients',
    INVOICE: 'Invoices & Bills',
    REPORT: 'Diagnostic Reports',
    TEST: 'Tests Catalog',
    SAMPLE: 'Specimens',
  };

  return (
    <header className="h-16 bg-[#FAF9F6] border-b border-[#DCDAD4] px-6 flex items-center justify-between shrink-0 shadow-2xs z-30">
      {/* Left: Inline Global Search Bar with Anchored Dropdown (Item 08 & 09) */}
      <div ref={containerRef} className="relative flex-1 max-w-md">
        <div className="flex items-center gap-2 px-3.5 py-1.5 bg-[#F4F3F0] focus-within:bg-white text-[#1B1B0E] rounded-xl border border-[#CAC7BE] focus-within:border-[#CF8852] focus-within:ring-1 focus-within:ring-[#CF8852] transition-all shadow-2xs">
          <Search className="w-4 h-4 text-[#8E8A7E] shrink-0" />
          <input
            id="medscope-global-search"
            ref={inputRef}
            type="text"
            data-testid="global-search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => {
              if (results.length > 0) setDropdownOpen(true);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search patients, invoices, tests, reports..."
            className="w-full text-xs bg-transparent border-none outline-none text-[#1B1B0E] placeholder:text-[#8E8A7E]"
          />
          {loading ? (
            <Loader2 className="w-3.5 h-3.5 text-[#CF8852] animate-spin shrink-0" />
          ) : query ? (
            <button
              type="button"
              onClick={() => {
                setQuery('');
                setResults([]);
                setDropdownOpen(false);
              }}
              className="p-0.5 text-[#8E8A7E] hover:text-[#1B1B0E] rounded transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          ) : (
            <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono text-[#8E8A7E] bg-white rounded border border-[#CAC7BE] shrink-0">
              Ctrl + F
            </kbd>
          )}
        </div>

        {/* Anchored Autocomplete Results Dropdown */}
        {dropdownOpen && (
          <div
            data-testid="global-search-dropdown"
            className="absolute top-full left-0 w-full mt-1.5 bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl shadow-2xl max-h-[70vh] overflow-y-auto z-50 p-2 space-y-3 animate-in fade-in zoom-in-98 duration-100"
          >
            {results.length === 0 ? (
              <div className="p-6 text-center text-xs text-[#8E8A7E]">
                No diagnostic records match &quot;{query}&quot;
              </div>
            ) : (
              categories.map((cat) => {
                const catResults = results.filter((r) => r.category === cat);
                if (catResults.length === 0) return null;

                return (
                  <div key={cat} className="space-y-1">
                    <span className="text-[10px] font-bold text-[#6D6A60] uppercase tracking-wider px-2 block">
                      {categoryLabels[cat]} ({catResults.length})
                    </span>
                    <div className="space-y-0.5">
                      {catResults.map((item) => {
                        const globalIndex = results.indexOf(item);
                        const isSelected = globalIndex === selectedIndex;
                        return (
                          <div
                            key={item.id}
                            data-testid={`search-result-${item.category.toLowerCase()}-${item.id}`}
                            onClick={() => handleSelectResult(item)}
                            onMouseEnter={() => setSelectedIndex(globalIndex)}
                            className={`flex items-center justify-between p-2 rounded-xl text-xs cursor-pointer transition-colors ${isSelected ? 'bg-[#E8E7E3] text-[#1B1B0E]' : 'hover:bg-[#F4F3F0] text-[#54524A]'
                              }`}
                          >
                            <div className="flex items-center gap-2.5 min-w-0">
                              <div className="p-1.5 rounded-lg bg-white border border-[#DCDAD4] shrink-0">
                                {getCategoryIcon(item.category)}
                              </div>
                              <div className="min-w-0">
                                <span className="font-semibold block truncate text-[#1B1B0E]">{item.title}</span>
                                <span className="text-[11px] text-[#6D6A60] block truncate">{item.subtitle}</span>
                              </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              {item.status && (
                                <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-white border border-[#DCDAD4] text-[#6D6A60]">
                                  {item.status}
                                </span>
                              )}
                              <ArrowRight className="w-3.5 h-3.5 text-[#8E8A7E]" />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Right: Status Pills & Role Switcher */}
      <div className="flex items-center gap-2 sm:gap-4 shrink-0">
        {/* Business Day Status */}
        <div className="hidden sm:flex items-center gap-2">
          {businessDay ? (
            <Badge variant="success" dot size="md">
              Day #{businessDay.day_number} Open ({businessDay.business_date})
            </Badge>
          ) : (
            <Badge variant="danger" dot size="md">
              Business Day Closed
            </Badge>
          )}
        </div>

        {/* Vertical divider */}
        <div className="h-6 w-px bg-[#DCDAD4]" />

        {/* Role Switcher (For Multi-Role Testing: Receptionist <-> Admin <-> Lab Techs) */}
        <button
          onClick={toggleRole}
          data-testid="role-switcher-button"
          title="Click to cycle between Receptionist, Admin, Tech Kamal (Hematology), and Tech Nasrin (Biochemistry)"
          className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer shadow-2xs ${
            role === 'ADMIN'
              ? 'bg-[#FAF3EC] border-[#CF8852] text-[#96572A] hover:bg-[#F3E4D6]'
              : role === 'LAB_TECH'
              ? 'bg-[#EEF2F6] border-[#4F6B8A] text-[#1E3A5F] hover:bg-[#DEE7F0]'
              : 'bg-[#F2F3EC] border-[#9FA574] text-[#444529] hover:bg-[#E2E4D4]'
          }`}
        >
          {role === 'ADMIN' ? (
            <>
              <Shield className="w-4 h-4 text-[#CF8852]" />
              <span>Admin Mode</span>
            </>
          ) : actorMode === 'LAB_TECH_KAMAL' ? (
            <>
              <FlaskConical className="w-4 h-4 text-[#2B547E]" />
              <span>Tech: Kamal (Hema)</span>
            </>
          ) : actorMode === 'LAB_TECH_NASRIN' ? (
            <>
              <FlaskConical className="w-4 h-4 text-[#2B547E]" />
              <span>Tech: Nasrin (Biochem)</span>
            </>
          ) : (
            <>
              <UserCheck className="w-4 h-4 text-[#525333]" />
              <span>Receptionist Mode</span>
            </>
          )}
          <span className="text-[10px] font-normal underline opacity-80">(Switch)</span>
        </button>

        {/* Staff Identity */}
        <div className="flex items-center gap-3 pl-1">
          <div className={`w-9 h-9 rounded-full text-white flex items-center justify-center font-bold text-xs shadow-xs border ${
            role === 'ADMIN'
              ? 'bg-[#CF8852] border-[#A85F2C]'
              : role === 'LAB_TECH'
              ? 'bg-[#2B547E] border-[#1C3B5E]'
              : 'bg-[#525333] border-[#373720]'
          }`}>
            {role === 'ADMIN' ? 'TI' : actorMode === 'LAB_TECH_KAMAL' ? 'KH' : actorMode === 'LAB_TECH_NASRIN' ? 'NS' : 'FA'}
          </div>
          <div className="hidden md:block text-left">
            <span className="text-xs font-semibold text-[#1B1B0E] block leading-tight">
              {staffName.split(' ')[0]} {staffName.split(' ')[1] || ''}
            </span>
            <span className="text-[10px] text-[#6D6A60] block leading-tight">
              {department}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};

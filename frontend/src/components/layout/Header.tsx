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
  Shield,
  LogOut,
  ChevronDown,
  Check,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Badge } from '../common/Badge';
import { api } from '../../api/client';
import { GlobalSearchResult, Role } from '../../types';
import { getRoleHomeRoute } from '../../utils/navigation';

export const Header: React.FC = () => {
  const { user, role, staffName, department, businessDay, logout, switchRole } = useAuth();
  const navigate = useNavigate();

  // Inline Search State
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GlobalSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // User profile dropdown menu state
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

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

  // Click outside to close dropdowns
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
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

  const handleSignOut = async () => {
    setUserMenuOpen(false);
    await logout();
    navigate('/login', { replace: true });
  };

  const handleRoleSwitch = async (newRole: Role) => {
    if (newRole === role) return;
    try {
      await switchRole(newRole);
      setUserMenuOpen(false);
      navigate(getRoleHomeRoute(newRole));
    } catch (err: unknown) {
      console.error('Failed to switch acting role:', err);
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'PATIENT':
        return <User className="w-4 h-4 text-[#525333]" />;
      case 'INVOICE':
        return <FileText className="w-4 h-4 text-[#CF8852]" />;
      case 'REPORT':
        return <Activity className="w-4 h-4 text-[#525333]" />;
      case 'TEST':
        return <FlaskConical className="w-4 h-4 text-[#CF8852]" />;
      case 'SAMPLE':
        return <Droplet className="w-4 h-4 text-[#B91C1C]" />;
      default:
        return <Search className="w-4 h-4 text-[#6D6A60]" />;
    }
  };

  // Group search results by category
  const categories = ['PATIENT', 'INVOICE', 'REPORT', 'TEST', 'SAMPLE'] as const;
  const groupedResults = categories.reduce((acc, cat) => {
    const matches = results.filter((r) => r.category === cat);
    if (matches.length > 0) acc[cat] = matches;
    return acc;
  }, {} as Record<string, GlobalSearchResult[]>);

  let flatIndexCounter = 0;

  // Initials for avatar
  const initials = staffName
    ? staffName
        .split(' ')
        .map((p) => p[0])
        .filter(Boolean)
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'MS';

  return (
    <header className="h-16 border-b border-[#DCDAD4] bg-[#F4F3F0] px-4 sm:px-6 flex items-center justify-between gap-4 sticky top-0 z-30">
      {/* Left / Center: Global Search Bar */}
      <div ref={containerRef} className="relative flex-1 max-w-xl">
        <div className="relative flex items-center">
          <Search className="w-4 h-4 absolute left-3.5 text-[#8E8A7E] pointer-events-none" />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded={dropdownOpen}
            aria-autocomplete="list"
            aria-controls="global-search-results"
            id="medscope-global-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => {
              if (results.length > 0) setDropdownOpen(true);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search patients, invoices, reports, tests (Ctrl+F)..."
            className="w-full pl-10 pr-10 py-2 text-xs sm:text-sm bg-white border border-[#DCDAD4] rounded-2xl text-[#1B1B0E] placeholder-[#8E8A7E] focus:outline-none focus:ring-2 focus:ring-[#CF8852] focus:border-transparent transition-all shadow-2xs"
          />
          {loading ? (
            <div className="absolute right-3">
              <Loader2 className="w-4 h-4 text-[#CF8852] animate-spin" />
            </div>
          ) : query ? (
            <button
              onClick={() => {
                setQuery('');
                setResults([]);
                setDropdownOpen(false);
              }}
              className="absolute right-3 p-0.5 text-[#8E8A7E] hover:text-[#1B1B0E] rounded-full hover:bg-[#E8E7E3]"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          ) : (
            <kbd className="hidden sm:inline-block absolute right-3 px-1.5 py-0.5 text-[10px] font-semibold text-[#8E8A7E] bg-[#F4F3F0] border border-[#DCDAD4] rounded">
              Ctrl+F
            </kbd>
          )}
        </div>

        {/* Global Search Results Dropdown */}
        {dropdownOpen && (
          <div
            id="global-search-results"
            role="listbox"
            className="absolute left-0 right-0 top-full mt-2 bg-white border border-[#DCDAD4] rounded-2xl shadow-xl overflow-hidden z-50 max-h-[75vh] overflow-y-auto"
          >
            {results.length === 0 ? (
              <div className="p-4 text-center text-xs text-[#8E8A7E]">
                No matching records found for "{query}"
              </div>
            ) : (
              Object.entries(groupedResults).map(([category, items]) => {
                return (
                  <div key={category} className="border-b border-[#F4F3F0] last:border-b-0">
                    <div className="px-3.5 py-1.5 bg-[#FAF9F7] text-[10px] font-bold tracking-wider text-[#6D6A60] uppercase">
                      {category}s ({items.length})
                    </div>
                    <div className="p-1 space-y-0.5">
                      {items.map((item) => {
                        const globalIndex = flatIndexCounter++;
                        const isSelected = globalIndex === selectedIndex;
                        return (
                          <div
                            key={item.id}
                            data-testid={`search-result-${item.category.toLowerCase()}-${item.id}`}
                            onClick={() => handleSelectResult(item)}
                            onMouseEnter={() => setSelectedIndex(globalIndex)}
                            className={`flex items-center justify-between p-2 rounded-xl text-xs cursor-pointer transition-colors ${
                              isSelected ? 'bg-[#E8E7E3] text-[#1B1B0E]' : 'hover:bg-[#F4F3F0] text-[#54524A]'
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

      {/* Right: Business Day Status & Authenticated User Menu */}
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

        {/* Authenticated Staff User Menu (Prompt 09) */}
        <div ref={userMenuRef} className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            data-testid="header-user-menu-btn"
            className="flex items-center gap-2.5 p-1 sm:px-2 sm:py-1.5 rounded-xl hover:bg-[#E8E7E3] transition-colors cursor-pointer text-left"
          >
            <div
              className={`w-9 h-9 rounded-full text-white flex items-center justify-center font-bold text-xs shadow-xs border shrink-0 ${
                role === 'ADMIN' || role === 'OWNER'
                  ? 'bg-[#CF8852] border-[#A85F2C]'
                  : role === 'LAB_TECH'
                  ? 'bg-[#2B547E] border-[#1C3B5E]'
                  : 'bg-[#525333] border-[#373720]'
              }`}
            >
              {initials}
            </div>
            <div className="hidden md:block">
              <span className="text-xs font-semibold text-[#1B1B0E] block leading-tight">
                {staffName.split(' ')[0]} {staffName.split(' ')[1] || ''}
              </span>
              <span className="text-[10px] text-[#6D6A60] block leading-tight">
                {role} • {department}
              </span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-[#8E8A7E] hidden md:block" />
          </button>

          {/* User Menu Dropdown */}
          {userMenuOpen && (
            <div
              data-testid="header-user-dropdown"
              className="absolute right-0 top-full mt-2 w-64 bg-white border border-[#DCDAD4] rounded-2xl shadow-xl overflow-hidden z-50 p-2 text-xs"
            >
              {/* Profile Header */}
              <div className="p-2.5 bg-[#FAF9F7] rounded-xl border border-[#F0EFEA] mb-2">
                <span className="font-bold text-sm text-[#1B1B0E] block truncate">{staffName}</span>
                <span className="text-[#6D6A60] text-[11px] block">@{user?.username}</span>
                <div className="mt-2 flex items-center gap-1.5">
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#E8E7E3] text-[#525333] border border-[#DCDAD4]">
                    Acting: {role}
                  </span>
                  <span className="text-[10px] text-[#8E8A7E] truncate">{department}</span>
                </div>
              </div>

              {/* Role Switcher if user holds multiple roles */}
              {user?.roles && user.roles.length > 1 && (
                <div className="mb-2 pb-2 border-b border-[#F0EFEA]">
                  <span className="px-2 py-1 text-[10px] font-bold text-[#8E8A7E] uppercase tracking-wider block">
                    Switch Acting Role
                  </span>
                  <div className="space-y-0.5 mt-1">
                    {user.roles.map((r) => {
                      const isActive = r === role;
                      return (
                        <button
                          key={r}
                          onClick={() => handleRoleSwitch(r)}
                          data-testid={`switch-role-${r.toLowerCase()}`}
                          className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                            isActive
                              ? 'bg-[#E8E7E3] text-[#1B1B0E] font-semibold'
                              : 'hover:bg-[#F4F3F0] text-[#54524A]'
                          }`}
                        >
                          <span>{r}</span>
                          {isActive && <Check className="w-3.5 h-3.5 text-[#525333]" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Sign Out Action */}
              <button
                onClick={handleSignOut}
                data-testid="sign-out-btn"
                className="w-full flex items-center gap-2 px-2.5 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
              >
                <LogOut className="w-4 h-4 text-rose-600" />
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

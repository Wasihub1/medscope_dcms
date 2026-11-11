import React, { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  PlusCircle,
  Receipt,
  Users,
  GitBranch,
  CreditCard,
  FileCheck,
  RotateCcw,
  CalendarDays,
  UserCircle,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  FlaskConical,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggleCollapse }) => {
  const { role, tenantName } = useAuth();
  const location = useLocation();

  const navItems = [
    { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { label: 'My Work (Lab)', path: '/worklist', icon: FlaskConical, highlight: role === 'LAB_TECH' },
    { label: 'New Invoice', path: '/invoices/new', icon: PlusCircle, highlight: role !== 'LAB_TECH' },
    { label: 'Invoices', path: '/invoices', icon: Receipt },
    { label: 'Patients', path: '/patients', icon: Users },
    { label: 'Assign Tests', path: '/assignments', icon: GitBranch },
    { label: 'Dues Settlement', path: '/dues', icon: CreditCard },
    { label: 'Ready Reports', path: '/reports', icon: FileCheck },
    { label: 'Refund Requests', path: '/refunds', icon: RotateCcw },
    { label: 'Business Day', path: '/business-day', icon: CalendarDays },
    { label: 'My Profile', path: '/profile', icon: UserCircle },
  ];

  return (
    <aside
      className={`hidden md:flex relative flex-col shrink-0 bg-[#292917] text-[#FAF9F6] border-r border-[#373720] transition-all duration-300 ease-in-out z-30 select-none ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-[#373720] overflow-hidden">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[#CF8852] flex items-center justify-center font-bold text-white text-lg shadow-md shrink-0">
            M
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <span className="font-bold text-sm tracking-wide text-white block truncate">
                MedScope DCMS
              </span>
              <span className="text-[11px] text-[#C2C6A4] block truncate">
                {role === 'ADMIN' || role === 'OWNER' ? 'Administration Portal' : role === 'LAB_TECH' ? 'Laboratory Workbench' : 'Receptionist Portal'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;

          return (
            <NavLink
              key={item.path}
              to={item.path}
              title={collapsed ? item.label : undefined}
              className={`flex items-center gap-3.5 px-3 py-2.5 rounded-xl text-xs font-medium transition-all group relative ${
                isActive
                  ? 'bg-[#CF8852] text-white shadow-sm'
                  : 'text-[#C2C6A4] hover:bg-[#373720] hover:text-white'
              } ${item.highlight && !isActive ? 'border border-[#CF8852]/30 text-[#FAF9F6]' : ''}`}
            >
              <Icon
                className={`w-5 h-5 shrink-0 transition-transform group-hover:scale-110 ${
                  isActive ? 'text-white' : item.highlight ? 'text-[#CF8852]' : 'text-[#9FA574]'
                }`}
              />
              {!collapsed && <span className="truncate">{item.label}</span>}
              {isActive && !collapsed && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse / Expand Toggle Button */}
      <div className="p-3 border-t border-[#373720]">
        <button
          onClick={onToggleCollapse}
          className="w-full flex items-center justify-center gap-2 py-2 text-[#9FA574] hover:text-white hover:bg-[#373720] rounded-xl text-xs font-medium transition-colors"
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse Sidebar</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
};


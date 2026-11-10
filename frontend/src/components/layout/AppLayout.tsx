import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('medscope_sidebar_collapsed') === 'true';
  });

  const handleToggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('medscope_sidebar_collapsed', String(next));
      return next;
    });
  };

  // Item 09: Ctrl+F shortcut focuses the inline global search input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
        // Do not hijack browser search in print mode or when target is already inside an active input with text selection
        const target = e.target as HTMLElement | null;
        const isPrintModal = document.querySelector('.print-only') !== null;
        if (isPrintModal) return;

        e.preventDefault();
        const searchInput = document.getElementById('medscope-global-search') as HTMLInputElement | null;
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#E8E7E3] font-sans">
      {/* Sidebar */}
      <Sidebar collapsed={collapsed} onToggleCollapse={handleToggleCollapse} />

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 bg-[#E8E7E3]">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

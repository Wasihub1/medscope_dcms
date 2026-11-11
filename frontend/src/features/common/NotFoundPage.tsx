import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getRoleHomeRoute } from '../../utils/navigation';

export const NotFoundPage: React.FC = () => {
  const { isAuthenticated, user } = useAuth();
  const homePath = isAuthenticated && user ? getRoleHomeRoute(user.acting_role) : '/';

  return (
    <div className="min-h-screen bg-[#E8E7E3] text-[#26270F] flex items-center justify-center p-6 font-['Manrope','Noto_Sans_Bengali',system-ui,sans-serif]">
      <div className="w-full max-w-md bg-white rounded-3xl p-8 sm:p-10 border border-[#DCDAD4] shadow-xs text-center box-border">
        {/* Brand Logo Mark */}
        <div className="flex justify-center mb-6">
          <svg width="48" height="48" viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
            <rect width="32" height="32" rx="8" fill="#525333" />
            <path d="M16 8v16M8 16h16" stroke="#CF8852" strokeWidth="3" strokeLinecap="round" fill="none" />
          </svg>
        </div>

        <h1 className="text-3xl font-semibold leading-9 text-[#26270F]">Page not found</h1>
        <p className="mt-3 text-sm leading-5 text-[#3D3E1F] [text-wrap:pretty]">
          The page you are looking for does not exist or has been moved.
        </p>

        <div className="mt-8">
          <Link
            to={homePath}
            data-testid="not-found-home-btn"
            className="inline-flex items-center justify-center bg-[#CF8852] hover:bg-[#B7703B] active:scale-[0.98] text-[#26270F] text-base font-bold leading-6 px-8 py-3.5 rounded-xl transition duration-200 shadow-xs focus-visible:ring-2 focus-visible:ring-[#525333] focus-visible:outline-none"
          >
            {isAuthenticated ? 'Back to workbench' : 'Back to home'}
          </Link>
        </div>
      </div>
    </div>
  );
};


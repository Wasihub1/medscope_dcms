import React from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getRoleHomeRoute } from '../../utils/navigation';

export interface WorkflowStep {
  id: string;
  label: string;
  icon: (props: { className?: string }) => React.JSX.Element;
}

export const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    id: 'register',
    label: 'Register',
    icon: ({ className }) => (
      <svg
        width="28"
        height="28"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#525333"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={className}
      >
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 20c0-3.6 3-6 7-6s7 2.4 7 6" />
      </svg>
    ),
  },
  {
    id: 'sample',
    label: 'Sample',
    icon: ({ className }) => (
      <svg
        width="28"
        height="28"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#525333"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={className}
      >
        <path d="M9 3h6M10 3v13a2 2 0 0 0 4 0V3" />
        <path d="M10 11h4" />
      </svg>
    ),
  },
  {
    id: 'result',
    label: 'Result',
    icon: ({ className }) => (
      <svg
        width="28"
        height="28"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#525333"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={className}
      >
        <rect x="6" y="4" width="12" height="17" rx="2" />
        <path d="M9 4h6v3H9z" />
        <path d="M9.5 14l2 2 3.5-4" />
      </svg>
    ),
  },
  {
    id: 'report',
    label: 'Report',
    icon: ({ className }) => (
      <svg
        width="28"
        height="28"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#525333"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={className}
      >
        <path d="M7 3h7l4 4v14H7z" />
        <path d="M14 3v4h4M10 12h5M10 16h5" />
      </svg>
    ),
  },
];

export const LandingPage: React.FC = () => {
  const { isAuthenticated, isLoading, user } = useAuth();

  // Redirect signed-in users directly to their designated role workbench
  if (!isLoading && isAuthenticated && user) {
    return <Navigate to={getRoleHomeRoute(user.acting_role)} replace />;
  }

  // 8 items per track (4 unique steps repeated twice), matching Landing.dc.html reference
  const marqueeSet = [...WORKFLOW_STEPS, ...WORKFLOW_STEPS];

  return (
    <div className="min-h-screen bg-[#E8E7E3] text-[#26270F] flex flex-col font-['Manrope','Noto_Sans_Bengali',system-ui,sans-serif]">
      {/* Component-level animations to ensure active motion across all OS / browser settings */}
      <style>{`
        @keyframes ecg-landing {
          0% { stroke-dashoffset: 720; }
          55% { stroke-dashoffset: 0; }
          100% { stroke-dashoffset: -720; }
        }
        @keyframes fillup {
          0% { transform: scaleY(0.15); }
          60% { transform: scaleY(1); }
          100% { transform: scaleY(1); }
        }
        @keyframes travel {
          0% { transform: translateX(0); }
          100% { transform: translateX(240px); }
        }
        @keyframes chipin {
          0% { opacity: 0; transform: translateY(16px); }
          12% { opacity: 1; transform: translateY(0); }
          80% { opacity: 1; transform: translateY(0); }
          100% { opacity: 0; transform: translateY(-8px); }
        }
        @keyframes marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .anim-ecg-landing {
          stroke-dasharray: 720;
          stroke-dashoffset: 720;
          animation: ecg-landing 3.6s cubic-bezier(0.22, 1, 0.36, 1) infinite !important;
          will-change: stroke-dashoffset;
        }
        .anim-tube-fill {
          transform-box: fill-box !important;
          transform-origin: bottom !important;
          animation: fillup 4s cubic-bezier(0.22, 1, 0.36, 1) infinite alternate !important;
          will-change: transform;
        }
        .anim-dot {
          animation: travel 4.8s cubic-bezier(0.22, 1, 0.36, 1) infinite alternate !important;
          will-change: transform;
        }
        .anim-chip {
          animation-name: chipin !important;
          animation-duration: 8s !important;
          animation-timing-function: cubic-bezier(0.22, 1, 0.36, 1) !important;
          animation-iteration-count: infinite !important;
          will-change: transform, opacity;
        }
        .marquee-track {
          display: flex !important;
          flex-direction: row !important;
          flex-wrap: nowrap !important;
          width: max-content !important;
          animation: marquee 28s linear infinite !important;
          will-change: transform;
        }
        .marquee-track:hover {
          animation-play-state: paused !important;
        }
      `}</style>

      {/* Accessible Skip Link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-[#525333] focus:text-white focus:rounded-xl focus:shadow-md focus:outline-none"
      >
        Skip to content
      </a>

      {/* Header */}
      <header className="w-full">
        <div className="max-w-[1200px] mx-auto px-6 py-6 md:px-8 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
              <rect width="32" height="32" rx="8" fill="#525333" />
              <path d="M16 8v16M8 16h16" stroke="#CF8852" strokeWidth="3" strokeLinecap="round" fill="none" />
            </svg>
            <span className="text-xl font-bold leading-7 text-[#26270F]">MedScope DCMS</span>
          </div>
          <Link
            to="/login"
            data-testid="landing-header-signin"
            className="inline-flex items-center justify-center bg-[#525333] hover:bg-[#444529] active:scale-[0.98] text-white text-sm font-bold leading-5 px-6 py-3 rounded-xl transition duration-300 focus-visible:ring-2 focus-visible:ring-[#CF8852] focus-visible:outline-none"
          >
            Sign in
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <main id="main-content" className="flex-1">
        <section className="max-w-[1200px] mx-auto px-6 pt-12 pb-20 md:px-8 md:pt-16 md:pb-24 flex flex-col lg:flex-row items-center gap-12 lg:gap-16">
          {/* Left Column: Heading, Subtitle, CTA */}
          <div className="flex-1 min-w-0 w-full">
            <h1 className="max-w-[680px] text-4xl sm:text-5xl lg:text-6xl font-bold text-[#26270F] leading-[1.05] [text-wrap:balance]">
              Your diagnostic center, in one place
            </h1>
            <p className="mt-6 max-w-[480px] text-lg sm:text-xl text-[#3D3E1F] leading-7 [text-wrap:pretty]">
              Billing, samples, results and reports.
            </p>
            <div className="mt-10">
              <Link
                to="/login"
                data-testid="landing-hero-cta"
                className="inline-flex items-center justify-center bg-[#CF8852] hover:bg-[#B7703B] active:scale-[0.98] text-[#26270F] text-lg font-bold leading-7 px-8 py-4 rounded-xl transition duration-300 shadow-xs focus-visible:ring-2 focus-visible:ring-[#525333] focus-visible:outline-none"
              >
                Sign in
              </Link>
            </div>
          </div>

          {/* Right Column: Animated Medical Scene */}
          <div className="flex-1 min-w-0 w-full">
            <div className="bg-[#525333] rounded-3xl p-8 sm:p-10 relative overflow-hidden min-h-[400px] box-border shadow-xs">
              {/* ECG Line Drawing Itself */}
              <svg viewBox="0 0 400 130" width="100%" className="block overflow-visible" role="img" aria-label="Animated heartbeat line">
                <path
                  d="M0 70 H70 L86 70 L100 24 L118 112 L134 46 L148 70 H230 L246 70 L260 38 L276 96 L290 70 H400"
                  fill="none"
                  stroke="#CF8852"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="anim-ecg-landing"
                />
              </svg>

              {/* Sample Tube and Travelling Indicator */}
              <div className="mt-8 flex items-end gap-8">
                <svg viewBox="0 0 60 120" width="60" height="120" role="img" aria-label="Sample tube filling" className="shrink-0">
                  <rect x="14" y="6" width="32" height="104" rx="16" fill="none" stroke="#E8E7E3" strokeWidth="3" />
                  <rect x="19" y="40" width="22" height="66" rx="11" fill="#CF8852" className="anim-tube-fill" />
                  <rect x="10" y="2" width="40" height="8" rx="4" fill="#E8E7E3" />
                </svg>

                <div className="flex-1 min-w-0 pb-12">
                  <div className="relative h-6">
                    <div className="absolute left-0 right-0 top-[11px] h-0.5 bg-[#E8E7E3] opacity-40" />
                    <div className="absolute left-0 top-1 w-4 h-4 rounded-full bg-[#CF8852] anim-dot" />
                  </div>
                </div>
              </div>

              {/* Sequential Status Chips */}
              <div className="relative h-12 mt-6">
                <div
                  className="anim-chip absolute left-0 top-0 bg-[#E8E7E3] text-[#26270F] text-sm font-semibold leading-5 px-4 py-3 rounded-xl shadow-2xs"
                  style={{ animationDelay: '0s' }}
                >
                  Sample taken
                </div>
                <div
                  className="anim-chip absolute left-0 top-0 bg-[#E8E7E3] text-[#26270F] text-sm font-semibold leading-5 px-4 py-3 rounded-xl shadow-2xs"
                  style={{ animationDelay: '2s' }}
                >
                  Result entered
                </div>
                <div
                  className="anim-chip absolute left-0 top-0 bg-[#CF8852] text-[#26270F] text-sm font-bold leading-5 px-4 py-3 rounded-xl shadow-2xs"
                  style={{ animationDelay: '4s' }}
                >
                  Report ready
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Endless Scrolling Strip (Marquee) */}
        <section className="bg-white border-y border-[#DCDAD4]" aria-label="Workflow steps">
          <div
            className="marquee-container overflow-hidden py-4 md:py-5 cursor-default focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
            tabIndex={0}
            aria-label="Workflow stages strip. Hover or focus to pause."
          >
            <div className="marquee-track flex flex-row flex-nowrap shrink-0">
              {/* Primary Sequence */}
              <div className="flex flex-row flex-nowrap shrink-0">
                {marqueeSet.map((item, idx) => (
                  <div
                    key={`m1-${item.id}-${idx}`}
                    className="shrink-0 flex items-center gap-3 px-6 md:px-8"
                  >
                    <item.icon className="shrink-0" />
                    <span className="text-base md:text-lg font-semibold leading-6 text-[#26270F] whitespace-nowrap">
                      {item.label}
                    </span>
                  </div>
                ))}
              </div>
              {/* Duplicate Sequence (Aria-hidden for seamless continuous loop) */}
              <div className="flex flex-row flex-nowrap shrink-0" aria-hidden="true">
                {marqueeSet.map((item, idx) => (
                  <div
                    key={`m2-${item.id}-${idx}`}
                    className="shrink-0 flex items-center gap-3 px-6 md:px-8"
                  >
                    <item.icon className="shrink-0" />
                    <span className="text-base md:text-lg font-semibold leading-6 text-[#26270F] whitespace-nowrap">
                      {item.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="w-full">
        <div className="max-w-[1200px] mx-auto px-6 py-8 md:px-8 text-sm leading-5 text-[#3D3E1F]">
          MedScope DCMS
        </div>
      </footer>
    </div>
  );
};


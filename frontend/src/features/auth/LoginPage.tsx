import React, { useState } from 'react';
import { useNavigate, Navigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getRoleHomeRoute } from '../../utils/navigation';

export const LoginPage: React.FC = () => {
  const { user, login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // If already authenticated, redirect directly to role home route
  if (!isLoading && isAuthenticated && user) {
    return <Navigate to={getRoleHomeRoute(user.acting_role)} replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanUser = username.trim();
    if (!cleanUser || !password) {
      setErrorMessage('Please enter both your username and password.');
      return;
    }

    setIsSubmitting(true);
    try {
      const authUser = await login(cleanUser, password);
      navigate(getRoleHomeRoute(authUser.acting_role), { replace: true });
    } catch (err: unknown) {
      const rawDetail = err instanceof Error ? err.message : String(err);
      const lower = rawDetail.toLowerCase();

      if (lower.includes('locked')) {
        setErrorMessage('This account is locked. Ask your administrator to reset it.');
      } else if (lower.includes('invalid') || lower.includes('password') || lower.includes('username') || lower.includes('401')) {
        setErrorMessage('Invalid username or password.');
      } else if (lower.includes('expired')) {
        setErrorMessage('Your session has expired. Please sign in again.');
      } else if (lower.includes('network') || lower.includes('fetch') || lower.includes('connect')) {
        setErrorMessage('Unable to connect to the server. Check your network connection.');
      } else {
        setErrorMessage('Unable to sign in. Please verify your credentials.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#E8E7E3] text-[#26270F] flex flex-col md:flex-row font-['Manrope','Noto_Sans_Bengali',system-ui,sans-serif]">
      {/* Component-level animations to ensure active motion across all OS / browser settings */}
      <style>{`
        @keyframes ecg-login {
          0% { stroke-dashoffset: 900; }
          55% { stroke-dashoffset: 0; }
          100% { stroke-dashoffset: -900; }
        }
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 0.9; }
          100% { transform: scale(2.4); opacity: 0; }
        }
        .anim-ecg-login {
          stroke-dasharray: 900;
          stroke-dashoffset: 900;
          animation: ecg-login 4.2s cubic-bezier(0.22, 1, 0.36, 1) infinite !important;
          will-change: stroke-dashoffset;
        }
        .anim-ring {
          transform-box: fill-box !important;
          transform-origin: center !important;
          animation: pulse-ring 2.4s cubic-bezier(0.22, 1, 0.36, 1) infinite !important;
          will-change: transform, opacity;
        }
      `}</style>

      {/* Accessible Skip Link */}
      <a
        href="#login-form"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-[#525333] focus:text-white focus:rounded-xl focus:shadow-md focus:outline-none"
      >
        Skip to sign in form
      </a>

      {/* LEFT: Animated Brand Panel */}
      <div className="flex-1 md:w-1/2 bg-[#525333] text-white p-8 md:p-12 lg:p-16 flex flex-col justify-between gap-12 box-border">
        {/* Brand Header */}
        <div className="flex items-center gap-3">
          <svg width="40" height="40" viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
            <rect width="32" height="32" rx="8" fill="#CF8852" />
            <path d="M16 8v16M8 16h16" stroke="#26270F" strokeWidth="3" strokeLinecap="round" fill="none" />
          </svg>
          <span className="text-2xl font-bold leading-8 tracking-tight text-white">MedScope DCMS</span>
        </div>

        {/* Animated ECG Illustration */}
        <div className="my-auto py-8">
          <svg
            viewBox="0 0 520 160"
            width="100%"
            className="block w-full overflow-visible"
            role="img"
            aria-label="Animated heartbeat line"
          >
            <line x1="0" y1="90" x2="520" y2="90" stroke="#E8E7E3" strokeOpacity="0.25" strokeWidth="2" />
            <path
              d="M0 90 H90 L110 90 L128 30 L150 140 L170 58 L188 90 H300 L320 90 L338 44 L358 120 L376 90 H520"
              fill="none"
              stroke="#CF8852"
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="anim-ecg-login"
            />
            <circle cx="128" cy="30" r="6" fill="#CF8852" />
            <circle cx="128" cy="30" r="6" fill="#CF8852" className="anim-ring" />
          </svg>
        </div>

        {/* Note */}
        <p className="m-0 max-w-[420px] text-sm leading-5 text-[#E8E7E3] [text-wrap:pretty]">
          Illustration only. No patient information is shown on this page.
        </p>
      </div>

      {/* RIGHT: Sign-In Card Container */}
      <div className="flex-1 md:w-1/2 bg-[#E8E7E3] p-6 sm:p-10 md:p-12 lg:p-16 flex items-center justify-center box-border">
        <div className="w-full max-w-[420px] bg-white rounded-3xl p-8 sm:p-10 box-border border border-[#DCDAD4] shadow-xs">
          <h1 className="m-0 text-3xl font-semibold leading-9 text-[#26270F]">Sign in</h1>
          <p className="mt-2 text-sm leading-5 text-[#3D3E1F] [text-wrap:pretty]">
            Use your own account. What you see depends on your role.
          </p>

          {/* Inline Error Area */}
          <div aria-live="polite" className="mt-4">
            {errorMessage && (
              <div
                role="alert"
                data-testid="login-error-banner"
                className="p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs font-medium leading-relaxed"
              >
                {errorMessage}
              </div>
            )}
          </div>

          {/* Sign In Form */}
          <form id="login-form" onSubmit={handleSubmit} className="mt-6 flex flex-col gap-6">
            {/* Username Field */}
            <div className="flex flex-col gap-2">
              <label htmlFor="user" className="text-sm font-semibold leading-5 text-[#26270F]">
                Username
              </label>
              <input
                id="user"
                name="username"
                type="text"
                data-testid="login-username"
                placeholder="Your username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full h-12 px-4 border border-[#525333] rounded-xl text-base text-[#26270F] bg-white placeholder-[#6B6C48] box-border transition duration-200 focus-visible:ring-2 focus-visible:ring-[#CF8852] focus-visible:outline-none"
              />
            </div>

            {/* Password Field */}
            <div className="flex flex-col gap-2">
              <label htmlFor="pass" className="text-sm font-semibold leading-5 text-[#26270F]">
                Password
              </label>
              <div className="flex gap-2">
                <input
                  id="pass"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  data-testid="login-password"
                  placeholder="Your password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="flex-1 min-w-0 h-12 px-4 border border-[#525333] rounded-xl text-base text-[#26270F] bg-white placeholder-[#6B6C48] box-border transition duration-200 focus-visible:ring-2 focus-visible:ring-[#CF8852] focus-visible:outline-none"
                />
                <button
                  type="button"
                  data-testid="toggle-password-visibility"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="shrink-0 h-12 px-4 border border-[#525333] rounded-xl bg-white hover:bg-[#FAF9F6] active:scale-[0.98] text-[#525333] text-sm font-semibold transition duration-200 focus-visible:ring-2 focus-visible:ring-[#CF8852] focus-visible:outline-none cursor-pointer"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              data-testid="login-submit-btn"
              className="w-full h-12 rounded-xl bg-[#CF8852] hover:bg-[#B7703B] active:scale-[0.98] disabled:opacity-60 text-[#26270F] text-base font-bold transition duration-200 shadow-xs focus-visible:ring-2 focus-visible:ring-[#525333] focus-visible:outline-none cursor-pointer disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          {/* Helper Copy & Link */}
          <p className="mt-6 text-sm leading-5 text-[#3D3E1F] [text-wrap:pretty]">
            Forgot your password? Ask your center administrator to reset it.
          </p>
          <p className="mt-4 text-sm leading-5">
            <Link
              to="/"
              data-testid="back-to-overview-link"
              className="font-semibold text-[#525333] hover:text-[#26270F] transition duration-200 underline focus-visible:ring-2 focus-visible:ring-[#CF8852] focus-visible:outline-none rounded-sm"
            >
              Back to the overview
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

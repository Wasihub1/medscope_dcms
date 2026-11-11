import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { AppLayout } from './components/layout/AppLayout';

import { LandingPage } from './features/landing/LandingPage';
import { LoginPage } from './features/auth/LoginPage';
import { NotFoundPage } from './features/common/NotFoundPage';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { NewInvoicePage } from './features/invoices/NewInvoicePage';
import { InvoicesPage } from './features/invoices/InvoicesPage';
import { PatientsPage } from './features/patients/PatientsPage';
import { AssignmentsPage } from './features/assignments/AssignmentsPage';
import { DuesPage } from './features/dues/DuesPage';
import { RefundsPage } from './features/refunds/RefundsPage';
import { ReportsPage } from './features/reports/ReportsPage';
import { BusinessDayPage } from './features/business_day/BusinessDayPage';
import { ProfilePage } from './features/profile/ProfilePage';
import { TechnicianWorklistPage } from './features/worklist/TechnicianWorklistPage';

const ProtectedLayout: React.FC = () => {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#E8E7E3] flex items-center justify-center font-['Manrope','Noto_Sans_Bengali',system-ui,sans-serif]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-[#CF8852] animate-spin" />
          <span className="text-xs text-[#525333] font-semibold">Verifying workstation session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  return <AppLayout />;
};

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            {/* Public Branded Routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />

            {/* Authenticated Protected Routes */}
            <Route element={<ProtectedLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/invoices/new" element={<NewInvoicePage />} />
              <Route path="/invoices" element={<InvoicesPage />} />
              <Route path="/patients" element={<PatientsPage />} />
              <Route path="/assignments" element={<AssignmentsPage />} />
              <Route path="/worklist" element={<TechnicianWorklistPage />} />
              <Route path="/dues" element={<DuesPage />} />
              <Route path="/refunds" element={<RefundsPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/business-day" element={<BusinessDayPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>

            {/* Branded 404 Route for Unknown Paths */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

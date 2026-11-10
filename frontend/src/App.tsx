import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { AppLayout } from './components/layout/AppLayout';

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

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<DashboardPage />} />
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
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

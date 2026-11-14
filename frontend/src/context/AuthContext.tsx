import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Role, BusinessDayState, AuthUser } from '../types';
import { api, setUnauthorizedCallback } from '../api/client';

interface AuthContextType {
  user: AuthUser | null;
  role: Role;
  staffName: string;
  staffId: string;
  department: string;
  tenantName: string;
  /** Prompt 13B: the open day, or null when closed. Same value for every role. */
  businessDay: BusinessDayState | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isLoadingBusinessDay: boolean;
  login: (username: string, password: string, role?: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  /** Prompt 10D: effective permission check (role defaults + per-user overrides, from /auth/me) */
  hasPermission: (key: string) => boolean;
  refreshBusinessDay: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [businessDay, setBusinessDay] = useState<BusinessDayState | null>(null);
  const [isLoadingBusinessDay, setIsLoadingBusinessDay] = useState<boolean>(false);

  const tenantName = 'Seba Diagnostic Center (সেবা ডায়াগনস্টিক সেন্টার)';

  const refreshBusinessDay = useCallback(async () => {
    setIsLoadingBusinessDay(true);
    try {
      // Money-free state endpoint: every authenticated role can read it (Lab Tech has no business_day.view).
      const day = await api.getBusinessDayState();
      setBusinessDay(day.is_open ? day : null);
    } catch {
      setBusinessDay(null);
    } finally {
      setIsLoadingBusinessDay(false);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.getMe();
      setUser(me);
      await refreshBusinessDay();
    } catch {
      setUser(null);
      setBusinessDay(null);
    }
  }, [refreshBusinessDay]);

  useEffect(() => {
    // Initial check for active session
    refreshUser().finally(() => {
      setIsLoading(false);
    });

    // Handle 401 expiration across API requests
    setUnauthorizedCallback(() => {
      setUser(null);
      setBusinessDay(null);
    });

    return () => {
      setUnauthorizedCallback(null);
    };
  }, [refreshUser]);

  const login = async (username: string, password: string, role?: string): Promise<AuthUser> => {
    const authUser = await api.login(username, password, role);
    setUser(authUser);
    await refreshBusinessDay();
    return authUser;
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Ignore logout errors
    } finally {
      setUser(null);
      setBusinessDay(null);
    }
  };

  // Prompt 10D: one login = one fixed role; no role switching.
  const hasPermission = useCallback(
    (key: string) => Boolean(user?.permissions?.includes(key)),
    [user]
  );

  const role: Role = (user?.role || user?.acting_role || 'RECEPTIONIST') as Role;
  const staffName = user?.display_name || '';
  const staffId = String(user?.id || '');
  const department = user?.department || 'General';

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        staffName,
        staffId,
        department,
        tenantName,
        businessDay,
        isAuthenticated: Boolean(user),
        isLoading,
        isLoadingBusinessDay,
        login,
        logout,
        hasPermission,
        refreshBusinessDay,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

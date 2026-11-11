import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Role, BusinessDay, AuthUser } from '../types';
import { api, setUnauthorizedCallback } from '../api/client';

interface AuthContextType {
  user: AuthUser | null;
  role: Role;
  staffName: string;
  staffId: string;
  department: string;
  tenantName: string;
  businessDay: BusinessDay | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isLoadingBusinessDay: boolean;
  login: (username: string, password: string, role?: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  switchRole: (role: string) => Promise<void>;
  refreshBusinessDay: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [businessDay, setBusinessDay] = useState<BusinessDay | null>(null);
  const [isLoadingBusinessDay, setIsLoadingBusinessDay] = useState<boolean>(false);

  const tenantName = 'Seba Diagnostic Center (সেবা ডায়াগনস্টিক সেন্টার)';

  const refreshBusinessDay = useCallback(async () => {
    setIsLoadingBusinessDay(true);
    try {
      const day = await api.getCurrentBusinessDay();
      setBusinessDay(day);
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

  const switchRole = async (newRole: string) => {
    const updated = await api.switchActingRole(newRole);
    setUser(updated);
  };

  const role: Role = user?.acting_role || 'RECEPTIONIST';
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
        switchRole,
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

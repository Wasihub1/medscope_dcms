import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Role, BusinessDay } from '../types';
import { setApiActor, api } from '../api/client';

export type DevActorMode = 'RECEPTIONIST' | 'ADMIN' | 'LAB_TECH_KAMAL' | 'LAB_TECH_NASRIN';

interface AuthContextType {
  role: Role;
  actorMode: DevActorMode;
  staffName: string;
  staffId: string;
  department: string;
  tenantName: string;
  businessDay: BusinessDay | null;
  toggleRole: () => void;
  setMode: (mode: DevActorMode) => void;
  refreshBusinessDay: () => Promise<void>;
  isLoadingBusinessDay: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [actorMode, setActorMode] = useState<DevActorMode>('RECEPTIONIST');
  const [businessDay, setBusinessDay] = useState<BusinessDay | null>(null);
  const [isLoadingBusinessDay, setIsLoadingBusinessDay] = useState(false);

  let role: Role = 'RECEPTIONIST';
  let staffName = 'Fatima Akter (Receptionist)';
  let staffId = '1';
  let department = 'Front Desk';

  if (actorMode === 'ADMIN') {
    role = 'ADMIN';
    staffName = 'Tariqul Islam (Admin)';
    staffId = '2';
    department = 'Administration';
  } else if (actorMode === 'LAB_TECH_KAMAL') {
    role = 'LAB_TECH';
    staffName = 'Kamal Hossain (Lab Tech)';
    staffId = '3';
    department = 'Hematology';
  } else if (actorMode === 'LAB_TECH_NASRIN') {
    role = 'LAB_TECH';
    staffName = 'Nasrin Sultana (Lab Tech)';
    staffId = '4';
    department = 'Biochemical Tests';
  }

  const tenantName = 'Seba Diagnostic Center (সেবা ডায়াগনস্টিক সেন্টার)';

  const refreshBusinessDay = useCallback(async () => {
    setIsLoadingBusinessDay(true);
    try {
      const day = await api.getCurrentBusinessDay();
      setBusinessDay(day);
    } catch (err) {
      console.error('Failed to fetch business day:', err);
      setBusinessDay(null);
    } finally {
      setIsLoadingBusinessDay(false);
    }
  }, []);

  useEffect(() => {
    refreshBusinessDay();
  }, [refreshBusinessDay]);

  const setMode = (mode: DevActorMode) => {
    setActorMode(mode);
    if (mode === 'ADMIN') {
      setApiActor('ADMIN', 2);
    } else if (mode === 'LAB_TECH_KAMAL') {
      setApiActor('LAB_TECH', 3);
    } else if (mode === 'LAB_TECH_NASRIN') {
      setApiActor('LAB_TECH', 4);
    } else {
      setApiActor('RECEPTIONIST', 1);
    }
  };

  const toggleRole = () => {
    const cycle: Record<DevActorMode, DevActorMode> = {
      RECEPTIONIST: 'ADMIN',
      ADMIN: 'LAB_TECH_KAMAL',
      LAB_TECH_KAMAL: 'LAB_TECH_NASRIN',
      LAB_TECH_NASRIN: 'RECEPTIONIST',
    };
    setMode(cycle[actorMode]);
  };

  return (
    <AuthContext.Provider
      value={{
        role,
        actorMode,
        staffName,
        staffId,
        department,
        tenantName,
        businessDay,
        toggleRole,
        setMode,
        refreshBusinessDay,
        isLoadingBusinessDay,
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

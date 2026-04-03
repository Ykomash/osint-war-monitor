import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

export type Period = '1d' | '3d' | '7d';

interface DashboardContextType {
  period: Period;
  setPeriod: (p: Period) => void;
  dateFrom: string;
}

const DashboardContext = createContext<DashboardContextType | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [period, setPeriod] = useState<Period>('1d');

  const daysBack = period === '1d' ? 1 : period === '3d' ? 3 : 7;
  const dateFrom = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0];

  return (
    <DashboardContext.Provider value={{ period, setPeriod, dateFrom }}>
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard(): DashboardContextType {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error('useDashboard must be used within DashboardProvider');
  return ctx;
}

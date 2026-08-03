'use client';

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';

interface PipelineContextType {
  statsRefreshKey: number;
  triggerStatsRefresh: () => void;
}

const PipelineContext = createContext<PipelineContextType | undefined>(undefined);

export function PipelineProvider({ children }: { children: ReactNode }) {
  const [statsRefreshKey, setStatsRefreshKey] = useState<number>(0);

  const triggerStatsRefresh = useCallback(() => {
    setStatsRefreshKey((prev) => prev + 1);
  }, []);

  return (
    <PipelineContext.Provider value={{ statsRefreshKey, triggerStatsRefresh }}>
      {children}
    </PipelineContext.Provider>
  );
}

export function usePipeline() {
  const context = useContext(PipelineContext);
  if (!context) {
    throw new Error('usePipeline must be used within a PipelineProvider');
  }
  return context;
}

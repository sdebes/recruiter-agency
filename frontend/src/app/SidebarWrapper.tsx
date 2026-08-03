'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import { usePipeline } from '@/context/PipelineContext';

export default function SidebarWrapper() {
  const { statsRefreshKey } = usePipeline();
  return <Sidebar statsRefreshKey={statsRefreshKey} />;
}

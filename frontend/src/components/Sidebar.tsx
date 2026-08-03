'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { apiFetch } from '@/utils/api';
import { PipelineStats } from '@/types';

interface SidebarProps {
  statsRefreshKey?: number;
}

export default function Sidebar({ statsRefreshKey = 0 }: SidebarProps) {
  const pathname = usePathname();
  const [stats, setStats] = useState<PipelineStats | null>(null);

  useEffect(() => {
    async function loadStats() {
      try {
        const data = await apiFetch<PipelineStats>('/api/stats');
        setStats(data);
      } catch (err) {
        console.error('Failed to load sidebar stats', err);
      }
    }
    loadStats();
  }, [statsRefreshKey]);

  const navItems = [
    { name: 'Dashboard', href: '/' },
    { name: 'Tracker', href: '/tracker' },
    { name: 'Settings', href: '/settings' },
    { name: 'Resume Builder', href: '/resume-builder' },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-100 flex flex-col h-screen fixed left-0 top-0 border-r border-slate-800">
      {/* Brand Header */}
      <div className="p-6 border-b border-slate-800">
        <h1 className="text-xl font-bold bg-gradient-to-r from-amber-400 to-rose-400 bg-clip-text text-transparent">
          Recruiter Agency
        </h1>
        <p className="text-xs text-slate-400 mt-1">AI-powered job search</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-slate-800 text-amber-400 border-l-4 border-amber-400 shadow-md'
                  : 'text-slate-300 hover:bg-slate-800/50 hover:text-white'
              }`}
            >
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Pipeline Stats Section */}
      <div className="p-6 border-t border-slate-800 bg-slate-950/40">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Pipeline
        </h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs">
            <span className="text-slate-400">Applications</span>
            <span className="font-semibold text-slate-200">
              {stats !== null ? stats.total : '—'}
            </span>
          </div>
          <div className="flex justify-between items-center text-xs">
            <span className="text-slate-400">Avg Score</span>
            <span className="font-semibold text-amber-400">
              {stats !== null && stats.avg_score > 0
                ? `${stats.avg_score.toFixed(1)}/5`
                : 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 text-center border-t border-slate-800 text-[10px] text-slate-500 font-mono">
        LangGraph + Gemini
      </div>
    </aside>
  );
}

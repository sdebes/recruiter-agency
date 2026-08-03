'use client';

import React, { useState, useEffect } from 'react';
import { apiFetch } from '@/utils/api';
import { useNotifications } from '@/context/NotificationContext';
import { usePipeline } from '@/context/PipelineContext';
import { Application } from '@/types';

export default function Tracker() {
  const { showToast } = useNotifications();
  const { triggerStatsRefresh } = usePipeline();

  // State
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('All');
  const [filterMinScore, setFilterMinScore] = useState(0.0);

  // Stats State
  const [stats, setStats] = useState({
    total: 0,
    avgScore: 'N/A',
    applied: 0,
    interview: 0,
  });

  // Load applications
  const loadApplications = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('min_score', filterMinScore.toString());
      if (filterStatus && filterStatus !== 'All') {
        params.append('status', filterStatus);
      }

      const path = `/api/applications?${params.toString()}`;
      const data = await apiFetch<Application[]>(path);
      setApps(data);
    } catch (err: any) {
      showToast(err.message || 'Failed to load applications', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Load tracker stats
  const loadTrackerStats = async () => {
    try {
      const data = await apiFetch<{
        total: number;
        by_status: Record<string, number>;
        avg_score: number;
      }>('/api/stats');

      setStats({
        total: data.total,
        avgScore: data.avg_score > 0 ? `${data.avg_score.toFixed(1)}/5` : 'N/A',
        applied: data.by_status?.['Applied'] || 0,
        interview: data.by_status?.['Interview'] || 0,
      });
    } catch {
      // Ignore background stats failures silently
    }
  };

  useEffect(() => {
    loadApplications();
    loadTrackerStats();
  }, [filterStatus, filterMinScore]);

  // Update Status Action
  const handleUpdateStatus = async (appId: string, status: string) => {
    if (!status) return;

    try {
      await apiFetch(`/api/applications/${appId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });

      showToast(`Status updated to ${status}`, 'success');
      loadApplications();
      loadTrackerStats();
      triggerStatsRefresh();
    } catch (err: any) {
      showToast(err.message || 'Failed to update status', 'error');
    }
  };

  // Badge Color Classes
  const getBadgeClass = (status: string) => {
    const classes: Record<string, string> = {
      Evaluated: 'bg-blue-50 text-blue-700 border-blue-200',
      Applied: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      Responded: 'bg-amber-50 text-amber-700 border-amber-200',
      Interview: 'bg-purple-50 text-purple-700 border-purple-200',
      Offer: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      Rejected: 'bg-rose-50 text-rose-700 border-rose-200',
      Discarded: 'bg-slate-100 text-slate-655 border-slate-200',
      SKIP: 'bg-slate-100 text-slate-655 border-slate-200',
    };
    return classes[status] || 'bg-slate-50 text-slate-600 border-slate-200';
  };

  return (
    <div className="space-y-8 animate-slide-in">
      {/* Page Header */}
      <div>
        <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Application Tracker</h2>
        <p className="text-sm text-slate-500 mt-1">All your evaluated applications in one place.</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total</span>
          <span className="text-3xl font-extrabold text-slate-800 mt-2">{stats.total}</span>
        </div>
        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Average Score</span>
          <span className="text-3xl font-extrabold text-amber-500 mt-2">{stats.avgScore}</span>
        </div>
        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Applied</span>
          <span className="text-3xl font-extrabold text-slate-800 mt-2">{stats.applied}</span>
        </div>
        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Interview</span>
          <span className="text-3xl font-extrabold text-indigo-600 mt-2">{stats.interview}</span>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-white p-5 rounded-xl shadow-sm border border-slate-200">
        <div>
          <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
            Filter by Status
          </label>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-500"
          >
            <option value="All">All</option>
            <option value="Evaluated">Evaluated</option>
            <option value="Applied">Applied</option>
            <option value="Responded">Responded</option>
            <option value="Interview">Interview</option>
            <option value="Offer">Offer</option>
            <option value="Rejected">Rejected</option>
            <option value="Discarded">Discarded</option>
            <option value="SKIP">SKIP</option>
          </select>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Minimum Score
            </label>
            <span className="text-xs font-extrabold text-amber-500">{filterMinScore.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="0"
            max="5"
            step="0.5"
            value={filterMinScore}
            onChange={(e) => setFilterMinScore(parseFloat(e.target.value))}
            className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer"
          />
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="text-center py-12 bg-white rounded-xl border border-slate-200">
          <div className="spinner border-t-amber-500 h-8 w-8 border-4 mb-2"></div>
          <p className="text-sm text-slate-500">Loading applications...</p>
        </div>
      )}

      {/* Empty State */}
      {!loading && apps.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border border-slate-200 p-8">
          <p className="text-sm text-slate-500 font-medium">
            No applications match the current filters. Add a job listing from the Dashboard to get started!
          </p>
        </div>
      )}

      {/* Table */}
      {!loading && apps.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm text-slate-700">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase tracking-wider">
                  <th className="px-6 py-4">#</th>
                  <th className="px-6 py-4">Company</th>
                  <th className="px-6 py-4">Role</th>
                  <th className="px-6 py-4 text-center">Score</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Date</th>
                  <th className="px-6 py-4">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {apps.map((a, i) => (
                  <tr key={a.id} className="hover:bg-slate-50/75 transition-colors">
                    <td className="px-6 py-4 font-semibold text-slate-500 text-xs">{i + 1}</td>
                    <td className="px-6 py-4 font-extrabold text-slate-900">{a.company}</td>
                    <td className="px-6 py-4 font-medium text-slate-700">{a.role}</td>
                    <td className="px-6 py-4 text-center font-extrabold text-slate-900">
                      {a.score != null ? a.score.toFixed(1) : <span className="text-slate-300 font-normal">—</span>}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 rounded text-xs font-bold border ${getBadgeClass(a.status)}`}>
                        {a.status || 'Evaluated'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-400 font-mono">
                      {a.updated_at.slice(0, 10)}
                    </td>
                    <td className="px-6 py-4">
                      <select
                        onChange={(e) => handleUpdateStatus(a.id, e.target.value)}
                        value=""
                        className="px-2 py-1 border border-slate-300 rounded text-xs bg-white focus:outline-none focus:ring-1 focus:ring-amber-500 focus:border-amber-500 cursor-pointer font-medium text-slate-700"
                      >
                        <option value="" disabled>Update</option>
                        <option value="Applied">Applied</option>
                        <option value="Responded">Responded</option>
                        <option value="Interview">Interview</option>
                        <option value="Offer">Offer</option>
                        <option value="Rejected">Rejected</option>
                        <option value="Discarded">Discarded</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 text-xs font-semibold text-slate-500">
            {apps.length} applications matching filters
          </div>
        </div>
      )}
    </div>
  );
}

'use client';

import React, { useState, useEffect } from 'react';
import { apiFetch } from '@/utils/api';
import { useNotifications } from '@/context/NotificationContext';
import { usePipeline } from '@/context/PipelineContext';
import { Listing, Evaluation, TailoredCV } from '@/types';

export default function Dashboard() {
  const { showToast } = useNotifications();
  const { triggerStatsRefresh } = usePipeline();

  // State
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSource, setFilterSource] = useState('');
  const [filterSearch, setFilterSearch] = useState('');
  const [filterLocation, setFilterLocation] = useState('');

  // Add Listing State
  const [jobUrl, setJobUrl] = useState('');
  const [scraping, setScraping] = useState(false);
  const [urlFeedback, setUrlFeedback] = useState<{ type: 'success' | 'error' | 'info'; msg: string } | null>(null);

  // Manual Form State
  const [manualFormOpen, setManualFormOpen] = useState(false);
  const [manualData, setManualData] = useState({
    title: '',
    company: '',
    url: '',
    location: '',
    description: '',
  });
  const [savingManual, setSavingManual] = useState(false);

  // Modal State
  const [activeModalId, setActiveModalId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'desc' | 'eval' | 'cv' | 'critique'>('desc');
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [loadingEval, setLoadingEval] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [tailoredCVs, setTailoredCVs] = useState<TailoredCV[]>([]);
  const [loadingCVs, setLoadingCVs] = useState(false);
  const [tailoringCV, setTailoringCV] = useState(false);

  // Critique State
  const [critiqueText, setCritiqueText] = useState<string | null>(null);
  const [loadingCritique, setLoadingCritique] = useState(false);
  const [critiquingCV, setCritiquingCV] = useState(false);

  // Find Listings State
  const [searchLocation, setSearchLocation] = useState('');
  const [findingListings, setFindingListings] = useState(false);
  const [findFeedback, setFindFeedback] = useState<{ type: 'success' | 'error' | 'info'; msg: string } | null>(null);

  // Stats State
  const [pipeStats, setPipeStats] = useState({
    totalListings: 0,
    applications: 0,
    avgScore: 'N/A',
    toEvaluate: 0,
  });

  // Action scoring tracking
  const [scoringListings, setScoringListings] = useState<Record<string, boolean>>({});
  const [cachedEvaluations, setCachedEvaluations] = useState<Record<string, Evaluation | null>>({});

  // Known countries for location parsing
  const KNOWN_COUNTRIES = new Set([
    'switzerland', 'denmark', 'germany', 'austria', 'france', 'italy', 'spain',
    'netherlands', 'belgium', 'sweden', 'norway', 'finland', 'uk', 'united kingdom',
    'ireland', 'portugal', 'poland', 'czech republic', 'czechia', 'luxembourg',
    'hungary', 'romania', 'greece', 'croatia', 'usa', 'united states',
  ]);

  // Parse location string into city and country
  function parseLocation(loc: string): { city: string; country: string } | null {
    if (!loc) return null;
    const parts = loc.split(',').map(s => s.trim()).filter(Boolean);
    if (parts.length === 1) return null;
    for (let i = parts.length - 1; i >= 0; i--) {
      const part = parts[i].toLowerCase();
      if (KNOWN_COUNTRIES.has(part)) {
        return { city: parts[0], country: parts[i] };
      }
    }
    return null;
  }

  // Build grouped location options from listings
  const locationGroups: { country: string; cities: { city: string; full: string }[] }[] = [];
  const otherLocations: string[] = [];
  {
    const map = new Map<string, { city: string; full: string }[]>();
    listings.forEach(l => {
      if (!l.location) return;
      const parsed = parseLocation(l.location);
      if (parsed) {
        if (!map.has(parsed.country)) {
          map.set(parsed.country, []);
        }
        const arr = map.get(parsed.country)!;
        if (!arr.some(x => x.full === l.location)) {
          arr.push({ city: parsed.city, full: l.location });
        }
      } else {
        if (!otherLocations.includes(l.location)) {
          otherLocations.push(l.location);
        }
      }
    });
    map.forEach((cities, country) => {
      cities.sort((a, b) => a.city.localeCompare(b.city));
      locationGroups.push({ country, cities });
    });
    locationGroups.sort((a, b) => a.country.localeCompare(b.country));
    otherLocations.sort();
  }

  // Apply location filter client-side
  const filteredListings = filterLocation
    ? listings.filter(l => l.location === filterLocation)
    : listings;

  // Active listing helper
  const activeListing = filteredListings.find((l) => l.id === activeModalId);

  // Load Listings
  const loadListings = async () => {
    try {
      const params = new URLSearchParams();
      if (filterSource) params.append('source', filterSource);
      if (filterSearch) params.append('search', filterSearch);

      const qs = params.toString();
      const path = `/api/listings${qs ? '?' + qs : ''}`;
      const data = await apiFetch<Listing[]>(path);
      setListings(data);
      setPipeStats((prev) => ({
        ...prev,
        totalListings: data.length,
        toEvaluate: data.filter((l) => l.source !== 'manual').length,
      }));
    } catch (err: any) {
      showToast(err.message || 'Failed to load listings', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Load pipeline aggregate stats
  const loadPipelineStats = async () => {
    try {
      const stats = await apiFetch<{ total: number; avg_score: number }>('/api/stats');
      setPipeStats((prev) => ({
        ...prev,
        applications: stats.total,
        avgScore: stats.avg_score > 0 ? `${stats.avg_score.toFixed(1)}/5` : 'N/A',
      }));
    } catch {
      // Ignore background stats failures silently
    }
  };

  useEffect(() => {
    loadListings();
    loadPipelineStats();
  }, [filterSource, filterSearch]);

  // Load evaluations for each listing (on demand or background)
  useEffect(() => {
    listings.forEach((l) => {
      if (cachedEvaluations[l.id] === undefined) {
        apiFetch<Evaluation[]>(`/api/listings/${l.id}/evaluations`)
          .then((evals) => {
            setCachedEvaluations((prev) => ({
              ...prev,
              [l.id]: evals && evals.length > 0 ? evals[0] : null,
            }));
          })
          .catch(() => {});
      }
    });
  }, [listings]);

  // Load Modal Tab details
  useEffect(() => {
    if (!activeModalId) return;

    if (activeTab === 'eval') {
      setEvalError(null);
      setLoadingEval(true);
      apiFetch<Evaluation[]>(`/api/listings/${activeModalId}/evaluations`)
        .then((data) => setEvaluations(data))
        .catch(() => showToast('Failed to load evaluations', 'error'))
        .finally(() => setLoadingEval(false));
    } else if (activeTab === 'cv') {
      setLoadingCVs(true);
      apiFetch<TailoredCV[]>(`/api/listings/${activeModalId}/tailored-cvs`)
        .then((data) => setTailoredCVs(data))
        .catch(() => showToast('Failed to load tailored CVs', 'error'))
        .finally(() => setLoadingCVs(false));
    } else if (activeTab === 'critique') {
      // Critique is generated on demand; reset stale state when switching listings
      setCritiqueText(null);
    }
  }, [activeModalId, activeTab]);

  // Add Listing from URL
  const addListingFromUrl = async () => {
    if (!jobUrl.trim()) {
      showToast('Please enter a URL', 'warning');
      return;
    }

    setScraping(true);
    setUrlFeedback({ type: 'info', msg: 'Scraping listing details...' });

    try {
      const data = await apiFetch<Listing>('/api/listings', {
        method: 'POST',
        body: JSON.stringify({ url: jobUrl }),
      });

      setUrlFeedback({ type: 'success', msg: 'Added successfully!' });
      setJobUrl('');
      loadListings();
      loadPipelineStats();
      triggerStatsRefresh();
      setTimeout(() => setUrlFeedback(null), 3000);
    } catch (err: any) {
      setUrlFeedback({ type: 'error', msg: `Failed: ${err.message}` });
    } finally {
      setScraping(false);
    }
  };

  // Add Listing Manually
  const addListingManual = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualData.title || !manualData.company) {
      showToast('Title and Company are required fields', 'warning');
      return;
    }

    setSavingManual(true);
    try {
      await apiFetch<Listing>('/api/listings', {
        method: 'POST',
        body: JSON.stringify(manualData),
      });

      showToast('Listing added!', 'success');
      setManualData({ title: '', company: '', url: '', location: '', description: '' });
      setManualFormOpen(false);
      loadListings();
      loadPipelineStats();
      triggerStatsRefresh();
    } catch (err: any) {
      showToast(err.message || 'Failed to save listing', 'error');
    } finally {
      setSavingManual(false);
    }
  };

  // Find Listings
  const handleFindListings = async () => {
    if (!searchLocation.trim()) {
      showToast('Please enter a location', 'warning');
      return;
    }

    setFindingListings(true);
    setFindFeedback({ type: 'info', msg: 'Searching job boards for listings...' });

    try {
      const data = await apiFetch<{ ok: boolean; listings: Listing[]; new_count: number; duplicates: number; total_found: number; sources: string[] }>('/api/listings/find', {
        method: 'POST',
        body: JSON.stringify({ location: searchLocation }),
      });

      setFindFeedback({
        type: 'success',
        msg: `Found ${data.new_count} new listing${data.new_count !== 1 ? 's' : ''} in ${searchLocation} (${data.duplicates} duplicates skipped)`,
      });
      loadListings();
      loadPipelineStats();
      triggerStatsRefresh();
      setTimeout(() => setFindFeedback(null), 5000);
    } catch (err: any) {
      setFindFeedback({ type: 'error', msg: `Failed: ${err.message}` });
    } finally {
      setFindingListings(false);
    }
  };

  // Delete Listing
  const handleDeleteListing = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this listing?')) return;

    try {
      await apiFetch(`/api/listings/${id}`, { method: 'DELETE' });
      showToast('Listing deleted', 'success');
      loadListings();
      loadPipelineStats();
      triggerStatsRefresh();
    } catch (err: any) {
      showToast(err.message || 'Failed to delete listing', 'error');
    }
  };

  // Evaluate / Score Listing
  const evaluateListing = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();

    setEvalError(null);
    setScoringListings((prev) => ({ ...prev, [id]: true }));

    try {
      const res = await apiFetch<{ ok: boolean; result: Evaluation }>(`/api/listings/${id}/evaluate`, {
        method: 'POST',
      });

      showToast('Evaluation complete!', 'success');
      setCachedEvaluations((prev) => ({ ...prev, [id]: res.result }));
      setEvaluations((prev) => [...prev, res.result]);
      if (activeTab !== 'eval') setActiveTab('eval');
      loadListings();
    } catch (err: any) {
      const msg = err.message || 'Evaluation failed';
      showToast(msg, 'error');
      if (activeModalId === id) setEvalError(msg);
    } finally {
      setScoringListings((prev) => ({ ...prev, [id]: false }));
    }
  };

  // Tailor CV
  const tailorCv = async (listingId: string) => {
    setTailoringCV(true);
    showToast('Tailoring CV...', 'info');
    try {
      await apiFetch(`/api/listings/${listingId}/tailor-cv`, { method: 'POST' });
      showToast('CV tailored successfully!', 'success');

      // Reload tab data
      if (activeTab === 'cv') {
        const cvs = await apiFetch<TailoredCV[]>(`/api/listings/${listingId}/tailored-cvs`);
        setTailoredCVs(cvs);
      } else {
        setActiveTab('cv');
      }
    } catch (err: any) {
      showToast(err.message || 'Tailoring failed', 'error');
    } finally {
      setTailoringCV(false);
    }
  };

  // Critique CV
  const critiqueCv = async (listingId: string) => {
    setCritiquingCV(true);
    setLoadingCritique(true);
    showToast('Running CV critique...', 'info');
    try {
      const res = await apiFetch<{ critique: string }>(`/api/listings/${listingId}/critique`, {
        method: 'POST',
      });
      setCritiqueText(res.critique);
      if (activeTab !== 'critique') setActiveTab('critique');
    } catch (err: any) {
      showToast(err.message || 'Critique failed', 'error');
    } finally {
      setCritiquingCV(false);
      setLoadingCritique(false);
    }
  };

  // Helper score range color
  const getScoreColorClass = (score: number) => {
    if (score >= 4.0) return 'text-emerald-600 bg-emerald-50 border-emerald-200';
    if (score >= 3.5) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-rose-600 bg-rose-50 border-rose-200';
  };

  const getScoreFillColor = (score: number) => {
    if (score >= 4.0) return 'bg-emerald-500';
    if (score >= 3.5) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  return (
    <div className="space-y-8 animate-slide-in">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Dashboard</h2>
          <p className="text-sm text-slate-500 mt-1">Find, evaluate, and track job opportunities.</p>
        </div>
      </div>

      {/* Add Job Listing Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <span className="font-semibold text-slate-800">
            Add Job Listing
          </span>
        </div>
        <div className="p-6">
          <p className="text-xs text-slate-500 mb-4">
            Paste a job URL to automatically scrape details, or add details manually below.
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={jobUrl}
              onChange={(e) => setJobUrl(e.target.value)}
              placeholder="https://www.jobs.ch/en/vacancies/detail/..."
              className="flex-1 min-w-0 px-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 bg-slate-50/50"
            />
            <button
              onClick={addListingFromUrl}
              disabled={scraping}
              className="px-5 py-2 bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-600 hover:to-rose-600 text-white text-sm font-semibold rounded-lg shadow-sm disabled:opacity-50 transition-all duration-200 flex items-center justify-center gap-2"
            >
              {scraping ? (
                <>
                  <span className="spinner"></span>
                  <span>Scraping...</span>
                </>
              ) : (
                <span>Add Job Listing</span>
              )}
            </button>
          </div>

          {urlFeedback && (
            <div
              className={`mt-3 p-3 rounded-lg border text-xs font-medium flex items-center gap-2 ${
                urlFeedback.type === 'success'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : urlFeedback.type === 'error'
                  ? 'bg-rose-50 text-rose-800 border-rose-200'
                  : 'bg-blue-50 text-blue-800 border-blue-200'
              }`}
            >
              {urlFeedback.msg}
            </div>
          )}

          {/* Add Manually Details Expandable */}
          <div className="mt-4 border-t border-slate-100 pt-4">
            <button
              onClick={() => setManualFormOpen(!manualFormOpen)}
              className="text-xs font-semibold text-amber-600 hover:text-amber-700 flex items-center gap-1 focus:outline-none"
            >
              <span>{manualFormOpen ? 'Hide Form' : 'Add Manually'}</span>
            </button>

            {manualFormOpen && (
              <form onSubmit={addListingManual} className="mt-4 space-y-4 animate-slide-in">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Job Title *</label>
                    <input
                      type="text"
                      required
                      value={manualData.title}
                      onChange={(e) => setManualData({ ...manualData, title: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Company *</label>
                    <input
                      type="text"
                      required
                      value={manualData.company}
                      onChange={(e) => setManualData({ ...manualData, company: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">URL</label>
                    <input
                      type="url"
                      value={manualData.url}
                      onChange={(e) => setManualData({ ...manualData, url: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Location</label>
                    <input
                      type="text"
                      value={manualData.location}
                      onChange={(e) => setManualData({ ...manualData, location: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Job Description</label>
                  <textarea
                    rows={4}
                    value={manualData.description}
                    onChange={(e) => setManualData({ ...manualData, description: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  />
                </div>

                <button
                  type="submit"
                  disabled={savingManual}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold rounded-lg shadow-sm disabled:opacity-50 transition-colors"
                >
                  {savingManual ? 'Saving...' : 'Save Listing'}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>

      {/* Find Listings Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <span className="font-semibold text-slate-800">
            Find Listings
          </span>
        </div>
        <div className="p-6">
          <p className="text-xs text-slate-500 mb-4">
            Search job boards for listings in a specific area. Found listings are added to Your Listings below.
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={searchLocation}
              onChange={(e) => setSearchLocation(e.target.value)}
              placeholder="e.g. Zurich, Switzerland or Copenhagen, Denmark"
              className="flex-1 min-w-0 px-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 bg-slate-50/50"
            />
            <button
              onClick={handleFindListings}
              disabled={findingListings}
              className="px-5 py-2 bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-600 hover:to-rose-600 text-white text-sm font-semibold rounded-lg shadow-sm disabled:opacity-50 transition-all duration-200 flex items-center justify-center gap-2"
            >
              {findingListings ? (
                <>
                  <span className="spinner"></span>
                  <span>Searching...</span>
                </>
              ) : (
                <span>Find Listings</span>
              )}
            </button>
          </div>

          {findFeedback && (
            <div
              className={`mt-3 p-3 rounded-lg border text-xs font-medium flex items-center gap-2 ${
                findFeedback.type === 'success'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : findFeedback.type === 'error'
                  ? 'bg-rose-50 text-rose-800 border-rose-200'
                  : 'bg-blue-50 text-blue-800 border-blue-200'
              }`}
            >
              {findFeedback.msg}
            </div>
          )}
        </div>
      </div>

      {/* Listings Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-bold text-slate-800">Your Listings</h3>
          <span className="text-xs font-semibold text-slate-500 px-2.5 py-1 bg-slate-200 rounded-full">
            {filteredListings.length} listing{filteredListings.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 bg-white p-4 rounded-xl shadow-sm border border-slate-200">
          <div className="w-full sm:w-48">
            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Filter by source
            </label>
            <select
              value={filterSource}
              onChange={(e) => setFilterSource(e.target.value)}
              className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              <option value="">All</option>
              <option value="manual">Manual</option>
              <option value="scan">Scan</option>
            </select>
          </div>
          <div className="w-full sm:w-56">
            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Filter by location
            </label>
            <select
              value={filterLocation}
              onChange={(e) => setFilterLocation(e.target.value)}
              className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              <option value="">All</option>
              {locationGroups.map(g => (
                <optgroup key={g.country} label={g.country}>
                  {g.cities.map(c => (
                    <option key={c.full} value={c.full}>{c.city}</option>
                  ))}
                </optgroup>
              ))}
              {otherLocations.length > 0 && (
                <optgroup label="Other">
                  {otherLocations.map(loc => (
                    <option key={loc} value={loc}>{loc}</option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Search
            </label>
            <input
              type="text"
              value={filterSearch}
              onChange={(e) => setFilterSearch(e.target.value)}
              placeholder="Company or title..."
              className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12 bg-white rounded-xl border border-slate-200">
            <div className="spinner border-t-amber-500 h-8 w-8 border-4 mb-2"></div>
            <p className="text-sm text-slate-500">Loading listings...</p>
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredListings.length === 0 && (
          <div className="text-center py-12 bg-white rounded-xl border border-slate-200 p-8 space-y-6">
            <div className="max-w-sm mx-auto">
              <h4 className="text-base font-bold text-slate-800">No listings yet</h4>
              <p className="text-xs text-slate-500 mt-1">
                Add a job URL above or search job boards to get started.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl mx-auto pt-4 border-t border-slate-100">
              <div className="p-4 bg-slate-50 rounded-lg text-center space-y-1">
                <h5 className="text-xs font-bold text-slate-700">Find Jobs</h5>
                <p className="text-[10px] text-slate-500">Scan job boards for new listings</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg text-center space-y-1">
                <h5 className="text-xs font-bold text-slate-700">Evaluate</h5>
                <p className="text-[10px] text-slate-500">Score listings against your profile</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-lg text-center space-y-1">
                <h5 className="text-xs font-bold text-slate-700">Track</h5>
                <p className="text-[10px] text-slate-500">Monitor your application pipeline</p>
              </div>
            </div>
          </div>
        )}

        {/* Listings Table */}
        {!loading && filteredListings.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-sm text-slate-700">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase tracking-wider">
                    <th className="px-6 py-4">Position</th>
                    <th className="px-6 py-4">Location</th>
                    <th className="px-6 py-4">Source</th>
                    <th className="px-6 py-4 text-center">Score</th>
                    <th className="px-6 py-4"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredListings.map((l) => {
                    const hasDetails = l.seniority && l.seniority !== 'Not specified';
                    const hasSalary = l.salary_range && l.salary_range !== 'Not specified';
                    const isScoring = !!scoringListings[l.id];
                    const cachedEval = cachedEvaluations[l.id];

                    return (
                      <tr
                        key={l.id}
                        onClick={() => {
                          setActiveModalId(l.id);
                          setActiveTab('desc');
                        }}
                        className="hover:bg-slate-50/75 cursor-pointer transition-colors"
                      >
                        <td className="px-6 py-4 max-w-sm">
                          <div>
                            <span className="text-base font-bold text-slate-900 hover:text-amber-600 transition-colors block">
                              {l.title}
                            </span>
                            <div className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                              <span>{l.company}</span>
                              {hasDetails && (
                                <>
                                  <span className="text-slate-300">|</span>
                                  <span>{l.seniority}</span>
                                </>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-xs font-medium text-slate-700">
                            {l.location || '-'}
                          </div>
                          {hasSalary && (
                            <div className="text-[10px] text-emerald-600 font-semibold mt-0.5">
                              {l.salary_range}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600 border border-slate-200">
                            {l.source || '?'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          {cachedEval ? (
                            <span
                              className={`px-3 py-1 rounded-full text-xs font-bold border ${getScoreColorClass(
                                cachedEval.global_score
                              )}`}
                            >
                              {cachedEval.global_score.toFixed(1)}
                            </span>
                          ) : (
                            <span className="text-xs text-slate-400 font-medium">—</span>
                          )}
                        </td>
                        <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={(e) => evaluateListing(l.id, e)}
                              disabled={isScoring}
                              className="px-3 py-1 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-xs font-semibold rounded transition-colors flex items-center gap-1 shadow-sm"
                            >
                              {isScoring ? (
                                <>
                                  <span className="spinner h-3 w-3"></span>
                                  <span>Scoring...</span>
                                </>
                              ) : (
                                <span>{cachedEval ? 'Re-score' : 'Score'}</span>
                              )}
                            </button>
                            <button
                              onClick={(e) => handleDeleteListing(l.id, e)}
                              className="p-1 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 transition-colors"
                              title="Delete Listing"
                            >
                              &times;
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Pipeline Overview Metrics Grid */}
      <div className="space-y-4">
        <h3 className="text-xl font-bold text-slate-800">Pipeline Overview</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Listings
            </span>
            <span className="text-3xl font-extrabold text-slate-800 mt-2">
              {pipeStats.totalListings}
            </span>
          </div>
          <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Applications
            </span>
            <span className="text-3xl font-extrabold text-slate-800 mt-2">
              {pipeStats.applications}
            </span>
          </div>
          <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Avg Score
            </span>
            <span className="text-3xl font-extrabold text-amber-500 mt-2">
              {pipeStats.avgScore}
            </span>
          </div>
          <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              To Evaluate
            </span>
            <span className="text-3xl font-extrabold text-slate-800 mt-2">
              {pipeStats.toEvaluate}
            </span>
          </div>
        </div>
      </div>

      {/* Detail Modal */}
      {activeModalId && activeListing && (
        <div
          className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex justify-center items-start pt-10 px-4 pb-4 overflow-y-auto"
          onClick={() => setActiveModalId(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden animate-slide-in"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="px-6 py-5 border-b border-slate-200 bg-slate-50 flex items-start justify-between">
              <div>
                <h3 className="text-xl font-extrabold text-slate-950">{activeListing.title}</h3>
                <div className="text-sm font-semibold text-amber-600 mt-1">
                  {activeListing.company}
                </div>
              </div>
              <button
                onClick={() => setActiveModalId(null)}
                className="text-slate-400 hover:text-slate-600 text-2xl font-light focus:outline-none"
              >
                &times;
              </button>
            </div>

            {/* Quick Specs */}
            <div className="px-6 py-3 bg-slate-100/50 border-b border-slate-200 flex flex-wrap gap-4 text-xs font-medium text-slate-600">
              {activeListing.location && <span>{activeListing.location}</span>}
              {activeListing.seniority && activeListing.seniority !== 'Not specified' && (
                <span>{activeListing.seniority}</span>
              )}
              {activeListing.employment_type && activeListing.employment_type !== 'Not specified' && (
                <span>{activeListing.employment_type}</span>
              )}
              {activeListing.salary_range && activeListing.salary_range !== 'Not specified' && (
                <span>{activeListing.salary_range}</span>
              )}
            </div>

            {/* Modal Body */}
            <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
              {/* Tab Workspace */}
              <div className="flex-1 p-6 flex flex-col overflow-y-auto min-w-0">
                {/* Tab buttons */}
                <div className="flex border-b border-slate-200 mb-6 gap-6">
                  <button
                    onClick={() => setActiveTab('desc')}
                    className={`pb-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-colors ${
                      activeTab === 'desc'
                        ? 'border-amber-500 text-amber-600'
                        : 'border-transparent text-slate-400 hover:text-slate-600'
                    }`}
                  >
                    Job Description
                  </button>
                  <button
                    onClick={() => setActiveTab('eval')}
                    className={`pb-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-colors ${
                      activeTab === 'eval'
                        ? 'border-amber-500 text-amber-600'
                        : 'border-transparent text-slate-400 hover:text-slate-600'
                    }`}
                  >
                    AI Evaluation
                  </button>
                  <button
                    onClick={() => setActiveTab('cv')}
                    className={`pb-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-colors ${
                      activeTab === 'cv'
                        ? 'border-amber-500 text-amber-600'
                        : 'border-transparent text-slate-400 hover:text-slate-600'
                    }`}
                  >
                    Tailored CV
                  </button>
                  <button
                    onClick={() => setActiveTab('critique')}
                    className={`pb-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-colors ${
                      activeTab === 'critique'
                        ? 'border-rose-500 text-rose-600'
                        : 'border-transparent text-slate-400 hover:text-slate-600'
                    }`}
                  >
                    Critique CV
                  </button>
                </div>

                {/* Tab Content: Job Description */}
                {activeTab === 'desc' && (
                  <div className="space-y-4">
                    <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                      {activeListing.description || 'No description provided.'}
                    </p>
                    {activeListing.url && (
                      <div className="pt-4 border-t border-slate-100">
                        <a
                          href={activeListing.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs font-bold text-amber-600 hover:underline inline-flex items-center gap-1"
                        >
                          View Original Listing &rarr;
                        </a>
                      </div>
                    )}
                  </div>
                )}

                {/* Tab Content: AI Evaluation */}
                {activeTab === 'eval' && (
                  <div className="space-y-6">
                    {loadingEval ? (
                      <div className="text-center py-8">
                        <span className="spinner border-t-amber-500 h-6 w-6 mb-2"></span>
                        <p className="text-xs text-slate-500">Loading evaluation...</p>
                      </div>
                    ) : evaluations.length > 0 ? (
                      (() => {
                        const ev = evaluations[0];
                        const label =
                          ev.global_score >= 4.5
                            ? 'Strong Match'
                            : ev.global_score >= 4.0
                            ? 'Good Match'
                            : ev.global_score >= 3.5
                            ? 'Decent Match'
                            : 'Weak Match';
                        const scoreColor = ev.global_score >= 4.0 ? 'text-emerald-500' : ev.global_score >= 3.5 ? 'text-amber-500' : 'text-rose-500';

                        const metricBlocks = [
                          { name: 'CV Match', val: ev.cv_match_score },
                          { name: 'North Star', val: ev.north_star_score },
                          { name: 'Compensation', val: ev.comp_score },
                          { name: 'Culture / Fit', val: ev.culture_score },
                        ];

                        return (
                          <div className="space-y-6 animate-slide-in">
                            {/* Score Hero */}
                            <div className="flex items-center gap-4 bg-slate-50 p-4 rounded-xl border border-slate-150">
                              <span className={`text-4xl font-extrabold ${scoreColor}`}>
                                {ev.global_score.toFixed(1)}
                              </span>
                              <div>
                                <div className="text-xs font-semibold text-slate-400">/ 5.0</div>
                                <div className={`text-sm font-bold ${scoreColor}`}>{label}</div>
                              </div>
                              {ev.legitimacy && (
                                <span
                                  className={`ml-auto text-[10px] font-bold px-2.5 py-1 rounded-full border ${
                                    ev.legitimacy === 'High Confidence'
                                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                      : ev.legitimacy === 'Proceed with Caution'
                                      ? 'bg-amber-50 text-amber-700 border-amber-200'
                                      : 'bg-rose-50 text-rose-700 border-rose-200'
                                  }`}
                                >
                                  {ev.legitimacy}
                                </span>
                              )}
                            </div>

                            {/* Scoring Weights Metrics */}
                            <div className="space-y-3">
                              {metricBlocks.map((b) => {
                                const pct = (b.val / 5) * 100;
                                const c = getScoreFillColor(b.val);
                                return (
                                  <div key={b.name} className="space-y-1">
                                    <div className="flex justify-between items-center text-xs font-bold text-slate-700">
                                      <span>{b.name}</span>
                                      <span>{b.val.toFixed(1)} / 5</span>
                                    </div>
                                    <div className="w-full bg-slate-100 rounded-full h-2">
                                      <div
                                        className={`h-2 rounded-full transition-all duration-300 ${c}`}
                                        style={{ width: `${pct}%` }}
                                      ></div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>

                            {/* Red flags */}
                            {ev.red_flags && ev.red_flags.length > 0 && (
                              <div className="space-y-2">
                                <h4 className="text-xs font-bold text-rose-700 flex items-center gap-1">
                                  Red Flags
                                </h4>
                                <div className="space-y-1.5">
                                  {ev.red_flags.map((flag, idx) => (
                                    <div
                                      key={idx}
                                      className="text-xs bg-rose-50 text-rose-800 p-2.5 rounded-lg border border-rose-200"
                                    >
                                      {flag}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Notes */}
                            {ev.detailed_notes && (
                              <details className="group cursor-pointer border border-slate-200 rounded-lg p-3 bg-slate-50/50">
                                <summary className="text-xs font-bold text-slate-700 flex justify-between items-center">
                                  <span>Detailed Evaluation Notes</span>
                                  <span className="text-slate-400 group-open:rotate-180 transition-transform">
                                    ▼
                                  </span>
                                </summary>
                                <p className="text-xs text-slate-650 mt-3 whitespace-pre-wrap leading-relaxed border-t border-slate-200/60 pt-3">
                                  {ev.detailed_notes}
                                </p>
                              </details>
                            )}
                          </div>
                        );
                      })()
                    ) : (
                      <div className="text-center py-6 bg-slate-50 rounded-xl border border-dashed border-slate-350 p-6 space-y-3">
                        {evalError ? (
                          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 font-medium text-left">
                            <div className="font-bold mb-1">Evaluation failed</div>
                            <div className="text-rose-600">{evalError}</div>
                            <p className="mt-2 text-rose-500 font-normal text-[10px]">Check the server logs for details and try again.</p>
                          </div>
                        ) : (
                          <p className="text-xs text-slate-500">
                            This listing has not been evaluated yet.
                          </p>
                        )}
                        <button
                          onClick={() => evaluateListing(activeListing.id)}
                          disabled={!!scoringListings[activeListing.id]}
                          className="px-4 py-2 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-bold rounded-lg transition-colors shadow-sm"
                        >
                          {scoringListings[activeListing.id] ? (
                            <span className="flex items-center gap-2">
                              <span className="spinner h-3 w-3"></span>
                              <span>Evaluating...</span>
                            </span>
                          ) : (
                            <span>{evalError ? 'Retry Evaluation' : 'Run AI Evaluation'}</span>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Tab Content: Tailored CV */}
                {activeTab === 'cv' && (
                  <div className="space-y-6 animate-slide-in">
                    {loadingCVs ? (
                      <div className="text-center py-8">
                        <span className="spinner border-t-amber-500 h-6 w-6 mb-2"></span>
                        <p className="text-xs text-slate-500">Loading CVs...</p>
                      </div>
                    ) : tailoredCVs.length > 0 ? (
                      (() => {
                        const cv = tailoredCVs[0];
                        return (
                          <div className="space-y-4">
                            <div className="p-4 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-xl text-xs font-bold flex items-center gap-2">
                              <span>Tailored CV generated on {cv.created_at.slice(0, 10)}</span>
                            </div>

                            {cv.resume_builder_url && (
                              <div>
                                <a
                                  href={`${cv.resume_builder_url}?resume=${encodeURIComponent(
                                    cv.cv_path
                                  )}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs font-bold text-amber-600 hover:underline flex items-center gap-1"
                                >
                                  Open in Resume Builder &rarr;
                                </a>
                              </div>
                            )}

                            {cv.commentary && (
                              <details className="group cursor-pointer border border-slate-200 rounded-lg p-3 bg-slate-50/50">
                                <summary className="text-xs font-bold text-slate-700 flex justify-between items-center">
                                  <span>Tailoring Commentary</span>
                                  <span className="text-slate-400 group-open:rotate-180 transition-transform">
                                    ▼
                                  </span>
                                </summary>
                                <p className="text-xs text-slate-650 mt-3 whitespace-pre-wrap leading-relaxed border-t border-slate-200/60 pt-3">
                                  {cv.commentary}
                                </p>
                              </details>
                            )}

                            <div className="pt-2">
                              <span className="text-[10px] text-slate-450 font-mono">
                                Path: {cv.cv_path}
                              </span>
                            </div>

                            {tailoredCVs.length > 1 && (
                              <details className="group cursor-pointer border border-slate-200 rounded-lg p-3">
                                <summary className="text-xs font-bold text-slate-650 flex justify-between items-center">
                                  <span>Previous versions ({tailoredCVs.length - 1} more)</span>
                                  <span className="text-slate-400 group-open:rotate-180 transition-transform">
                                    ▼
                                  </span>
                                </summary>
                                <ul className="text-xs text-slate-500 mt-3 pl-4 list-disc space-y-1">
                                  {tailoredCVs.slice(1).map((c) => (
                                    <li key={c.id}>
                                      {c.cv_path.split('/').pop()} ({c.created_at.slice(0, 10)})
                                    </li>
                                  ))}
                                </ul>
                              </details>
                            )}
                          </div>
                        );
                      })()
                    ) : (
                      <div className="text-center py-6 bg-slate-50 rounded-xl border border-dashed border-slate-350 p-6">
                        <p className="text-xs text-slate-500">
                          No tailored CV yet. Generate one from the sidebar.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Tab Content: Critique CV */}
                {activeTab === 'critique' && (
                  <div className="space-y-4 animate-slide-in">
                    {loadingCritique ? (
                      <div className="text-center py-8">
                        <span className="spinner border-t-rose-500 h-6 w-6 mb-2"></span>
                        <p className="text-xs text-slate-500">Running critique...</p>
                      </div>
                    ) : critiqueText ? (
                      <div className="space-y-4">
                        <div className="p-4 bg-rose-50 text-rose-800 border border-rose-200 rounded-xl text-xs font-bold flex items-center gap-2">
                          CV Critique — {activeListing?.title} at {activeListing?.company}
                        </div>
                        <div
                          className="prose prose-sm prose-slate max-w-none text-sm leading-relaxed"
                          dangerouslySetInnerHTML={{
                            __html: critiqueText
                              .replace(/^### (.+)$/gm, '<h3 class="text-sm font-extrabold text-slate-800 mt-4 mb-1">$1</h3>')
                              .replace(/^## (.+)$/gm, '<h2 class="text-base font-extrabold text-slate-900 mt-5 mb-2 border-b border-slate-200 pb-1">$1</h2>')
                              .replace(/^\*\*(.+?)\*\*/gm, '<strong>$1</strong>')
                              .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-slate-700 text-xs">$1</li>')
                              .replace(/\n{2,}/g, '<br/><br/>')
                          }}
                        />
                        <div className="pt-2">
                          <button
                            onClick={() => critiqueCv(activeListing!.id)}
                            disabled={critiquingCV}
                            className="px-3 py-1.5 text-xs font-bold bg-white border border-rose-300 text-rose-700 rounded-lg hover:bg-rose-50 transition-colors disabled:opacity-50"
                          >
                            Re-run Critique
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-10 bg-slate-50 rounded-xl border border-dashed border-slate-300 p-6 space-y-4">
                        <div>
                          <h4 className="text-sm font-bold text-slate-700">No critique yet</h4>
                          <p className="text-xs text-slate-500 mt-1">
                            Run the critique agent to get detailed feedback on skill gaps, impact metrics, and ATS alignment.
                          </p>
                        </div>
                        <button
                          onClick={() => critiqueCv(activeListing!.id)}
                          disabled={critiquingCV}
                          className="px-4 py-2 bg-rose-500 hover:bg-rose-600 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-sm transition-colors flex items-center gap-1.5 mx-auto"
                        >
                          {critiquingCV ? (
                            <><span className="spinner h-3 w-3"></span><span>Running...</span></>
                          ) : (
                            <span>Run CV Critique</span>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Modal Sidebar */}
              <div className="w-full md:w-56 bg-slate-50 p-6 border-t md:border-t-0 md:border-l border-slate-200 space-y-6">
                <div>
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
                    Actions
                  </h4>
                  <div className="space-y-2">
                    <button
                      onClick={() => tailorCv(activeListing.id)}
                      disabled={tailoringCV}
                      className="w-full py-2 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-sm transition-colors flex items-center justify-center gap-1.5"
                    >
                      {tailoringCV ? (
                        <>
                          <span className="spinner h-3 w-3"></span>
                          <span>Tailoring...</span>
                        </>
                      ) : (
                        <span>Tailor CV</span>
                      )}
                    </button>
                    <button
                      onClick={() => critiqueCv(activeListing.id)}
                      disabled={critiquingCV}
                      className="w-full py-2 bg-white hover:bg-rose-50 border border-rose-300 text-rose-700 text-xs font-bold rounded-lg shadow-sm transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
                    >
                      {critiquingCV ? (
                        <><span className="spinner h-3 w-3"></span><span>Critiquing...</span></>
                      ) : (
                        <span>Critique CV</span>
                      )}
                    </button>
                    <button
                      onClick={() => showToast('Cover letter tailoring coming soon!', 'info')}
                      className="w-full py-2 bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 text-xs font-bold rounded-lg shadow-sm transition-colors"
                    >
                      Tailor Letter
                    </button>
                  </div>
                </div>

                <div className="border-t border-slate-200 pt-4">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                    Tracker Status
                  </h4>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Add this listing to your tracker to manage its status and details.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

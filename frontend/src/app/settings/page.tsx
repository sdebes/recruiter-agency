'use client';

import React, { useState, useEffect } from 'react';
import { apiFetch } from '@/utils/api';
import { useNotifications } from '@/context/NotificationContext';
import { Profile, Archetype } from '@/types';

export default function Settings() {
  const { showToast } = useNotifications();

  // State
  const [profile, setProfile] = useState<Profile | null>(null);
  const [archetypes, setArchetypes] = useState<Archetype[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [savingArchetypes, setSavingArchetypes] = useState(false);

  // Accordion active index
  const [openArchIndex, setOpenArchIndex] = useState<number | null>(0);

  // Load configuration
  useEffect(() => {
    async function loadConfig() {
      try {
        const [profileData, archetypesData] = await Promise.all([
          apiFetch<Profile>('/api/config/profile'),
          apiFetch<{ archetypes: Archetype[] }>('/api/config/archetypes'),
        ]);

        setProfile(profileData);
        setArchetypes(archetypesData.archetypes || []);
      } catch (err: any) {
        showToast(err.message || 'Failed to load configuration files', 'error');
      } finally {
        setLoading(false);
      }
    }
    loadConfig();
  }, []);

  // Save Profile Form
  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;

    setSavingProfile(true);
    try {
      // In python/Jinja, we had target_roles and compensation inside candidate.
      // But in the load_profile we loaded it. Let's send the correct nested profile.
      await apiFetch('/api/config/profile', {
        method: 'POST',
        body: JSON.stringify(profile),
      });
      showToast('Profile saved!', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to save profile', 'error');
    } finally {
      setSavingProfile(false);
    }
  };

  // Save Search Preferences Form
  const saveSearchPrefs = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;

    setSavingPrefs(true);
    try {
      // Send the partial configuration or complete profile schema
      await apiFetch('/api/config/profile', {
        method: 'POST',
        body: JSON.stringify(profile),
      });
      showToast('Search preferences saved!', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to save search preferences', 'error');
    } finally {
      setSavingPrefs(false);
    }
  };

  // Save Archetypes Form
  const saveArchetypes = async (e: React.FormEvent) => {
    e.preventDefault();

    setSavingArchetypes(true);
    try {
      await apiFetch('/api/config/archetypes', {
        method: 'POST',
        body: JSON.stringify({ archetypes }),
      });
      showToast('Archetypes saved!', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to save archetypes', 'error');
    } finally {
      setSavingArchetypes(false);
    }
  };

  // Handle nested profile input changes
  const handleProfileChange = (keyPath: string, value: any) => {
    if (!profile) return;

    const newProfile = { ...profile };
    const keys = keyPath.split('.');
    let current: any = newProfile;

    for (let i = 0; i < keys.length - 1; i++) {
      current = current[keys[i]];
    }

    current[keys[keys.length - 1]] = value;
    setProfile(newProfile);
  };

  // Handle multi-line target roles changes
  const handleTargetRolesChange = (type: 'primary' | 'secondary', rawValue: string) => {
    const rolesList = rawValue.split('\n').map((s) => s.trim()).filter(Boolean);
    handleProfileChange(`target_roles.${type}`, rolesList);
  };

  // Handle Archetypes edits
  const handleArchetypeKeywordChange = (index: number, rawKeywords: string) => {
    const updated = [...archetypes];
    updated[index].keywords = rawKeywords.split(',').map((s) => s.trim()).filter(Boolean);
    setArchetypes(updated);
  };

  const handleArchetypeWeightChange = (archIndex: number, weightKey: string, val: number) => {
    const updated = [...archetypes];
    updated[archIndex].scoring_weights = {
      ...updated[archIndex].scoring_weights,
      [weightKey]: val,
    };
    setArchetypes(updated);
  };

  if (loading) {
    return (
      <div className="text-center py-24 animate-slide-in">
        <div className="spinner border-t-amber-500 h-10 w-10 border-4 mb-3"></div>
        <p className="text-slate-500 font-medium">Loading system configurations...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-slide-in">
      {/* Page Header */}
      <div>
        <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Settings</h2>
        <p className="text-sm text-slate-500 mt-1">Configure your profile, target roles, and scoring system.</p>
      </div>

      {profile && (
        <>
          {/* Profile Form */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
              <span className="font-semibold text-slate-800">
                Candidate Profile
              </span>
            </div>
            <div className="p-6">
              <form onSubmit={saveProfile} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Full Name</label>
                    <input
                      type="text"
                      value={profile.candidate?.full_name || ''}
                      onChange={(e) => handleProfileChange('candidate.full_name', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Email</label>
                    <input
                      type="email"
                      value={profile.candidate?.email || ''}
                      onChange={(e) => handleProfileChange('candidate.email', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Location</label>
                    <input
                      type="text"
                      value={profile.candidate?.location || ''}
                      onChange={(e) => handleProfileChange('candidate.location', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Visa Status</label>
                    <input
                      type="text"
                      value={profile.candidate?.visa_status || ''}
                      onChange={(e) => handleProfileChange('candidate.visa_status', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">LinkedIn URL</label>
                    <input
                      type="url"
                      value={profile.candidate?.linkedin || ''}
                      onChange={(e) => handleProfileChange('candidate.linkedin', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">GitHub URL</label>
                    <input
                      type="url"
                      value={profile.candidate?.github || ''}
                      onChange={(e) => handleProfileChange('candidate.github', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                    Target Roles — Primary
                  </label>
                  <textarea
                    rows={3}
                    value={profile.target_roles?.primary?.join('\n') || ''}
                    onChange={(e) => handleTargetRolesChange('primary', e.target.value)}
                    className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30 font-sans"
                    placeholder="Enter one role per line..."
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                    Target Roles — Secondary
                  </label>
                  <textarea
                    rows={3}
                    value={profile.target_roles?.secondary?.join('\n') || ''}
                    onChange={(e) => handleTargetRolesChange('secondary', e.target.value)}
                    className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30 font-sans"
                    placeholder="Enter one role per line..."
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Target Range</label>
                    <input
                      type="text"
                      value={profile.compensation?.target_range || ''}
                      onChange={(e) => handleProfileChange('compensation.target_range', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Currency</label>
                    <input
                      type="text"
                      value={profile.compensation?.currency || ''}
                      onChange={(e) => handleProfileChange('compensation.currency', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Minimum</label>
                    <input
                      type="text"
                      value={profile.compensation?.minimum || ''}
                      onChange={(e) => handleProfileChange('compensation.minimum', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-350 rounded-lg text-sm bg-slate-50/30"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={savingProfile}
                  className="px-5 py-2.5 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-sm transition-colors"
                >
                  {savingProfile ? 'Saving...' : 'Save Profile'}
                </button>
              </form>
            </div>
          </div>

          {/* Search Preferences Form */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
              <span className="font-semibold text-slate-800">
                Search Preferences
              </span>
            </div>
            <div className="p-6">
              <form onSubmit={saveSearchPrefs} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Country</label>
                    <input
                      type="text"
                      value={profile.search_preferences?.country || ''}
                      onChange={(e) => handleProfileChange('search_preferences.country', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-355 rounded-lg text-sm bg-slate-50/30"
                    />
                    <span className="text-[10px] text-slate-400 mt-1 block">Only show listings mentioning this country.</span>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Cities</label>
                    <input
                      type="text"
                      value={profile.search_preferences?.cities || ''}
                      onChange={(e) => handleProfileChange('search_preferences.cities', e.target.value)}
                      className="w-full px-4 py-2 border border-slate-355 rounded-lg text-sm bg-slate-50/30"
                    />
                    <span className="text-[10px] text-slate-400 mt-1 block">Only show listings in these cities (comma-separated).</span>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={savingPrefs}
                  className="px-5 py-2.5 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-sm transition-colors"
                >
                  {savingPrefs ? 'Saving...' : 'Save Search Preferences'}
                </button>
              </form>
            </div>
          </div>
        </>
      )}

      {/* Archetypes & Scoring Weights */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
              <span className="font-semibold text-slate-800">
                Archetypes &amp; Scoring Weights
              </span>
        </div>
        <div className="p-6">
          <form onSubmit={saveArchetypes} className="space-y-6">
            <div className="space-y-4">
              {archetypes.map((arch, archIndex) => {
                const isOpen = openArchIndex === archIndex;
                return (
                  <div
                    key={arch.name}
                    className="border border-slate-200 rounded-lg overflow-hidden transition-all duration-200"
                  >
                    {/* Expandable Header */}
                    <button
                      type="button"
                      onClick={() => setOpenArchIndex(isOpen ? null : archIndex)}
                      className="w-full px-5 py-3 bg-slate-50 hover:bg-slate-100/70 border-b border-slate-200 text-left text-sm font-bold text-slate-800 flex justify-between items-center"
                    >
                      <span>{arch.name}</span>
                      <span className={`text-xs text-slate-400 transform transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}>
                        ▼
                      </span>
                    </button>

                    {/* Expandable Body */}
                    {isOpen && (
                      <div className="p-5 space-y-4 bg-white animate-slide-in">
                        <div>
                          <label className="block text-xs font-bold text-slate-655 mb-2">
                            Keywords (comma-separated)
                          </label>
                          <input
                            type="text"
                            value={arch.keywords?.join(', ') || ''}
                            onChange={(e) => handleArchetypeKeywordChange(archIndex, e.target.value)}
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                          />
                        </div>

                        <div className="space-y-4 border-t border-slate-100 pt-4">
                          <label className="block text-xs font-bold text-slate-700">Scoring Weights</label>
                          <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
                            {[
                              { label: 'CV Match', key: 'cv_match' },
                              { label: 'North Star', key: 'north_star' },
                              { label: 'Comp', key: 'compensation' },
                              { label: 'Culture', key: 'culture' },
                              { label: 'Red Flags', key: 'red_flags' },
                            ].map((w) => {
                              const val = arch.scoring_weights?.[w.key as keyof typeof arch.scoring_weights] || 0.0;
                              return (
                                <div key={w.key} className="space-y-1">
                                  <div className="flex justify-between items-center text-[10px] font-bold text-slate-650">
                                    <span>{w.label}</span>
                                    <span className="text-amber-500 font-extrabold">{val.toFixed(2)}</span>
                                  </div>
                                  <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    value={val}
                                    onChange={(e) =>
                                      handleArchetypeWeightChange(archIndex, w.key, parseFloat(e.target.value))
                                    }
                                    className="w-full h-1 bg-slate-100 rounded-lg appearance-none cursor-pointer"
                                  />
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <button
              type="submit"
              disabled={savingArchetypes}
              className="px-5 py-2.5 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-sm transition-colors"
            >
              {savingArchetypes ? 'Saving...' : 'Save Archetypes'}
            </button>
          </form>
        </div>
      </div>

      {/* Info Integrations */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
          <span className="font-semibold text-slate-800">Master Resume Location</span>
        </div>
        <div className="p-6 space-y-3">
          <p className="text-xs text-slate-500 leading-relaxed">
            Your master resume source JSON file is stored at <code>config/resumeinfo.json</code>.
          </p>
          <p className="text-xs text-slate-500 leading-relaxed">
            When the AI tailors a CV, it modifies bulletpoints and profiles using this source data to create optimized target versions in the output directory.
          </p>
        </div>
      </div>

      {/* System Info */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
          <span className="font-semibold text-slate-800">System Info</span>
        </div>
        <div className="p-6">
          <pre className="p-4 bg-slate-900 text-slate-100 rounded-lg text-[10px] font-mono overflow-x-auto leading-relaxed shadow-inner">
            {JSON.stringify(
              {
                'Config Path': 'config/profile.yml',
                'Archetypes Path': 'config/archetypes.yml',
                'Database Path': 'agentdb/applications.db',
                'Server Port': '8000 (FastAPI)',
                'Frontend Port': '3000 (Next.js)',
              },
              null,
              2
            )}
          </pre>
        </div>
      </div>
    </div>
  );
}

'use client';

import React, { Suspense, useState, useEffect, useRef, useLayoutEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { apiFetch } from '@/utils/api';
import { useNotifications } from '@/context/NotificationContext';

interface ResumeData {
  name?: string;
  title?: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  summaries?: string[];
  skills?: Record<string, string[]>;
  experience?: Array<{
    company: string;
    role: string;
    startDate: string;
    endDate: string;
    location: string;
    bulletpoints?: string[];
  }>;
  education?: Array<{
    institution: string;
    degree?: string;
    major?: string;
    gpa?: string;
    startDate: string;
    endDate: string;
    location: string;
    bulletpoints?: string[];
  }>;
  projects?: Array<{
    name: string;
    link?: string;
    technologies?: string;
    description: string;
  }>;
  courses?: Array<{
    name: string;
    link?: string;
    description?: string;
  }>;
  references?: Array<{
    name: string;
    company: string;
    position: string;
    contact?: string;
  }>;
}

interface LayoutOptions {
  horizontalMargin: number;
  verticalMargin: number;
  padding: number;
  lineSpacing: number;
  showCourses: boolean;
  showProjects: boolean;
  showReferences: boolean;
  excludedProjects?: string[];
  excludedCourses?: string[];
  excludedReferences?: string[];
}

// Representing a block for pagination
interface PrintableBlock {
  id: string;
  type: 'header' | 'title' | 'summary' | 'skills' | 'experience' | 'education' | 'project' | 'coursework' | 'reference';
  html: string;
}

function ResumeBuilderInner() {
  const searchParams = useSearchParams();
  const resumeParam = searchParams.get('resume');
  const { showToast } = useNotifications();

  // State
  const [jsonText, setJsonText] = useState('');
  const [jsonStatus, setJsonStatus] = useState({ isValid: true, message: 'Valid JSON' });
  const [layoutOptions, setLayoutOptions] = useState<LayoutOptions>({
    horizontalMargin: 0.6,
    verticalMargin: 0.6,
    padding: 0.4,
    lineSpacing: 1.4,
    showCourses: true,
    showProjects: true,
    showReferences: true,
    excludedProjects: [],
    excludedCourses: [],
    excludedReferences: [],
  });
  const [autoSync, setAutoSync] = useState(true);
  const [isSynced, setIsSynced] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resumeData, setResumeData] = useState<ResumeData | null>(null);

  // Pagination Pages State
  const [pages, setPages] = useState<PrintableBlock[][]>([]);

  // Refs for measurement
  const hiddenContainerRef = useRef<HTMLDivElement>(null);
  const jsonEditorRef = useRef<HTMLTextAreaElement>(null);

  // Load resume data
  const fetchResumeData = async (force = false) => {
    try {
      let path = '/api/resume-builder/data';
      if (resumeParam) {
        path += `?resume=${encodeURIComponent(resumeParam)}`;
      }

      const data = await apiFetch<ResumeData>(path);
      const text = JSON.stringify(data, null, 2);

      setResumeData(data);
      setIsSynced(true);
      setJsonStatus({ isValid: true, message: 'Valid JSON' });

      // Update text in editor if not actively focused
      if (document.activeElement !== jsonEditorRef.current || force) {
        setJsonText(text);
      }
    } catch (err: any) {
      console.error(err);
      setIsSynced(false);
      setJsonStatus({ isValid: false, message: 'Sync failed: ' + err.message });
    }
  };

  useEffect(() => {
    fetchResumeData(true);
  }, [resumeParam]);

  // Polling for autosync
  useEffect(() => {
    if (!autoSync) return;

    const interval = setInterval(() => {
      fetchResumeData(false);
    }, 3000);

    return () => clearInterval(interval);
  }, [autoSync, resumeParam]);

  // Save to Server (Master only)
  const saveToServer = async () => {
    if (resumeParam) {
      showToast('Cannot save: this is a tailored resume. Edit the master resumeinfo.json instead.', 'warning');
      return;
    }

    try {
      JSON.parse(jsonText); // check validation
      setSaving(true);

      await apiFetch('/api/resume-builder/data', {
        method: 'POST',
        body: jsonText,
      });

      showToast('Resume data saved!', 'success');
      setJsonStatus({ isValid: true, message: 'Saved to server' });
    } catch (err: any) {
      setJsonStatus({ isValid: false, message: 'Save failed: ' + err.message });
      showToast('Save failed: ' + err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  // Handle typing inside JSON editor
  const handleJsonChange = (val: string) => {
    setJsonText(val);
    try {
      const data = JSON.parse(val);
      setResumeData(data);
      setJsonStatus({ isValid: true, message: 'JSON is valid (autoupdated preview)' });
    } catch (err: any) {
      setJsonStatus({ isValid: false, message: 'Typing... Invalid JSON format: ' + err.message });
    }
  };

  // Compile list of printable blocks
  const compileBlocks = (data: ResumeData, opts: LayoutOptions): PrintableBlock[] => {
    const list: PrintableBlock[] = [];
    const esc = (s?: string) => {
      if (!s) return '';
      return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    };
    const cleanUrl = (url?: string) => {
      if (!url) return '';
      return url.startsWith('http') ? url : 'https://' + url;
    };

    // 1. Header
    const contacts: string[] = [];
    if (data.email) contacts.push(`<a href="mailto:${data.email}">${esc(data.email)}</a>`);
    if (data.phone) contacts.push(`<span>${esc(data.phone)}</span>`);
    if (data.location) contacts.push(`<span>${esc(data.location)}</span>`);
    if (data.linkedin) contacts.push(`<a href="${cleanUrl(data.linkedin)}" target="_blank" rel="noopener">${esc(data.linkedin)}</a>`);
    if (data.github) contacts.push(`<a href="${cleanUrl(data.github)}" target="_blank" rel="noopener">${esc(data.github)}</a>`);

    const headerHtml = `
      <div class="resume-header text-right flex items-center gap-5 pb-3 border-b-2 border-black mb-3 font-serif">
        <div class="grow">
          <h1 class="resume-name text-3xl font-bold tracking-widest uppercase mb-1 font-serif" style="font-variant: small-caps;">${esc(data.name || 'Jane Doe')}</h1>
          <div class="resume-title text-sm font-bold text-slate-700 tracking-wider uppercase mb-1 font-serif">${esc(data.title || 'Engineer')}</div>
          <div class="resume-contact text-[10px] text-slate-800 gap-1.5 font-serif">${contacts.join(' | ')}</div>
        </div>
      </div>
    `;
    list.push({ id: 'header', type: 'header', html: headerHtml });

    // 2. Summary
    if (data.summaries && data.summaries.length > 0) {
      list.push({ id: 'summary-title', type: 'title', html: `<div class="resume-section-title text-base font-bold border-b border-black pb-0.5 mt-4 mb-2 font-serif uppercase tracking-wider">Summary</div>` });
      list.push({
        id: 'summary-content',
        type: 'summary',
        html: `<p class="resume-summary text-xs text-justify leading-relaxed font-serif" style="margin: 2px 0;">${esc(data.summaries[0])}</p>`,
      });
    }

    // 3. Skills
    if (data.skills && Object.keys(data.skills).length > 0) {
      list.push({ id: 'skills-title', type: 'title', html: `<div class="resume-section-title text-base font-bold border-b border-black pb-0.5 mt-4 mb-2 font-serif uppercase tracking-wider">Technical Skills</div>` });
      let skillsHtml = `<div class="skills-section font-serif text-xs space-y-1">`;
      for (const cat in data.skills) {
        if (Array.isArray(data.skills[cat]) && data.skills[cat].length > 0) {
          const catName = cat.charAt(0).toUpperCase() + cat.slice(1);
          skillsHtml += `
            <div class="skill-item flex gap-1">
              <span class="skill-label font-bold shrink-0">${esc(catName)}:</span>
              <span>${data.skills[cat].map(esc).join(', ')}</span>
            </div>
          `;
        }
      }
      skillsHtml += `</div>`;
      list.push({ id: 'skills-content', type: 'skills', html: skillsHtml });
    }

    // 4. Experience
    if (data.experience && data.experience.length > 0) {
      list.push({ id: 'exp-title', type: 'title', html: `<div class="resume-section-title text-base font-bold border-b border-black pb-0.5 mt-4 mb-2 font-serif uppercase tracking-wider">Work Experience</div>` });
      data.experience.forEach((exp, idx) => {
        let expHtml = `
          <div class="resume-item mb-3 font-serif">
            <div class="resume-item-header flex justify-between font-bold text-xs">
              <span>${esc(exp.company)}</span>
              <span>${esc(exp.startDate)} – ${esc(exp.endDate)}</span>
            </div>
            <div class="flex justify-between text-xs italic text-slate-800">
              <span class="resume-item-subtitle font-serif font-medium">${esc(exp.role)}</span>
              <span class="resume-item-location font-serif">${esc(exp.location)}</span>
            </div>
        `;
        if (exp.bulletpoints && exp.bulletpoints.length > 0) {
          expHtml += `<ul class="resume-list pl-5 list-disc mt-1 text-xs space-y-0.5">`;
          exp.bulletpoints.forEach((b) => {
            expHtml += `<li class="pl-1">${esc(b)}</li>`;
          });
          expHtml += `</ul>`;
        }
        expHtml += `</div>`;
        list.push({ id: `exp-${idx}`, type: 'experience', html: expHtml });
      });
    }

    // 5. Education
    if (data.education && data.education.length > 0) {
      list.push({ id: 'edu-title', type: 'title', html: `<div class="resume-section-title text-base font-bold border-b border-black pb-0.5 mt-4 mb-2 font-serif uppercase tracking-wider">Education</div>` });
      data.education.forEach((edu, idx) => {
        const degreeDetails: string[] = [];
        if (edu.degree) degreeDetails.push(edu.degree);
        if (edu.major) degreeDetails.push(edu.major);
        let detailStr = degreeDetails.join(' in ');
        if (edu.gpa) detailStr += ` (GPA: ${edu.gpa})`;

        let eduHtml = `
          <div class="resume-item mb-3 font-serif">
            <div class="resume-item-header flex justify-between font-bold text-xs">
              <span>${esc(edu.institution)}</span>
              <span>${esc(edu.startDate)} – ${esc(edu.endDate)}</span>
            </div>
            <div class="flex justify-between text-xs italic text-slate-800">
              <span class="resume-item-subtitle font-serif font-medium">${esc(detailStr)}</span>
              <span class="resume-item-location font-serif">${esc(edu.location)}</span>
            </div>
        `;
        if (edu.bulletpoints && edu.bulletpoints.length > 0) {
          eduHtml += `<ul class="resume-list pl-5 list-disc mt-1 text-xs space-y-0.5">`;
          edu.bulletpoints.forEach((b) => {
            eduHtml += `<li class="pl-1">${esc(b)}</li>`;
          });
          eduHtml += `</ul>`;
        }
        eduHtml += `</div>`;
        list.push({ id: `edu-${idx}`, type: 'education', html: eduHtml });
      });
    }

    // 6. Projects
    if (opts.showProjects && data.projects && data.projects.length > 0) {
      const activeProjects = data.projects.filter(p => !(opts.excludedProjects || []).includes(p.name));
      if (activeProjects.length > 0) {
        list.push({ id: 'proj-title', type: 'title', html: `<div class="resume-section-title text-base font-bold border-b border-black pb-0.5 mt-4 mb-2 font-serif uppercase tracking-wider">Projects</div>` });
        activeProjects.forEach((proj, idx) => {
          const titleLink = proj.link
            ? `<a href="${cleanUrl(proj.link)}" target="_blank" rel="noopener" class="underline font-bold">${esc(proj.name)}</a>`
            : `<span class="font-bold">${esc(proj.name)}</span>`;
          const techHtml = proj.technologies
            ? `<span class="text-xs font-serif italic text-slate-655 font-normal">${esc(proj.technologies)}</span>`
            : '';

          const projHtml = `
            <div class="resume-item mb-3 font-serif">
              <div class="resume-item-header flex justify-between items-center text-xs">
                ${titleLink}
                ${techHtml}
              </div>
              <div class="resume-item-subtitle text-xs font-normal mt-0.5 leading-relaxed">${esc(proj.description)}</div>
            </div>
          `;
          list.push({ id: `proj-${idx}`, type: 'project', html: projHtml });
        });
      }
    }

    // 7. Coursework
    if (opts.showCourses && data.courses && data.courses.length > 0) {
      const activeCourses = data.courses.filter(c => !(opts.excludedCourses || []).includes(c.name));
      if (activeCourses.length > 0) {
        list.push({ id: 'courses-title', type: 'title', html: `<div class="resume-section-title text-base font-bold border-b border-black pb-0.5 mt-4 mb-2 font-serif uppercase tracking-wider">Relevant Coursework</div>` });
        let coursesHtml = `<ul class="coursework-grid grid grid-cols-2 gap-x-6 gap-y-1 list-disc pl-5 font-serif text-xs">`;
        activeCourses.forEach((c) => {
          const cName = c.link
            ? `<a href="${cleanUrl(c.link)}" target="_blank" rel="noopener" class="underline font-bold">${esc(c.name)}</a>`
            : `<strong>${esc(c.name)}</strong>`;
          const desc = c.description ? `: ${esc(c.description)}` : '';
          coursesHtml += `<li>${cName}${desc}</li>`;
        });
        coursesHtml += `</ul>`;
        list.push({ id: 'courses-content', type: 'coursework', html: coursesHtml });
      }
    }

    // 8. References
    if (opts.showReferences && data.references && data.references.length > 0) {
      const activeRefs = data.references.filter(r => !(opts.excludedReferences || []).includes(r.name));
      if (activeRefs.length > 0) {
        list.push({ id: 'ref-title', type: 'title', html: `<div class="resume-section-title text-base font-bold border-b border-black pb-0.5 mt-4 mb-2 font-serif uppercase tracking-wider">References</div>` });
        activeRefs.forEach((ref, idx) => {
          const refHtml = `
            <div class="resume-item mb-3 font-serif text-xs">
              <div class="resume-item-header flex justify-between font-bold">
                <span>${esc(ref.name)}</span>
                <span>${esc(ref.company)}</span>
              </div>
              <div class="flex justify-between italic text-slate-800">
                <span class="resume-item-subtitle">${esc(ref.position)}</span>
                <span>${esc(ref.contact || '')}</span>
              </div>
            </div>
          `;
          list.push({ id: `ref-${idx}`, type: 'reference', html: refHtml });
        });
      }
    }

    return list;
  };

  // Perform PDF Pagination calculations
  const calculatePagination = () => {
    if (!resumeData || !hiddenContainerRef.current) return;

    // letter page height: 11in = 1056px at 96dpi
    // page width: 8.5in = 816px
    const dpi = 96;
    const pageHeight = 11 * dpi;
    const verticalPadding = layoutOptions.verticalMargin * 2 * dpi;
    const printableHeight = pageHeight - verticalPadding;

    const childNodes = hiddenContainerRef.current.children;
    const blocksList = compileBlocks(resumeData, layoutOptions);

    if (childNodes.length !== blocksList.length) return;

    const measuredBlocks = blocksList.map((block, idx) => {
      const el = childNodes[idx] as HTMLElement;
      return {
        ...block,
        height: el.offsetHeight,
      };
    });

    const calculatedPages: PrintableBlock[][] = [];
    let currentPage: PrintableBlock[] = [];
    let currentHeight = 0;

    measuredBlocks.forEach((block, idx) => {
      // If adding this block overflows the printable area
      if (currentHeight + block.height > printableHeight - 20) { // small buffer for page numbering
        // Check for orphan title: if the last element in currentPage is a title block, shift it to next page
        const lastInPage = currentPage[currentPage.length - 1];
        if (lastInPage && lastInPage.html.includes('resume-section-title')) {
          currentPage.pop();
          calculatedPages.push(currentPage);
          currentPage = [lastInPage, block];
          currentHeight = measuredBlocks[idx - 1].height + block.height;
        } else {
          calculatedPages.push(currentPage);
          currentPage = [block];
          currentHeight = block.height;
        }
      } else {
        currentPage.push(block);
        currentHeight += block.height;
      }
    });

    if (currentPage.length > 0) {
      calculatedPages.push(currentPage);
    }

    setPages(calculatedPages);
  };

  // Run pagination layout whenever resumeData, layoutOptions change
  useLayoutEffect(() => {
    if (resumeData) {
      // Delay slightly to let the hidden container render so heights can be read accurately
      const timer = setTimeout(() => {
        calculatePagination();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [resumeData, layoutOptions]);

  // Copy HTML
  const copyHtmlToClipboard = () => {
    const previewContainer = document.getElementById('renderedPreviewPages');
    if (!previewContainer) return;

    const tempInput = document.createElement('textarea');
    tempInput.value = previewContainer.innerHTML;
    document.body.appendChild(tempInput);
    tempInput.select();
    document.execCommand('copy');
    document.body.removeChild(tempInput);

    showToast('HTML copied to clipboard!', 'success');
  };

  const blocksToMeasure = resumeData ? compileBlocks(resumeData, layoutOptions) : [];

  return (
    <div className="space-y-6 animate-slide-in pb-12">
      {/* Page Header */}
      <div>
        <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Resume Builder</h2>
        <p className="text-sm text-slate-500 mt-1">Edit master JSON, render layout live, and print PDFs.</p>
      </div>

      {resumeParam && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex justify-between items-center text-xs text-amber-800 font-medium">
          <span>
            <strong>Tailored Resume View:</strong> {decodeURIComponent(resumeParam).split('/').pop()}
          </span>
          <a href="/resume-builder" className="text-amber-955 font-bold hover:underline">
            View Master Resume &rarr;
          </a>
        </div>
      )}

      {/* Hidden Container for Pagination Calculations */}
      <div
        ref={hiddenContainerRef}
        style={{
          position: 'absolute',
          top: '-9999px',
          left: '-9999px',
          width: `${(8.5 - layoutOptions.horizontalMargin * 2) * 96}px`, // exact width of print area in pixels
          fontFamily: '"Computer Modern", "Times New Roman", serif',
        }}
      >
        {blocksToMeasure.map((b) => (
          <div
            key={b.id}
            dangerouslySetInnerHTML={{ __html: b.html }}
            style={{
              lineHeight: layoutOptions.lineSpacing,
              fontSize: '11pt',
            }}
          />
        ))}
      </div>

      {/* Two Column Workspace */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6 items-start">
        {/* Left Side Preview Panel */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 overflow-hidden flex flex-col">
          <h3 className="text-lg font-bold text-slate-800 mb-4">Resume Preview</h3>

          {/* Rendered Preview Pages */}
          <div id="renderedPreviewPages" className="bg-slate-100 p-6 rounded-xl border border-slate-200 flex flex-col items-center gap-6 overflow-x-auto min-h-[500px]">
            {pages.length > 0 ? (
              pages.map((pageBlocks, pageIdx) => (
                <div
                  key={pageIdx}
                  className="bg-white shadow-xl relative overflow-hidden flex flex-col border border-amber-300 print:border-none select-text"
                  style={{
                    width: '8.5in',
                    height: '11in',
                    padding: `${layoutOptions.padding}in`,
                    boxSizing: 'border-box',
                    fontFamily: 'Georgia, serif', // Computer Modern fallback
                    color: '#000',
                  }}
                >
                  <div className="flex-1 flex flex-col">
                    {pageBlocks.map((b) => (
                      <div
                        key={b.id}
                        dangerouslySetInnerHTML={{ __html: b.html }}
                        style={{
                          lineHeight: layoutOptions.lineSpacing,
                          fontSize: '10.5pt',
                        }}
                      />
                    ))}
                  </div>

                  {/* Page Footer */}
                  <div
                    className="absolute text-slate-500 font-mono"
                    style={{
                      bottom: '0.3in',
                      right: `${layoutOptions.horizontalMargin}in`,
                      fontSize: '8.5pt',
                    }}
                  >
                    Page {pageIdx + 1} of {pages.length}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-400 mt-20">Loading and formatting resume layout...</p>
            )}
          </div>

          {/* Actions below preview */}
          <div className="flex gap-4 mt-6">
            <button
              onClick={() => window.print()}
              className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-900 text-white font-bold text-xs rounded-lg transition-colors shadow-sm"
            >
              Download PDF
            </button>
            <button
              onClick={copyHtmlToClipboard}
              className="flex-1 py-2.5 bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 font-bold text-xs rounded-lg transition-colors shadow-sm"
            >
              Copy HTML
            </button>
          </div>
        </div>

        {/* Right Side Options & Editor Panel */}
        <div className="space-y-6">
          {/* Controls Card */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-6">
            <div className="flex justify-between items-center pb-4 border-b border-slate-100">
              <h3 className="font-bold text-slate-800 text-sm">Resume Configurer</h3>
              <div className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  id="autoSync"
                  checked={autoSync}
                  onChange={(e) => setAutoSync(e.target.checked)}
                  className="rounded text-amber-500 focus:ring-amber-500"
                />
                <label htmlFor="autoSync" className="text-xs font-medium cursor-pointer text-slate-600">
                  Auto
                </label>
                <span
                  className={`h-2 w-2 rounded-full ${isSynced ? 'bg-emerald-500' : 'bg-rose-500'}`}
                  title={isSynced ? 'Synced' : 'Sync Error'}
                ></span>
              </div>
            </div>

            {/* Layout Options */}
            <div className="space-y-4">
              <h4 className="text-xs font-bold text-slate-700">Layout Settings</h4>

              <div className="space-y-1">
                <div className="flex justify-between text-xs text-slate-600">
                  <span>Page Margin</span>
                  <span className="font-bold font-mono">{layoutOptions.horizontalMargin.toFixed(2)} in</span>
                </div>
                <input
                  type="range"
                  min="0.3"
                  max="1.0"
                  step="0.05"
                  value={layoutOptions.horizontalMargin}
                  onChange={(e) => setLayoutOptions({ ...layoutOptions, horizontalMargin: parseFloat(e.target.value) })}
                  className="w-full h-1 bg-slate-100 rounded-lg appearance-none cursor-pointer"
                />
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-xs text-slate-600">
                  <span>Line Spacing</span>
                  <span className="font-bold font-mono">{layoutOptions.lineSpacing.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min="1.0"
                  max="2.0"
                  step="0.1"
                  value={layoutOptions.lineSpacing}
                  onChange={(e) => setLayoutOptions({ ...layoutOptions, lineSpacing: parseFloat(e.target.value) })}
                  className="w-full h-1 bg-slate-100 rounded-lg appearance-none cursor-pointer"
                />
              </div>

              {/* Toggles & Sub-checkboxes */}
              <div className="space-y-4 pt-2 border-t border-slate-100 font-sans">
                <h5 className="text-xs font-bold text-slate-700">Section Visibility</h5>

                {/* Projects */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer font-medium">
                    <input
                      type="checkbox"
                      checked={layoutOptions.showProjects}
                      onChange={(e) => setLayoutOptions({ ...layoutOptions, showProjects: e.target.checked })}
                      className="rounded text-amber-500 focus:ring-amber-500"
                    />
                    Include Projects
                  </label>
                  {layoutOptions.showProjects && resumeData?.projects && resumeData.projects.length > 0 && (
                    <div className="pl-4 ml-1 border-l border-slate-200 space-y-1 flex flex-col">
                      {resumeData.projects.map((p) => {
                        const isExcluded = (layoutOptions.excludedProjects || []).includes(p.name);
                        return (
                          <label key={p.name} className="flex items-center gap-1.5 text-[11px] text-slate-500 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={!isExcluded}
                              onChange={(e) => {
                                const excl = layoutOptions.excludedProjects || [];
                                const next = e.target.checked
                                  ? excl.filter((name) => name !== p.name)
                                  : [...excl, p.name];
                                setLayoutOptions({ ...layoutOptions, excludedProjects: next });
                              }}
                              className="rounded text-amber-500 focus:ring-amber-500"
                            />
                            {p.name}
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Courses */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer font-medium">
                    <input
                      type="checkbox"
                      checked={layoutOptions.showCourses}
                      onChange={(e) => setLayoutOptions({ ...layoutOptions, showCourses: e.target.checked })}
                      className="rounded text-amber-500 focus:ring-amber-500"
                    />
                    Include Courses
                  </label>
                  {layoutOptions.showCourses && resumeData?.courses && resumeData.courses.length > 0 && (
                    <div className="pl-4 ml-1 border-l border-slate-200 space-y-1 flex flex-col">
                      {resumeData.courses.map((c) => {
                        const isExcluded = (layoutOptions.excludedCourses || []).includes(c.name);
                        return (
                          <label key={c.name} className="flex items-center gap-1.5 text-[11px] text-slate-500 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={!isExcluded}
                              onChange={(e) => {
                                const excl = layoutOptions.excludedCourses || [];
                                const next = e.target.checked
                                  ? excl.filter((name) => name !== c.name)
                                  : [...excl, c.name];
                                setLayoutOptions({ ...layoutOptions, excludedCourses: next });
                              }}
                              className="rounded text-amber-500 focus:ring-amber-500"
                            />
                            {c.name}
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* References */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer font-medium">
                    <input
                      type="checkbox"
                      checked={layoutOptions.showReferences}
                      onChange={(e) => setLayoutOptions({ ...layoutOptions, showReferences: e.target.checked })}
                      className="rounded text-amber-500 focus:ring-amber-500"
                    />
                    Include References
                  </label>
                  {layoutOptions.showReferences && resumeData?.references && resumeData.references.length > 0 && (
                    <div className="pl-4 ml-1 border-l border-slate-200 space-y-1 flex flex-col">
                      {resumeData.references.map((r) => {
                        const isExcluded = (layoutOptions.excludedReferences || []).includes(r.name);
                        return (
                          <label key={r.name} className="flex items-center gap-1.5 text-[11px] text-slate-500 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={!isExcluded}
                              onChange={(e) => {
                                const excl = layoutOptions.excludedReferences || [];
                                const next = e.target.checked
                                  ? excl.filter((name) => name !== r.name)
                                  : [...excl, r.name];
                                setLayoutOptions({ ...layoutOptions, excludedReferences: next });
                              }}
                              className="rounded text-amber-500 focus:ring-amber-500"
                            />
                            {r.name} ({r.company})
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-3 pt-2 border-t border-slate-100">
              <button
                onClick={() => fetchResumeData(true)}
                className="flex-1 py-1.5 border border-slate-300 text-slate-700 text-xs font-bold rounded-lg shadow-sm hover:bg-slate-50 transition-colors"
              >
                Reload
              </button>
              <button
                onClick={saveToServer}
                disabled={saving || !!resumeParam}
                className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-sm transition-colors"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>

          {/* JSON Editor Card */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-4">
            <div className="flex justify-between items-center">
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                Source JSON (Editable)
              </label>
              <span className={`text-[10px] font-extrabold ${jsonStatus.isValid ? 'text-emerald-500' : 'text-rose-500'}`}>
                {jsonStatus.message}
              </span>
            </div>

            <textarea
              ref={jsonEditorRef}
              value={jsonText}
              onChange={(e) => handleJsonChange(e.target.value)}
              className="w-full h-80 px-3 py-2 border border-slate-300 rounded-lg text-[10px] font-mono leading-relaxed bg-slate-50 focus:outline-none focus:ring-1 focus:ring-amber-500"
              placeholder="Loading resume JSON data..."
            />

            <button
              onClick={() => handleJsonChange(jsonText)}
              className="w-full py-2 bg-slate-100 hover:bg-slate-200/80 text-slate-700 text-xs font-bold rounded-lg transition-colors border border-slate-250"
            >
              Render Manual Changes
            </button>
          </div>
        </div>
      </div>

      {/* Printing style tag wrapper */}
      <style jsx global>{`
        @media print {
          body {
            background: white !important;
            padding: 0 !important;
            margin: 0 !important;
          }
          main {
            margin-left: 0 !important;
            padding: 0 !important;
          }
          aside, nav, header, button, .aside, .sidebar, select, input, label, textarea,
          .bg-slate-50, .shadow-sm, .bg-white, .border-t, .xl\\:grid-cols-\\[1fr_380px\\],
          .space-y-6, .text-3xl {
            display: none !important;
          }
          #renderedPreviewPages {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            margin: 0 !important;
            display: block !important;
            overflow: visible !important;
          }
          .bg-white.shadow-xl {
            box-shadow: none !important;
            border: none !important;
            margin: 0 !important;
            page-break-after: always !important;
            break-after: page !important;
          }
        }
      `}</style>
    </div>
  );
}

export default function ResumeBuilder() {
  return (
    <Suspense fallback={<div className="text-center py-20 text-sm text-slate-500">Loading resume builder...</div>}>
      <ResumeBuilderInner />
    </Suspense>
  );
}

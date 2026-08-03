document.addEventListener("DOMContentLoaded", () => {
    const jsonEditor = document.getElementById("jsonEditor");
    const jsonStatus = document.getElementById("jsonStatus");
    const renderBtn = document.getElementById("renderBtn");
    const fetchBtn = document.getElementById("fetchBtn");
    const autoSync = document.getElementById("autoSync");
    const syncIndicator = document.getElementById("syncIndicator");
    const resumePreview = document.getElementById("resumePreview");
    const downloadBtn = document.getElementById("downloadBtn");
    const copyBtn = document.getElementById("copyBtn");
    const saveBtn = document.getElementById("saveBtn");

    const marginSlider = document.getElementById("marginSlider");
    const marginValue = document.getElementById("marginValue");
    const lineSpacingSlider = document.getElementById("lineSpacingSlider");
    const lineSpacingValue = document.getElementById("lineSpacingValue");
    const includeCourses = document.getElementById("includeCourses");
    const includeProjects = document.getElementById("includeProjects");
    const includeReferences = document.getElementById("includeReferences");

    let lastFetchedJsonString = "";
    let pollInterval = null;

    // Helper to format HTML elements safely
    function escapeHTML(str) {
        if (!str) return "";
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Function to render the resume layout based on JSON
    function renderResume(data, options) {
        options = options || {};
        const pageMargin = options.margin || 0.6;
        const lineSpacing = options.lineSpacing || 1.4;
        const showCourses = options.showCourses !== false;
        const showProjects = options.showProjects !== false;
        const showReferences = options.showReferences !== false;

        resumePreview.innerHTML = ""; // Clear existing contents

        // Helper to format HTML elements safely
        function escapeHTML(str) {
            if (!str) return "";
            return str
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        // Helper to parse strings/URLs for safe attribute usage
        function getCleanUrl(url) {
            if (!url) return "";
            return url.startsWith("http") ? url : "https://" + url;
        }

        // Helper to instantiate DOM element from HTML
        function createElementFromHTML(htmlString) {
            const div = document.createElement("div");
            div.innerHTML = htmlString.trim();
            return div.firstElementChild;
        }

        // 1. Build list of individual printable blocks
        const blocks = [];

        // Header block
        let contacts = [];
        if (data.email) contacts.push(`<a href="mailto:${data.email}">${escapeHTML(data.email)}</a>`);
        if (data.phone) contacts.push(`<span>${escapeHTML(data.phone)}</span>`);
        if (data.location) contacts.push(`<span>${escapeHTML(data.location)}</span>`);
        if (data.linkedin) contacts.push(`<a href="${getCleanUrl(data.linkedin)}" target="_blank">${escapeHTML(data.linkedin)}</a>`);
        if (data.github) contacts.push(`<a href="${getCleanUrl(data.github)}" target="_blank">${escapeHTML(data.github)}</a>`);

        const headerHtml = `
            <div class="resume-header">
                <img src="/static/resume-builder/portrait.jpg" class="resume-portrait" alt="${escapeHTML(data.name || 'Portrait')}" onerror="this.style.display='none'">
                <div class="resume-header-details">
                    <h1 class="resume-name">${escapeHTML(data.name || 'Jane Doe')}</h1>
                    <div class="resume-title">${escapeHTML(data.title || 'ML Engineer')}</div>
                    <div class="resume-contact">${contacts.join(" | ")}</div>
                </div>
            </div>
        `;
        blocks.push({ type: "header", element: createElementFromHTML(headerHtml) });

        // Summary block
        if (data.summaries) {
            blocks.push({ type: "title", title: "Summary", element: createElementFromHTML(`<div class="resume-section-title">Summary</div>`) });
            blocks.push({
                type: "content", element: createElementFromHTML(`<p class="resume-summary" style="font-size: 10pt; line-height: 1.4; text-align: justify; margin: 5px 0;">${escapeHTML(data.summaries[0])}</p>`)
            });
        }

        // Skills block
        if (data.skills && typeof data.skills === "object") {
            blocks.push({ type: "title", title: "Technical Skills", element: createElementFromHTML(`<div class="resume-section-title">Technical Skills</div>`) });
            let skillsHtml = `<div class="skills-section">`;
            for (let category in data.skills) {
                if (Array.isArray(data.skills[category]) && data.skills[category].length > 0) {
                    const cleanCategoryName = category.charAt(0).toUpperCase() + category.slice(1);
                    skillsHtml += `
                        <div class="skill-item" style="font-size: 10pt;">
                            <span class="skill-label">${escapeHTML(cleanCategoryName)}:</span>
                            <span>${data.skills[category].map(escapeHTML).join(", ")}</span>
                        </div>
                    `;
                }
            }
            skillsHtml += `</div>`;
            blocks.push({ type: "content", element: createElementFromHTML(skillsHtml) });
        }

        // Experience blocks
        if (data.experience && Array.isArray(data.experience) && data.experience.length > 0) {
            blocks.push({ type: "title", title: "Work Experience", element: createElementFromHTML(`<div class="resume-section-title">Work Experience</div>`) });
            data.experience.forEach(exp => {
                let expHtml = `
                    <div class="resume-item">
                        <div class="resume-item-header">
                            <span>${escapeHTML(exp.company)}</span>
                            <span>${escapeHTML(exp.startDate)} – ${escapeHTML(exp.endDate)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 10pt;">
                            <span class="resume-item-subtitle">${escapeHTML(exp.role)}</span>
                            <span class="resume-item-location">${escapeHTML(exp.location)}</span>
                        </div>
                `;
                if (exp.bulletpoints && Array.isArray(exp.bulletpoints) && exp.bulletpoints.length > 0) {
                    expHtml += `<ul class="resume-list">`;
                    exp.bulletpoints.forEach(bullet => {
                        expHtml += `<li>${escapeHTML(bullet)}</li>`;
                    });
                    expHtml += `</ul>`;
                }
                expHtml += `</div>`;
                blocks.push({ type: "item", element: createElementFromHTML(expHtml) });
            });
        }

        // Education blocks
        if (data.education && Array.isArray(data.education) && data.education.length > 0) {
            blocks.push({ type: "title", title: "Education", element: createElementFromHTML(`<div class="resume-section-title">Education</div>`) });
            data.education.forEach(edu => {
                let degreeMajor = [];
                if (edu.degree) degreeMajor.push(edu.degree);
                if (edu.major) degreeMajor.push(edu.major);
                let detailsStr = degreeMajor.join(" in ");
                if (edu.gpa) detailsStr += ` (GPA: ${edu.gpa})`;

                let eduHtml = `
                    <div class="resume-item">
                        <div class="resume-item-header">
                            <span>${escapeHTML(edu.institution)}</span>
                            <span>${escapeHTML(edu.startDate)} – ${escapeHTML(edu.endDate)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 10pt;">
                            <span class="resume-item-subtitle">${escapeHTML(detailsStr)}</span>
                            <span class="resume-item-location">${escapeHTML(edu.location)}</span>
                        </div>
                `;
                if (edu.bulletpoints && Array.isArray(edu.bulletpoints) && edu.bulletpoints.length > 0) {
                    eduHtml += `<ul class="resume-list">`;
                    edu.bulletpoints.forEach(bullet => {
                        eduHtml += `<li>${escapeHTML(bullet)}</li>`;
                    });
                    eduHtml += `</ul>`;
                }
                eduHtml += `</div>`;
                blocks.push({ type: "item", element: createElementFromHTML(eduHtml) });
            });
        }

        // Projects blocks
        if (showProjects && data.projects && Array.isArray(data.projects) && data.projects.length > 0) {
            blocks.push({ type: "title", title: "Projects", element: createElementFromHTML(`<div class="resume-section-title">Projects</div>`) });
            data.projects.forEach(project => {
                let nameHtml = project.link
                    ? `<a href="${getCleanUrl(project.link)}" target="_blank" style="text-decoration: underline; color: #000;">${escapeHTML(project.name)}</a>`
                    : escapeHTML(project.name);
                let techHtml = project.technologies
                    ? `<span style="font-weight: normal; font-size: 10pt; font-style: italic;">${escapeHTML(project.technologies)}</span>`
                    : '';

                let projHtml = `
                    <div class="resume-item">
                        <div class="resume-item-header">
                            <span>${nameHtml}</span>
                            ${techHtml}
                        </div>
                        <div class="resume-item-subtitle" style="font-weight: normal; font-style: normal; margin-top: 3px; font-size: 10pt;">${escapeHTML(project.description)}</div>
                    </div>
                `;
                blocks.push({ type: "item", element: createElementFromHTML(projHtml) });
            });
        }

        // Courses blocks
        if (showCourses && data.courses && Array.isArray(data.courses) && data.courses.length > 0) {
            blocks.push({ type: "title", title: "Relevant Coursework", element: createElementFromHTML(`<div class="resume-section-title">Relevant Coursework</div>`) });
            let coursesHtml = `<ul class="coursework-grid">`;
            data.courses.forEach(course => {
                let courseName = course.name;
                if (course.link) {
                    courseName = `<a href="${getCleanUrl(course.link)}" target="_blank" style="text-decoration: underline; color: #000;">${escapeHTML(course.name)}</a>`;
                }
                let desc = course.description ? `: ${escapeHTML(course.description)}` : "";
                coursesHtml += `<li style="font-size: 10pt;"><strong>${courseName}</strong>${desc}</li>`;
            });
            coursesHtml += `</ul>`;
            blocks.push({ type: "content", element: createElementFromHTML(coursesHtml) });
        }

        // References blocks
        if (showReferences && data.references && Array.isArray(data.references) && data.references.length > 0) {
            blocks.push({ type: "title", title: "References", element: createElementFromHTML(`<div class="resume-section-title">References</div>`) });
            data.references.forEach(ref => {
                let refHtml = `
                    <div class="resume-item">
                        <div class="resume-item-header">
                            <span>${escapeHTML(ref.name)}</span>
                            <span>${escapeHTML(ref.company)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 10pt;">
                            <span class="resume-item-subtitle">${escapeHTML(ref.position)}</span>
                            <span class="resume-item-location">${escapeHTML(ref.contact || "")}</span>
                        </div>
                    </div>
                `;
                blocks.push({ type: "item", element: createElementFromHTML(refHtml) });
            });
        }

        // 2. Perform Paginated Rendering
        let pageNum = 1;

        function createNewPage() {
            const page = document.createElement("div");
            page.className = "resume-page";
            page.id = `page-${pageNum}`;
            page.style.padding = `${pageMargin}in`;
            page.style.lineHeight = lineSpacing;

            const footer = document.createElement("div");
            footer.className = "resume-page-footer";
            footer.style.position = "absolute";
            footer.style.bottom = "0.3in";
            footer.style.right = "0.6in";
            footer.style.fontSize = "8.5pt";
            footer.style.color = "#777";
            footer.style.fontFamily = "Computer Modern, Times New Roman, serif";
            footer.textContent = `Page ${pageNum}`;

            page.appendChild(footer);
            resumePreview.appendChild(page);
            pageNum++;
            return page;
        }

        let currentPage = createNewPage();

        blocks.forEach((block) => {
            const footer = currentPage.querySelector(".resume-page-footer");
            currentPage.insertBefore(block.element, footer);

            // Check if adding this block overflows the page
            if (currentPage.scrollHeight > currentPage.clientHeight) {
                // Yes, remove it from this page
                currentPage.removeChild(block.element);

                // Check for orphan header (a title block with no content below it)
                const children = Array.from(currentPage.children).filter(c => c !== footer);
                const lastChild = children[children.length - 1];
                const titleMoved = [];

                if (lastChild && lastChild.classList.contains("resume-section-title")) {
                    currentPage.removeChild(lastChild);
                    titleMoved.push(lastChild);
                }

                // Create a new page
                currentPage = createNewPage();
                const newFooter = currentPage.querySelector(".resume-page-footer");

                // Put the orphaned title onto the new page first
                if (titleMoved.length > 0) {
                    titleMoved.forEach(titleEl => currentPage.insertBefore(titleEl, newFooter));
                }

                // Put the element onto the new page
                currentPage.insertBefore(block.element, newFooter);
            }
        });

        // 3. Update total page counts in page footers
        const totalPages = pageNum - 1;
        const pageFooters = resumePreview.querySelectorAll(".resume-page-footer");
        pageFooters.forEach((footer, idx) => {
            footer.textContent = `Page ${idx + 1} of ${totalPages}`;
        });
    }

    // Function to load resumeinfo.json (or a tailored resume via ?resume=)
    async function fetchResumeData(force = false) {
        try {
            let url = "/api/resume-builder/data?t=" + new Date().getTime();
            const resumePath = window.__resumeBuilderPath;
            if (resumePath) {
                url += "&resume=" + encodeURIComponent(resumePath);
            }
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error("HTTP error " + response.status);
            }
            const text = await response.text();

            // Check if contents actually changed
            if (text === lastFetchedJsonString && !force) {
                updateSyncIndicator(true, "Synced (No changes)");
                return;
            }

            // Attempt to parse
            const data = JSON.parse(text);

            lastFetchedJsonString = text;

            // Only update editor if user is not actively editing
            if (document.activeElement !== jsonEditor || force) {
                jsonEditor.value = JSON.stringify(data, null, 2);
            }

            renderResume(data, getLayoutOptions());
            updateStatus(true, "JSON loaded successfully");
            updateSyncIndicator(true, "Synced");
            updateTailoredBanner();
        } catch (err) {
            console.error("Error fetching/parsing JSON:", err);
            updateStatus(false, "Error loading/parsing JSON: " + err.message);
            updateSyncIndicator(false, "Sync failed");
        }
    }

    // Show/hide a banner when a tailored resume is loaded
    function updateTailoredBanner() {
        let banner = document.getElementById("tailored-banner");
        if (window.__resumeBuilderPath) {
            const filename = decodeURIComponent(window.__resumeBuilderPath).split("/").pop();
            if (!banner) {
                banner = document.createElement("div");
                banner.id = "tailored-banner";
                banner.style.cssText = "background:#fff3cd; border:1px solid #ffc107; border-radius:8px; padding:10px 14px; margin-bottom:12px; font-size:13px; color:#856404; display:flex; justify-content:space-between; align-items:center;";
                const previewPanel = document.querySelector(".preview-panel");
                if (previewPanel) {
                    const title = previewPanel.querySelector("h1");
                    title.parentNode.insertBefore(banner, title.nextSibling);
                }
            }
            banner.style.display = "flex";
            banner.innerHTML = '<span><strong>Tailored Resume:</strong> ' + escapeHTML(filename) + '</span><a href="/resume-builder" style="color:#533f03; font-weight:600;">View Master</a>';
        } else if (banner) {
            banner.style.display = "none";
        }
    }

    // Update the validation status label
    function updateStatus(isValid, message) {
        if (isValid) {
            jsonStatus.textContent = message || "Valid JSON";
            jsonStatus.style.color = "#28a745";
        } else {
            jsonStatus.textContent = message || "Invalid JSON";
            jsonStatus.style.color = "#dc3545";
        }
    }

    // Update sync green/red dot
    function updateSyncIndicator(success, labelText) {
        if (success) {
            syncIndicator.style.background = "#28a745";
            syncIndicator.title = labelText;
        } else {
            syncIndicator.style.background = "#dc3545";
            syncIndicator.title = labelText;
        }
    }

    // Set up polling interval
    function setupPolling() {
        if (pollInterval) clearInterval(pollInterval);
        if (autoSync.checked) {
            pollInterval = setInterval(() => {
                fetchResumeData(false);
            }, 2000);
            syncIndicator.style.opacity = "1";
        } else {
            syncIndicator.style.opacity = "0.4";
        }
    }

    function getLayoutOptions() {
        return {
            margin: parseFloat(marginSlider.value),
            lineSpacing: parseFloat(lineSpacingSlider.value),
            showCourses: includeCourses.checked,
            showProjects: includeProjects.checked,
            showReferences: includeReferences.checked
        };
    }

    function reRender() {
        try {
            const rawText = jsonEditor.value;
            const data = JSON.parse(rawText);
            renderResume(data, getLayoutOptions());
            updateStatus(true, "Rendered with layout options");
        } catch (err) {
            updateStatus(false, "JSON Error: " + err.message);
        }
    }

    // Update slider labels
    marginValue.textContent = marginSlider.value + " in";
    lineSpacingValue.textContent = lineSpacingSlider.value;

    function handleManualRender() {
        try {
            const rawText = jsonEditor.value;
            const data = JSON.parse(rawText);
            renderResume(data, getLayoutOptions());
            updateStatus(true, "Rendered manual changes successfully");
        } catch (err) {
            updateStatus(false, "JSON Error: " + err.message);
        }
    }

    // Event listeners
    renderBtn.addEventListener("click", handleManualRender);
    fetchBtn.addEventListener("click", () => fetchResumeData(true));
    autoSync.addEventListener("change", setupPolling);

    marginSlider.addEventListener("input", () => {
        marginValue.textContent = marginSlider.value + " in";
        reRender();
    });
    lineSpacingSlider.addEventListener("input", () => {
        lineSpacingValue.textContent = lineSpacingSlider.value;
        reRender();
    });
    includeCourses.addEventListener("change", reRender);
    includeProjects.addEventListener("change", reRender);
    includeReferences.addEventListener("change", reRender);

    // Live update preview on keyup in editor (if valid)
    jsonEditor.addEventListener("input", () => {
        try {
            const data = JSON.parse(jsonEditor.value);
            renderResume(data, getLayoutOptions());
            updateStatus(true, "JSON is valid (autoupdated preview)");
        } catch (err) {
            updateStatus(false, "Typing... Invalid JSON format: " + err.message);
        }
    });

    // Copy HTML button
    copyBtn.addEventListener("click", () => {
        const tempElement = document.createElement("textarea");
        tempElement.value = resumePreview.innerHTML;
        document.body.appendChild(tempElement);
        tempElement.select();
        document.execCommand("copy");
        document.body.removeChild(tempElement);

        const originalText = copyBtn.textContent;
        copyBtn.textContent = "Copied!";
        copyBtn.disabled = true;
        setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.disabled = false;
        }, 1500);
    });

    // Save to Server
    async function saveResumeData() {
        if (window.__resumeBuilderPath) {
            showToast("Cannot save: this is a tailored resume. Edit the master resumeinfo.json instead.", "warning");
            return;
        }
        try {
            const rawText = jsonEditor.value;
            JSON.parse(rawText); // validate
            saveBtn.disabled = true;
            saveBtn.textContent = "Saving...";
            const response = await fetch("/api/resume-builder/data", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: rawText,
            });
            if (!response.ok) throw new Error("HTTP error " + response.status);
            lastFetchedJsonString = rawText;
            updateStatus(true, "Saved to server");
            showToast("Resume data saved!", "success");
        } catch (err) {
            updateStatus(false, "Save failed: " + err.message);
            showToast("Save failed: " + err.message, "error");
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = "Save to Server";
        }
    }

    saveBtn.addEventListener("click", saveResumeData);

    // Download PDF (triggers browser print dialog optimized via CSS @media print)
    downloadBtn.addEventListener("click", () => {
        window.print();
    });

    // Initial load
    fetchResumeData(true);
    setupPolling();
});

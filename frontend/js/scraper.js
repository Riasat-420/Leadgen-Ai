/* scraper.js — Scraper controls, job monitoring, quick targets for all platforms */

let _activeJobId   = null;
let _pollInterval  = null;

// ── Platform icons (Lucide icon names) ────────────────────
const PLATFORM_ICONS = {
  google_maps: 'map-pin',
  upwork:      'briefcase',
  freelancer:  'code-2',
  linkedin:    'linkedin',
  fiverr:      'layers',
};

const PLATFORM_COLORS = {
  google_maps: 'var(--primary)',
  upwork:      'var(--green)',
  freelancer:  '#FF9119',
  linkedin:    'var(--cyan)',
  fiverr:      '#1DBF73',
};

// ── Load scraper view ─────────────────────────────────────
async function loadScraper() {
  loadQuickTargets();
  loadJobs();
}

async function loadQuickTargets() {
  const el = document.getElementById('quick-targets');

  try {
    const targets = await API.getTargets();

    // Group by platform
    const groups = {};
    for (const t of targets) {
      const p = t.platform || 'google_maps';
      if (!groups[p]) groups[p] = [];
      groups[p].push(t);
    }

    const platformLabels = {
      google_maps: 'Google Maps',
      upwork:      'Upwork',
      freelancer:  'Freelancer',
      linkedin:    'LinkedIn',
      fiverr:      'Fiverr',
    };

    let html = '';
    for (const [platform, items] of Object.entries(groups)) {
      const color = PLATFORM_COLORS[platform] || 'var(--text-2)';
      const icon  = PLATFORM_ICONS[platform] || 'search';
      html += `
        <div class="platform-group">
          <div class="platform-group-label" style="color:${color}">
            <i data-lucide="${icon}"></i>
            ${platformLabels[platform] || platform}
          </div>
          <div class="platform-targets">
            ${items.map(t => {
              const isGoogleMaps = platform === 'google_maps';
              const label = t.label || (isGoogleMaps ? `${t.category} — ${t.city}` : t.keyword);
              const onclickAttr = isGoogleMaps
                ? `onclick="fillScrapeForm('${esc(t.category)}','${esc(t.city)}','${esc(t.country || '')}')"`
                : `onclick="fillPlatformForm('${esc(platform)}','${esc(t.keyword || '')}')"`;
              return `
                <button class="quick-target-btn" ${onclickAttr}>
                  <i data-lucide="${icon}" style="color:${color};width:14px;height:14px;flex-shrink:0"></i>
                  <span style="font-size:12px;font-weight:500">${esc(label)}</span>
                </button>`;
            }).join('')}
          </div>
        </div>`;
    }

    el.innerHTML = html;
    if (window.lucide) lucide.createIcons();

  } catch {
    el.innerHTML = '<div class="empty-state" style="padding:8px">Could not load targets</div>';
  }
}

// ── Fill form helpers ─────────────────────────────────────
function fillScrapeForm(category, city, country) {
  document.getElementById('scrape-category').value = category;
  document.getElementById('scrape-city').value     = city;
  document.getElementById('scrape-country').value  = country;
  // Switch to Google Maps tab
  showScrapeTab('google_maps');
}

function fillPlatformForm(platform, keyword) {
  document.getElementById('platform-select').value  = platform;
  document.getElementById('platform-keyword').value = keyword;
  showScrapeTab('platform');
}

// ── Tab switching (Google Maps vs Platform) ───────────────
let _activeScrapeTab = 'google_maps';

function showScrapeTab(tab) {
  _activeScrapeTab = tab;
  const gmTab = document.getElementById('gm-tab');
  const plTab = document.getElementById('platform-tab');
  const gmForm = document.getElementById('gm-form');
  const plForm = document.getElementById('platform-form');

  if (!gmTab || !plTab) return;

  if (tab === 'google_maps') {
    gmTab.classList.add('active');
    plTab.classList.remove('active');
    gmForm.style.display = 'block';
    plForm.style.display = 'none';
  } else {
    plTab.classList.add('active');
    gmTab.classList.remove('active');
    plForm.style.display = 'block';
    gmForm.style.display = 'none';
  }
}

// ── Start Google Maps scrape ──────────────────────────────
async function startScrape() {
  const category   = document.getElementById('scrape-category').value.trim();
  const city       = document.getElementById('scrape-city').value.trim();
  const country    = document.getElementById('scrape-country').value.trim() || 'Unknown';
  const maxResults = parseInt(document.getElementById('scrape-max').value) || 30;

  if (!category || !city) {
    toast('Enter both category and city', 'warning');
    return;
  }

  const btn = document.getElementById('scrape-btn');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader"></i> Starting...';
  if (window.lucide) lucide.createIcons();

  try {
    const res = await API.startScrape({ category, city, country, max_results: maxResults });
    _activeJobId = res.job_id;
    toast(`Scrape started for "${category} in ${city}"`, 'success');
    showActiveJob(res.job_id, `${category} in ${city}`, 'google_maps');
    startPolling(res.job_id);
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="play"></i> Start Scraping';
    if (window.lucide) lucide.createIcons();
  }
}

// ── Start Platform scrape ─────────────────────────────────
async function startPlatformScrape() {
  const platform   = document.getElementById('platform-select').value;
  const keyword    = document.getElementById('platform-keyword').value.trim();
  const maxResults = parseInt(document.getElementById('platform-max').value) || 30;

  if (!keyword) {
    toast('Enter a keyword to search', 'warning');
    return;
  }

  const btn = document.getElementById('platform-scrape-btn');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader"></i> Starting...';
  if (window.lucide) lucide.createIcons();

  try {
    const res = await API.startPlatformScrape({ platform, keyword, max_results: maxResults });
    _activeJobId = res.job_id;
    toast(`${platform} scrape started for "${keyword}"`, 'success');
    showActiveJob(res.job_id, `[${platform}] ${keyword}`, platform);
    startPolling(res.job_id);
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="play"></i> Start Scraping';
    if (window.lucide) lucide.createIcons();
  }
}

// ── Active job UI ─────────────────────────────────────────
function showActiveJob(jobId, query, platform) {
  const card = document.getElementById('active-job-card');
  card.style.display = 'block';
  document.getElementById('job-details').textContent = `Job #${jobId} — "${query}"`;
  document.getElementById('job-status-badge').textContent = 'Running';
  document.getElementById('job-status-badge').className = 'job-status-badge running';
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('progress-pct').textContent = '0%';
  const platformLabels = {
    google_maps: 'Scanning Google Maps...',
    upwork:      'Scanning Upwork jobs...',
    freelancer:  'Scanning Freelancer projects...',
    linkedin:    'Scanning LinkedIn companies...',
    fiverr:      'Scanning Fiverr gigs...',
  };
  document.getElementById('progress-text').textContent = platformLabels[platform] || 'Scraping...';
  document.getElementById('job-found').textContent = '0';
  document.getElementById('job-scanned').textContent = '0';
}

function updateJobUI(job) {
  const pct = Math.round(job.progress || 0);
  document.getElementById('progress-bar').style.width = pct + '%';
  document.getElementById('progress-pct').textContent = pct + '%';
  document.getElementById('job-found').textContent = job.leads_found || 0;
  document.getElementById('job-scanned').textContent = job.leads_scraped || 0;

  const badge = document.getElementById('job-status-badge');
  badge.textContent = job.status.charAt(0).toUpperCase() + job.status.slice(1);
  badge.className = `job-status-badge ${job.status}`;

  if (job.status === 'completed') {
    document.getElementById('progress-text').textContent = `Complete — ${job.leads_found} new leads found`;
    document.getElementById('progress-bar').style.width = '100%';
    document.getElementById('progress-pct').textContent = '100%';
    toast(`Scrape complete — ${job.leads_found} new leads collected!`, 'success');
    stopPolling();
    loadJobs();
  } else if (job.status === 'failed') {
    document.getElementById('progress-text').textContent = `Failed: ${job.error_message || 'Unknown error'}`;
    toast('Scrape job failed', 'error');
    stopPolling();
    loadJobs();
  }
}

// ── Polling ───────────────────────────────────────────────
function startPolling(jobId) {
  stopPolling();
  _pollInterval = setInterval(async () => {
    try {
      const job = await API.scrapeStatus(jobId);
      updateJobUI(job);
    } catch (e) {
      console.error('Poll error:', e);
    }
  }, 3000);
}

function stopPolling() {
  if (_pollInterval) { clearInterval(_pollInterval); _pollInterval = null; }
}

// ── Job history table ─────────────────────────────────────
async function loadJobs() {
  const tbody = document.getElementById('jobs-tbody');
  try {
    const jobs = await API.getJobs();

    if (!jobs || jobs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No scrape jobs yet</td></tr>';
      return;
    }

    tbody.innerHTML = jobs.map(job => {
      const pct = Math.round(job.progress || 0);
      return `
        <tr style="cursor:pointer" onclick="resumeJobView(${job.id})">
          <td style="color:var(--text-3)">#${job.id}</td>
          <td>
            <div style="font-size:13px;font-weight:600;color:var(--text)">${esc(job.query)}</div>
            <div style="font-size:11px;color:var(--text-3)">${esc(job.city)}, ${esc(job.country || '')}</div>
          </td>
          <td>${jobStatusBadge(job.status)}</td>
          <td><strong style="color:var(--text)">${job.leads_found || 0}</strong> <span style="color:var(--text-3)">new</span></td>
          <td>
            <div style="display:flex;align-items:center;gap:8px">
              <div style="flex:1;height:4px;background:var(--surface-2);border-radius:2px;overflow:hidden">
                <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,var(--primary),var(--cyan));border-radius:2px"></div>
              </div>
              <span style="font-size:11px;color:var(--text-3)">${pct}%</span>
            </div>
          </td>
          <td style="font-size:12px;color:var(--text-3)">${timeAgo(job.started_at || job.created_at)}</td>
        </tr>`;
    }).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Error: ${esc(e.message)}</td></tr>`;
  }
}

function jobStatusBadge(status) {
  return `<span class="job-status-badge ${status}">${status}</span>`;
}

async function resumeJobView(jobId) {
  const job = await API.scrapeStatus(jobId);
  if (job.status === 'running') {
    showActiveJob(jobId, job.query, 'google_maps');
    startPolling(jobId);
    updateJobUI(job);
  } else {
    const card = document.getElementById('active-job-card');
    card.style.display = 'block';
    document.getElementById('job-details').textContent = `Job #${jobId} — "${job.query}"`;
    updateJobUI(job);
  }
}

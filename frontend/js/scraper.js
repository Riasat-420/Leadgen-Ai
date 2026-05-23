/* scraper.js — Scraper controls, job monitoring, quick targets */

let _activeJobId   = null;
let _pollInterval  = null;

// ── Load scraper view ─────────────────────────────────────
async function loadScraper() {
  loadQuickTargets();
  loadJobs();
}

async function loadQuickTargets() {
  const el = document.getElementById('quick-targets');
  const icons = { 'real estate agency': '🏢', 'cafe': '☕', 'restaurant': '🍽️' };

  try {
    const targets = await API.getTargets();
    el.innerHTML = targets.map(t => {
      const icon = icons[t.category] || '📍';
      return `
        <button class="quick-target-btn" onclick="fillScrapeForm('${esc(t.category)}','${esc(t.city)}','${esc(t.country)}')">
          <span class="quick-target-icon">${icon}</span>
          <div>
            <div style="font-weight:600">${esc(t.category)}</div>
            <div style="font-size:11px;color:var(--text-3)">${esc(t.city)}, ${esc(t.country)}</div>
          </div>
        </button>`;
    }).join('');
  } catch {
    el.innerHTML = '<div class="empty-state" style="padding:8px">Could not load targets</div>';
  }
}

function fillScrapeForm(category, city, country) {
  document.getElementById('scrape-category').value = category;
  document.getElementById('scrape-city').value     = city;
  document.getElementById('scrape-country').value  = country;
}

// ── Start scrape job ──────────────────────────────────────
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
  btn.textContent = '⏳ Starting...';

  try {
    const res = await API.startScrape({ category, city, country, max_results: maxResults });
    _activeJobId = res.job_id;
    toast(`Scrape job started for "${category} in ${city}"`, 'success');
    showActiveJob(res.job_id, `${category} in ${city}`);
    startPolling(res.job_id);
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 Start Scraping';
  }
}

// ── Active job UI ─────────────────────────────────────────
function showActiveJob(jobId, query) {
  const card = document.getElementById('active-job-card');
  card.style.display = 'block';
  document.getElementById('job-details').textContent = `Job #${jobId} — "${query}"`;
  document.getElementById('job-status-badge').textContent = 'Running';
  document.getElementById('job-status-badge').className = 'job-status-badge running';
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('progress-pct').textContent = '0%';
  document.getElementById('progress-text').textContent = 'Scraping Google Maps...';
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
    document.getElementById('progress-text').textContent = `✅ Complete! ${job.leads_found} new leads found`;
    document.getElementById('progress-bar').style.width = '100%';
    document.getElementById('progress-pct').textContent = '100%';
    toast(`Scrape complete — ${job.leads_found} new leads collected! 🎉`, 'success');
    stopPolling();
    loadJobs();
  } else if (job.status === 'failed') {
    document.getElementById('progress-text').textContent = `❌ Failed: ${job.error_message || 'Unknown error'}`;
    toast('Scrape job failed — check console', 'error');
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
    showActiveJob(jobId, job.query);
    startPolling(jobId);
    updateJobUI(job);
  } else {
    const card = document.getElementById('active-job-card');
    card.style.display = 'block';
    document.getElementById('job-details').textContent = `Job #${jobId} — "${job.query}"`;
    updateJobUI(job);
  }
}

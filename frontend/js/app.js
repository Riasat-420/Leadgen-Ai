/* app.js — Navigation, utilities, global init */

// ── State ────────────────────────────────────────────────
let currentView = 'dashboard';
let _currentLeadId = null; // for email modal

// ── Navigation ────────────────────────────────────────────
function showView(name) {
  // Deactivate all
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Activate target
  const view = document.getElementById(`view-${name}`);
  const nav  = document.getElementById(`nav-${name}`);
  if (view) view.classList.add('active');
  if (nav)  nav.classList.add('active');

  currentView = name;

  // Update topbar
  const titles = {
    dashboard: ['Dashboard',  'Overview of your lead pipeline'],
    leads:     ['Leads',      'All collected business leads'],
    scraper:   ['Scraper',    'Launch Google Maps scraping jobs'],
    outreach:  ['Outreach',   'Send emails and track replies'],
    inbox:     ['Outreach Inbox', 'Read replies, track dialogues, and chat with leads in real-time'],
    analytics: ['Analytics',  'Performance charts and insights'],
    'api-docs':['API Docs',   'Interactive and beautiful API Reference Documentation'],
    settings:  ['System Settings', 'Configure your custom SMTP server and IMAP reply-sync credentials'],
  };

  const [title, sub] = titles[name] || ['—', ''];
  document.getElementById('page-title').textContent = title;
  document.getElementById('page-sub').textContent   = sub;

  // Load view data
  switch (name) {
    case 'dashboard': loadDashboard(); break;
    case 'leads':     loadLeads(1);    break;
    case 'scraper':   loadScraper();   break;
    case 'outreach':  loadOutreach();  break;
    case 'inbox':     loadInbox();     break;
    case 'analytics': loadAnalytics(); break;
    case 'settings':  loadSettings();  break;
  }
}



// ── Toast Notifications ───────────────────────────────────
function toast(message, type = 'info', duration = 3500) {
  const icons = { success: '✓', error: '✗', info: 'ℹ', warning: '⚠' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="toast-icon-wrap">${icons[type]}</span><span>${message}</span>`;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => {
    el.style.animation = 'slideInRight 0.3s reverse ease';
    setTimeout(() => el.remove(), 300);
  }, duration);
}

// ── Score helpers ─────────────────────────────────────────
function scoreClass(score) {
  if (!score) return 'cold';
  if (score >= 7) return 'hot';
  if (score >= 5) return 'warm';
  if (score >= 3) return 'cool';
  return 'cold';
}

function scoreBadge(score) {
  if (!score && score !== 0) return '<span class="score-badge cold">—</span>';
  const cls = scoreClass(score);
  return `<span class="score-badge ${cls}">${score.toFixed(1)}</span>`;
}

function scoreCircle(score) {
  const cls = scoreClass(score);
  const display = score ? score.toFixed(1) : '—';
  return `<div class="score-circle ${cls}" id="modal-score">${display}</div>`;
}

// ── Status badge ──────────────────────────────────────────
function statusBadge(status) {
  const labels = {
    new: 'New', analyzed: 'Analyzed', analyzing: 'Analyzing...',
    message_ready: 'Msg Ready', contacted: 'Contacted',
    replied: 'Replied', interested: 'Interested',
    closed: 'Closed', not_interested: 'Not Interested',
    follow_up_complete: 'Done', failed: 'Failed',
  };
  const label = labels[status] || status;
  return `<span class="status-badge status-${status}">${label}</span>`;
}

// ── Website link ──────────────────────────────────────────
function websiteLink(url) {
  if (!url) return '<span style="color:var(--text-3)">None</span>';
  const domain = url.replace(/^https?:\/\//, '').split('/')[0];
  return `<a href="${url}" target="_blank" style="color:var(--primary);font-size:11px">${domain}</a>`;
}

// ── Health indicator ──────────────────────────────────────
function healthDot(val, label) {
  const cls = val === null || val === undefined ? 'na' : (val ? 'ok' : 'bad');
  const icon = val === null || val === undefined ? '—' : (val ? '✓' : '✗');
  return `<div class="health-item">
    <div class="health-dot ${cls}"></div>
    <span class="health-label">${label}: <strong>${icon}</strong></span>
  </div>`;
}

// ── Avatar Letter ─────────────────────────────────────────
function avatarLetter(name) {
  return name ? name.charAt(0).toUpperCase() : '?';
}

// ── Time format ───────────────────────────────────────────
function timeAgo(iso) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso + 'Z').getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso + 'Z').toLocaleString();
}

// ── Dashboard ─────────────────────────────────────────────
async function loadDashboard() {
  try {
    const data = await API.getDashboardStats();
    const { leads, outreach, top_leads, recent_leads, by_city, score_distribution } = data;

    // Stats
    animateNumber('stat-total',     leads.total);
    animateNumber('stat-hot',       leads.hot);
    animateNumber('stat-contacted', leads.contacted);
    animateNumber('stat-replied',   leads.replied);
    document.getElementById('stat-conversion').textContent = outreach.conversion_rate + '%';
    animateNumber('stat-closed',    leads.closed);

    // Badge
    document.getElementById('badge-leads').textContent = leads.total;

    // Quota
    const sentPct = Math.min((outreach.emails_today / outreach.daily_limit) * 100, 100);
    document.getElementById('quota-text').textContent =
      `${outreach.emails_today} / ${outreach.daily_limit} emails today`;
    document.getElementById('quota-fill').style.width = sentPct + '%';
    document.getElementById('quota-text-2') && (document.getElementById('quota-text-2').textContent = outreach.emails_today);

    // Top leads
    const topEl = document.getElementById('top-leads-list');
    topEl.innerHTML = top_leads.length === 0
      ? '<div class="empty-state">No analyzed leads yet</div>'
      : top_leads.map(l => `
        <div class="lead-list-item" onclick="openLeadModal(${l.id})">
          <div class="lead-avatar" style="background:var(--primary-dim);color:var(--primary)">${avatarLetter(l.business_name)}</div>
          <div class="lead-list-info">
            <div class="lead-list-name">${esc(l.business_name)}</div>
            <div class="lead-list-meta">${esc(l.category || '')} · ${esc(l.city || '')}</div>
          </div>
          ${scoreBadge(l.lead_score)}
          ${statusBadge(l.status)}
        </div>`).join('');

    // Recent
    const recEl = document.getElementById('recent-leads-list');
    recEl.innerHTML = recent_leads.length === 0
      ? '<div class="empty-state">No leads yet — run the scraper!</div>'
      : recent_leads.map(l => `
        <div class="lead-list-item" onclick="openLeadModal(${l.id})">
          <div class="lead-avatar">${avatarLetter(l.business_name)}</div>
          <div class="lead-list-info">
            <div class="lead-list-name">${esc(l.business_name)}</div>
            <div class="lead-list-meta">${esc(l.city || '')} · ${timeAgo(l.created_at)}</div>
          </div>
          ${statusBadge(l.status)}
        </div>`).join('');

    // Pipeline bars
    const totalForPct = leads.total || 1;
    const stages = [
      { label: 'New',         count: leads.new,       color: '#475569' },
      { label: 'Analyzed',    count: leads.analyzed,  color: '#3b82f6' },
      { label: 'Contacted',   count: leads.contacted, color: '#f59e0b' },
      { label: 'Replied',     count: leads.replied,   color: '#10b981' },
      { label: 'Interested',  count: leads.interested,color: '#06b6d4' },
      { label: 'Closed',      count: leads.closed,    color: '#ec4899' },
    ];

    document.getElementById('pipeline-bars').innerHTML = stages.map(s => `
      <div class="pipeline-row">
        <span class="pipeline-label">${s.label}</span>
        <div class="pipeline-track">
          <div class="pipeline-fill" style="width:${(s.count/totalForPct*100).toFixed(1)}%;background:${s.color}"></div>
        </div>
        <span class="pipeline-count">${s.count}</span>
      </div>`).join('');

  } catch (e) {
    console.error('Dashboard error:', e);
    toast('Could not load dashboard — is the server running?', 'error');
    document.getElementById('connection-status').innerHTML =
      '<span class="status-dot offline"></span><span>API Offline</span>';
  }
}

// ── Animate counter ───────────────────────────────────────
function animateNumber(elId, target) {
  const el = document.getElementById(elId);
  if (!el || isNaN(target)) { if (el) el.textContent = target ?? '—'; return; }
  let start = 0;
  const step = Math.ceil(target / 20);
  const timer = setInterval(() => {
    start += step;
    if (start >= target) { el.textContent = target; clearInterval(timer); }
    else el.textContent = start;
  }, 30);
}

// ── Escape HTML ───────────────────────────────────────────
function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Lead Modal ────────────────────────────────────────────
async function openLeadModal(id) {
  _currentLeadId = id;
  document.getElementById('lead-modal-overlay').classList.add('open');
  document.getElementById('modal-body').innerHTML = '<div class="empty-state">Loading...</div>';

  try {
    const lead = await API.getLead(id);
    renderLeadModal(lead);
  } catch (e) {
    toast('Could not load lead', 'error');
  }
}

function closeLeadModal() {
  document.getElementById('lead-modal-overlay').classList.remove('open');
  _currentLeadId = null;
}

function renderLeadModal(lead) {
  document.getElementById('modal-lead-name').textContent = lead.business_name;
  document.getElementById('modal-lead-sub').textContent =
    `${lead.category || ''} · ${lead.city || ''}, ${lead.country || ''}`;
  document.getElementById('modal-header-right') &&
    document.getElementById('modal-score').outerHTML === '' || null;

  const scoreEl = document.getElementById('modal-score');
  if (scoreEl) {
    const sc = scoreClass(lead.lead_score);
    scoreEl.className = `score-circle ${sc}`;
    scoreEl.textContent = lead.lead_score ? lead.lead_score.toFixed(1) : '—';
  }

  // Action buttons
  document.getElementById('modal-analyze-btn').onclick = async () => {
    try {
      toast('Analysis started...', 'info');
      await API.analyzeLead(lead.id);
      toast('Analyzing in background — refresh in ~30s', 'success');
    } catch (e) { toast(e.message, 'error'); }
  };

  document.getElementById('modal-generate-btn').onclick = async () => {
    try {
      toast('Generating messages...', 'info');
      await API.generateMessages(lead.id);
      toast('Messages generating — refresh in ~15s', 'success');
    } catch (e) { toast(e.message, 'error'); }
  };

  document.getElementById('modal-send-btn').onclick = () => {
    openEmailModal(lead);
  };

  // Body
  document.getElementById('modal-body').innerHTML = `
    <!-- Info -->
    <div class="modal-section">
      <div class="modal-section-title">Business Info</div>
      <div class="modal-grid">
        <div class="modal-field">
          <div class="modal-field-label">Phone</div>
          <div class="modal-field-value">${esc(lead.phone) || '—'}</div>
        </div>
        <div class="modal-field">
          <div class="modal-field-label">Email</div>
          <div class="modal-field-value">${esc(lead.email) || '—'}</div>
        </div>
        <div class="modal-field">
          <div class="modal-field-label">Address</div>
          <div class="modal-field-value">${esc(lead.address) || '—'}</div>
        </div>
        <div class="modal-field">
          <div class="modal-field-label">Rating</div>
          <div class="modal-field-value">${lead.google_rating ? `<i data-lucide="star" style="width:14px;height:14px;display:inline-block;fill:var(--amber);stroke:var(--amber);vertical-align:middle;margin-right:2px"></i> ${lead.google_rating} (${lead.review_count || 0} reviews)` : '—'}</div>
        </div>
        <div class="modal-field">
          <div class="modal-field-label">Website</div>
          <div class="modal-field-value">${websiteLink(lead.website)}</div>
        </div>
        <div class="modal-field">
          <div class="modal-field-label">Status</div>
          <div class="modal-field-value">${statusBadge(lead.status)}</div>
        </div>
      </div>
    </div>

    <!-- Website Health -->
    ${lead.has_website ? `
    <div class="modal-section">
      <div class="modal-section-title">Website Health · SEO ${lead.seo_score || 0}/100</div>
      <div class="health-grid">
        ${healthDot(lead.has_ssl, 'SSL')}
        ${healthDot(lead.mobile_friendly, 'Mobile')}
        ${healthDot(lead.website_loads, 'Loads')}
        ${healthDot(lead.has_whatsapp, 'WhatsApp')}
        ${healthDot(lead.has_contact_form, 'Contact Form')}
        ${healthDot(lead.has_google_analytics, 'Analytics')}
      </div>
      ${lead.load_time_ms ? `<div style="margin-top:10px;font-size:12px;color:var(--text-3)">Load Time: <strong style="color:${lead.load_time_ms > 3000 ? 'var(--red)' : 'var(--green)'}">${lead.load_time_ms}ms</strong></div>` : ''}
    </div>` : ''}

    <!-- Notes / Description -->
    ${lead.notes ? `
    <div class="modal-section">
      <div class="modal-section-title">${lead.source !== 'google_maps' ? 'Posting Details & Description' : 'Notes'}</div>
      <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:16px;font-size:13px;color:var(--text);white-space:pre-wrap;line-height:1.6;font-family:inherit">${esc(lead.notes)}</div>
    </div>` : ''}

    <!-- AI Analysis -->
    ${lead.issues_found && lead.issues_found.length > 0 ? `
    <div class="modal-section">
      <div class="modal-section-title">AI Analysis · Score: ${lead.lead_score || 0}/10</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <div style="font-size:12px;font-weight:600;color:var(--red);margin-bottom:8px">Issues Found</div>
          <div class="issues-list">
            ${(lead.issues_found || []).map(i => `<div class="issue-item">${esc(i)}</div>`).join('')}
          </div>
        </div>
        <div>
          <div style="font-size:12px;font-weight:600;color:var(--green);margin-bottom:8px">Opportunities</div>
          <div class="opps-list">
            ${(lead.opportunities || []).map(o => `<div class="opp-item">${esc(o)}</div>`).join('')}
          </div>
        </div>
      </div>
      ${lead.pitch_angle ? `<div style="margin-top:14px;padding:12px;background:var(--primary-dim);border-radius:8px;font-size:13px;color:var(--primary)"><i data-lucide="lightbulb" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:4px"></i> <strong>Pitch:</strong> ${esc(lead.pitch_angle)}</div>` : ''}
    </div>` : '<div class="modal-section"><div class="empty-state" style="padding:16px">No AI analysis yet — click Analyze</div></div>'}

    <!-- Messages -->
    ${lead.cold_email_body ? `
    <div class="modal-section">
      <div class="modal-section-title">Generated Messages</div>
      <div class="msg-tabs">
        <button class="msg-tab active" onclick="switchTab(this,'tab-email')"><i data-lucide="mail" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> Cold Email</button>
        <button class="msg-tab" onclick="switchTab(this,'tab-whatsapp')"><i data-lucide="message-square" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> WhatsApp</button>
        <button class="msg-tab" onclick="switchTab(this,'tab-follow1')"><i data-lucide="refresh-cw" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> Follow-up 1</button>
        <button class="msg-tab" onclick="switchTab(this,'tab-follow2')"><i data-lucide="refresh-cw" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> Follow-up 2</button>
      </div>
      <div class="msg-panel active" id="tab-email">
        <div style="font-size:12px;color:var(--text-3);margin-bottom:6px">Subject: <strong style="color:var(--text)">${esc(lead.cold_email_subject)}</strong></div>
        <div class="msg-content">${esc(lead.cold_email_body)}</div>
      </div>
      <div class="msg-panel" id="tab-whatsapp">
        <div class="msg-content">${esc(lead.whatsapp_message || '—')}</div>
      </div>
      <div class="msg-panel" id="tab-follow1">
        <div class="msg-content">${esc(lead.followup_1 || '—')}</div>
      </div>
      <div class="msg-panel" id="tab-follow2">
        <div class="msg-content">${esc(lead.followup_2 || '—')}</div>
      </div>
    </div>` : '<div class="modal-section"><div class="empty-state" style="padding:16px">No messages yet — click Generate Messages</div></div>'}

    <!-- Email history -->
    ${lead.outreach_logs && lead.outreach_logs.length > 0 ? `
    <div class="modal-section">
      <div class="modal-section-title">Outreach History (${lead.emails_sent || 0} emails sent)</div>
      ${lead.outreach_logs.map(l => `
        <div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:12px;color:var(--text-2)">
          ${l.message_type} · Follow-up #${l.follow_up_number} ·
          <span style="color:var(--text-3)">${formatDate(l.sent_at)}</span> ·
          ${statusBadge(l.status)}
        </div>`).join('')}
    </div>` : ''}

    <!-- Notes / Status -->
    <div class="modal-section">
      <div class="modal-section-title">Update Status</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        ${['interested','not_interested','closed','replied'].map(s =>
          `<button class="btn btn-sm btn-secondary" onclick="updateLeadStatus(${lead.id},'${s}')">${s.replace('_',' ')}</button>`
        ).join('')}
      </div>
    </div>
  `;
  if (window.lucide) lucide.createIcons();
}

function switchTab(btn, tabId) {
  btn.closest('.modal-section').querySelectorAll('.msg-tab').forEach(t => t.classList.remove('active'));
  btn.closest('.modal-section').querySelectorAll('.msg-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(tabId).classList.add('active');
}

async function updateLeadStatus(id, status) {
  try {
    await API.updateLead(id, { status });
    toast(`Status updated to ${status}`, 'success');
    closeLeadModal();
    if (currentView === 'leads') loadLeads(1);
  } catch (e) { toast(e.message, 'error'); }
}

// ── Email Modal ───────────────────────────────────────────
function openEmailModal(lead) {
  _currentLeadId = lead.id;
  document.getElementById('email-to').value = lead.email || '';
  document.getElementById('email-subject').value = lead.cold_email_subject || `Quick question about ${lead.business_name}`;
  document.getElementById('email-body').value = lead.cold_email_body || '';
  document.getElementById('email-modal-overlay').classList.add('open');
}

function closeEmailModal() {
  document.getElementById('email-modal-overlay').classList.remove('open');
}

async function sendEmailConfirm() {
  const to      = document.getElementById('email-to').value.trim();
  const subject = document.getElementById('email-subject').value.trim();
  const body    = document.getElementById('email-body').value.trim();

  if (!to) { toast('Enter a recipient email', 'warning'); return; }
  if (!body) { toast('Message body is empty', 'warning'); return; }

  try {
    const res = await API.sendEmail({
      lead_id: _currentLeadId,
      to_email: to,
      subject,
      body,
      follow_up_number: 0,
    });

    if (res.success) {
      toast('Email sent successfully!', 'success');
      closeEmailModal();
      closeLeadModal();
    } else {
      toast('Email failed — check Gmail credentials in .env', 'error');
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

// ── Analytics Chart Loader ────────────────────────────────
let _charts = {};

async function loadAnalytics() {
  try {
    const data = await API.getDashboardStats();
    renderCharts(data);
  } catch (e) {
    toast('Could not load analytics', 'error');
  }
}

function renderCharts(data) {
  const chartDefaults = {
    responsive: true,
    plugins: {
      legend: {
        labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } }
      }
    },
    scales: {
      x: { ticks: { color: '#475569' }, grid: { color: 'rgba(255,255,255,0.04)' } },
      y: { ticks: { color: '#475569' }, grid: { color: 'rgba(255,255,255,0.04)' } },
    }
  };

  // Destroy old charts
  Object.values(_charts).forEach(c => c.destroy());
  _charts = {};

  // Score distribution
  const sd = data.score_distribution;
  _charts.score = new Chart(document.getElementById('chart-score'), {
    type: 'bar',
    data: {
      labels: ['0–3 (Cold)', '3–5 (Cool)', '5–7 (Warm)', '7–10 (Hot)'],
      datasets: [{
        label: 'Leads',
        data: [sd['0-3'], sd['3-5'], sd['5-7'], sd['7-10']],
        backgroundColor: ['#475569', '#3b82f6', '#f59e0b', '#ef4444'],
        borderRadius: 6,
      }]
    },
    options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: false } } }
  });

  // Status breakdown donut
  const l = data.leads;
  _charts.status = new Chart(document.getElementById('chart-status'), {
    type: 'doughnut',
    data: {
      labels: ['New', 'Analyzed', 'Contacted', 'Replied', 'Interested', 'Closed'],
      datasets: [{
        data: [l.new, l.analyzed, l.contacted, l.replied, l.interested, l.closed],
        backgroundColor: ['#475569', '#3b82f6', '#f59e0b', '#10b981', '#06b6d4', '#ec4899'],
        borderColor: 'transparent',
        borderWidth: 0,
      }]
    },
    options: {
      responsive: true,
      cutout: '65%',
      plugins: {
        legend: { position: 'right', labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } }
      }
    }
  });

  // By city
  const cities = data.by_city || [];
  _charts.city = new Chart(document.getElementById('chart-city'), {
    type: 'bar',
    data: {
      labels: cities.map(c => c.city || 'Unknown'),
      datasets: [{
        label: 'Leads',
        data: cities.map(c => c.count),
        backgroundColor: '#6366f1',
        borderRadius: 6,
      }]
    },
    options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: false } } }
  });

  // Outreach funnel
  const o = data.outreach;
  _charts.funnel = new Chart(document.getElementById('chart-funnel'), {
    type: 'bar',
    data: {
      labels: ['Total Leads', 'Contacted', 'Replied', 'Interested'],
      datasets: [{
        label: 'Count',
        data: [l.total, l.contacted, l.replied, l.interested],
        backgroundColor: ['#6366f1', '#f59e0b', '#10b981', '#06b6d4'],
        borderRadius: 6,
      }]
    },
    options: { ...chartDefaults, indexAxis: 'y', plugins: { ...chartDefaults.plugins, legend: { display: false } } }
  });
}

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Wire nav clicks
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      showView(item.dataset.view);
    });
  });

  showView('dashboard');

  // Check API health
  fetch('/api/health')
    .then(r => {
      if (r.ok) {
        document.getElementById('connection-status').innerHTML =
          '<span class="status-dot online"></span><span>API Connected</span>';
      }
    })
    .catch(() => {
      document.getElementById('connection-status').innerHTML =
        '<span class="status-dot offline"></span><span>API Offline</span>';
    });

  // Auto-refresh dashboard every 30s when on dashboard view
  setInterval(() => {
    if (currentView === 'dashboard') loadDashboard();
  }, 30000);
});

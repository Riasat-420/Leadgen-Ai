/* leads.js — Leads table, filtering, pagination, bulk actions, and real-time polling engine */

let _leadsPage     = 1;
let _leadsTotal    = 0;
let _leadsPageSize = 20;

// ── Real-Time Polling Engine ────────────────────────────────
const _activeLeadPollers = new Map();

function startPollingLead(leadId) {
  if (_activeLeadPollers.has(leadId)) return;

  const interval = setInterval(async () => {
    try {
      const lead = await API.getLead(leadId);
      
      // If status has finished transitioning away from background tasks
      if (lead.status !== 'analyzing' && lead.status !== 'generating') {
        clearInterval(interval);
        _activeLeadPollers.delete(leadId);
        
        // Refresh leads list to show the updated status, score, etc.
        loadLeads(_leadsPage);
        
        // Also refresh dashboard stats if currently viewing dashboard
        if (typeof currentView !== 'undefined' && currentView === 'dashboard') {
          loadDashboard();
        }
        
        // Also, if the lead detail modal is currently open for THIS lead, re-render it to show the fresh analysis!
        if (typeof _currentLeadId !== 'undefined' && _currentLeadId === leadId) {
          openLeadModal(leadId, true); // skip spinner
        }
        
        toast(`Lead "${lead.business_name}" update completed!`, 'success');
      }
    } catch (e) {
      console.error(`Error polling lead #${leadId}:`, e);
      clearInterval(interval);
      _activeLeadPollers.delete(leadId);
    }
  }, 2500);
  
  _activeLeadPollers.set(leadId, interval);
}

// ── Load Leads ──────────────────────────────────────────────
async function loadLeads(page = 1) {
  _leadsPage = page;

  const params = {
    page,
    page_size: _leadsPageSize,
    status:    document.getElementById('filter-status')?.value || '',
    city:      document.getElementById('filter-city')?.value   || '',
    min_score: document.getElementById('filter-score')?.value  || '',
    search:    document.getElementById('lead-search')?.value   || '',
    source:    document.getElementById('filter-source')?.value   || '',
  };

  const tbody = document.getElementById('leads-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Loading...</td></tr>';

  try {
    const data = await API.getLeads(params);
    _leadsTotal = data.total;

    document.getElementById('leads-count').textContent = data.total;
    document.getElementById('badge-leads').textContent = data.total;

    if (!data.leads || data.leads.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" class="empty-state">
        No leads found. Run the scraper to collect some!
      </td></tr>`;
      document.getElementById('leads-pagination').innerHTML = '';
      return;
    }

    tbody.innerHTML = data.leads.map(lead => `
      <tr>
        <td><input type="checkbox" class="lead-cb" value="${lead.id}" onchange="onCheckboxChange()" /></td>
        <td>
          <div style="display:flex;align-items:center;gap:10px">
            <div class="lead-avatar" style="width:30px;height:30px;font-size:12px">${avatarLetter(lead.business_name)}</div>
            <div>
              <div style="font-size:13px;font-weight:600;color:var(--text);cursor:pointer"
                   onclick="openLeadModal(${lead.id})">${esc(lead.business_name)}</div>
              <div style="font-size:11px;color:var(--text-3)">${esc(lead.phone || '')}</div>
            </div>
          </div>
        </td>
        <td>${esc(lead.city || '—')}</td>
        <td><span style="font-size:11px;color:var(--text-3)">${esc(lead.category || '—')}</span></td>
        <td><span style="font-size:12px;font-weight:500;color:var(--primary);word-break:break-all">${esc(lead.email || '—')}</span></td>
        <td>${scoreBadge(lead.lead_score)}</td>
        <td>
          ${lead.google_rating
            ? `<i data-lucide="star" style="width:14px;height:14px;display:inline-block;fill:var(--amber);stroke:var(--amber);vertical-align:middle;margin-right:2px"></i> <span style="font-size:12px">${lead.google_rating}</span>`
            : '<span style="color:var(--text-3)">—</span>'}
        </td>
        <td>${websiteLink(lead.website)}</td>
        <td>${statusBadge(lead.status)}</td>
        <td>
          <div class="action-group">
            <button class="btn-icon" title="View Details" onclick="openLeadModal(${lead.id})"><i data-lucide="eye" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i></button>
            
            ${lead.status === 'analyzing'
              ? `<button class="btn-icon" title="Analyzing..." disabled><i data-lucide="loader" style="width:14px;height:14px;display:inline-block;vertical-align:middle;animation:spin 1.5s infinite linear"></i></button>`
              : `<button class="btn-icon" title="Analyze" onclick="analyzeLeadInline(${lead.id}, this)"><i data-lucide="cpu" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i></button>`
            }
            
            ${lead.status === 'generating'
              ? `<button class="btn-icon" title="Generating messages..." disabled><i data-lucide="loader" style="width:14px;height:14px;display:inline-block;vertical-align:middle;animation:spin 1.5s infinite linear"></i></button>`
              : `<button class="btn-icon" title="Generate Messages" onclick="generateMessagesInline(${lead.id}, this)"><i data-lucide="pencil-line" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i></button>`
            }
            
            <button class="btn-icon" title="Send Email" onclick="openEmailForLead(${lead.id})"><i data-lucide="mail" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i></button>
            <button class="btn-icon" title="Delete" onclick="deleteLeadInline(${lead.id}, this)" style="color:var(--red)"><i data-lucide="trash-2" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i></button>
          </div>
        </td>
      </tr>
    `).join('');

    // Pagination
    renderPagination(data.pages, page);

    if (window.lucide) lucide.createIcons();

    // Automatically resume pollers for any loaded leads in background state (e.g., page load/reload)
    data.leads.forEach(lead => {
      if (lead.status === 'analyzing' || lead.status === 'generating') {
        startPollingLead(lead.id);
      }
    });

  } catch (e) {
    console.error('Load leads error:', e);
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state" style="color:var(--red)">Error loading leads: ${esc(e.message)}</td></tr>`;
  }
}

function renderPagination(totalPages, current) {
  const el = document.getElementById('leads-pagination');
  if (totalPages <= 1) { el.innerHTML = ''; return; }

  const pages = [];
  const start = Math.max(1, current - 2);
  const end   = Math.min(totalPages, current + 2);

  if (start > 1) pages.push({ n: 1, label: '1' });
  if (start > 2) pages.push({ n: null, label: '…' });
  for (let i = start; i <= end; i++) pages.push({ n: i, label: String(i) });
  if (end < totalPages - 1) pages.push({ n: null, label: '…' });
  if (end < totalPages) pages.push({ n: totalPages, label: String(totalPages) });

  el.innerHTML = pages.map(p =>
    p.n === null
      ? `<span class="page-btn" style="cursor:default">…</span>`
      : `<button class="page-btn ${p.n === current ? 'active' : ''}"
               onclick="loadLeads(${p.n})">${p.label}</button>`
  ).join('');
}

// Inline actions
async function analyzeLeadInline(id, btn) {
  btn.innerHTML = '<i data-lucide="loader" style="width:14px;height:14px;display:inline-block;vertical-align:middle;animation:spin 1.5s infinite linear"></i>';
  if (window.lucide) lucide.createIcons();
  btn.disabled = true;
  try {
    await API.analyzeLead(id);
    toast(`Analysis started for lead #${id}`, 'info');
    startPollingLead(id);
  } catch (e) {
    toast(e.message, 'error');
    loadLeads(_leadsPage);
  }
}

async function generateMessagesInline(id, btn) {
  btn.innerHTML = '<i data-lucide="loader" style="width:14px;height:14px;display:inline-block;vertical-align:middle;animation:spin 1.5s infinite linear"></i>';
  if (window.lucide) lucide.createIcons();
  btn.disabled = true;
  try {
    await API.generateMessages(id);
    toast(`Message generation started for lead #${id}`, 'info');
    startPollingLead(id);
  } catch (e) {
    toast(e.message, 'error');
    loadLeads(_leadsPage);
  }
}

async function openEmailForLead(id) {
  try {
    const lead = await API.getLead(id);
    openEmailModal(lead);
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteLeadInline(id, btn) {
  if (!confirm('Delete this lead permanently?')) return;
  try {
    await API.deleteLead(id);
    toast('Lead deleted', 'success');
    loadLeads(_leadsPage);
  } catch (e) { toast(e.message, 'error'); }
}

// Checkboxes / bulk
function onCheckboxChange() {
  const checked = document.querySelectorAll('.lead-cb:checked');
  const bulkBar = document.getElementById('bulk-actions');
  bulkBar.style.display = checked.length > 0 ? 'flex' : 'none';
}

document.getElementById('select-all')?.addEventListener('change', e => {
  document.querySelectorAll('.lead-cb').forEach(cb => cb.checked = e.target.checked);
  onCheckboxChange();
});

async function bulkAnalyze() {
  const ids = [...document.querySelectorAll('.lead-cb:checked')].map(cb => Number(cb.value));
  if (!ids.length) return;

  toast(`Starting analysis for ${ids.length} leads...`, 'info');
  let done = 0;
  for (const id of ids) {
    try {
      await API.analyzeLead(id);
      startPollingLead(id);
      done++;
    } catch {}
    await new Promise(r => setTimeout(r, 200));
  }
  toast(`Started AI analysis for ${done} leads. Progress is being monitored in real-time!`, 'success');
}

async function bulkGenerate() {
  const ids = [...document.querySelectorAll('.lead-cb:checked')].map(cb => Number(cb.value));
  if (!ids.length) return;

  toast(`Generating messages for ${ids.length} leads...`, 'info');
  let done = 0;
  for (const id of ids) {
    try {
      await API.generateMessages(id);
      startPollingLead(id);
      done++;
    } catch {}
    await new Promise(r => setTimeout(r, 200));
  }
  toast(`Started draft generation for ${done} leads. Progress is being monitored in real-time!`, 'success');
}

async function bulkDelete() {
  const ids = [...document.querySelectorAll('.lead-cb:checked')].map(cb => Number(cb.value));
  if (!ids.length) return;

  if (!confirm(`Are you sure you want to permanently delete the ${ids.length} selected leads?`)) return;

  toast(`Deleting ${ids.length} leads...`, 'warning');
  let done = 0;
  for (const id of ids) {
    try { await API.deleteLead(id); done++; } catch {}
  }
  toast(`Successfully deleted ${done} leads`, 'success');
  
  // Uncheck select all
  const selectAll = document.getElementById('select-all');
  if (selectAll) selectAll.checked = false;
  
  onCheckboxChange();
  loadLeads(_leadsPage);
}

async function bulkSendEmails() {
  const ids = [...document.querySelectorAll('.lead-cb:checked')].map(cb => Number(cb.value));
  if (!ids.length) return;

  toast(`Preparing to send bulk emails to ${ids.length} leads...`, 'info');
  
  let successCount = 0;
  let skippedCount = 0;
  let errorCount = 0;

  for (const id of ids) {
    try {
      const lead = await API.getLead(id);
      
      // Validation checks
      if (!lead.email || !lead.email.trim()) {
        skippedCount++;
        continue;
      }
      if (!lead.cold_email_body || !lead.cold_email_body.trim()) {
        skippedCount++;
        continue;
      }

      // Trigger the send email API
      await API.sendEmail({
        lead_id: id,
        to_email: lead.email,
        subject: lead.cold_email_subject,
        body: lead.cold_email_body
      });
      successCount++;
    } catch (err) {
      console.error(`Error sending email to lead #${id}:`, err);
      errorCount++;
    }
    // Delay between SMTP deliveries to prevent spam blocks and rate limits
    await new Promise(r => setTimeout(r, 1000));
  }

  if (successCount > 0) {
    toast(`Successfully sent cold emails to ${successCount} leads!`, 'success');
  }
  if (skippedCount > 0) {
    toast(`Skipped ${skippedCount} leads (missing email or drafted message).`, 'warning');
  }
  if (errorCount > 0) {
    toast(`Failed to send emails to ${errorCount} leads due to SMTP/SMTP errors.`, 'error');
  }

  // Reset checkboxes & reload leads
  const selectAll = document.getElementById('select-all');
  if (selectAll) selectAll.checked = false;
  
  onCheckboxChange();
  loadLeads(_leadsPage);
}

// Filter: search on Enter
document.getElementById('lead-search')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') loadLeads(1);
});

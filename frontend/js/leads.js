/* leads.js — Leads table, filtering, pagination, bulk actions */

let _leadsPage     = 1;
let _leadsTotal    = 0;
let _leadsPageSize = 20;

async function loadLeads(page = 1) {
  _leadsPage = page;

  const params = {
    page,
    page_size: _leadsPageSize,
    status:    document.getElementById('filter-status')?.value || '',
    city:      document.getElementById('filter-city')?.value   || '',
    min_score: document.getElementById('filter-score')?.value  || '',
    search:    document.getElementById('lead-search')?.value   || '',
  };

  const tbody = document.getElementById('leads-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Loading...</td></tr>';

  try {
    const data = await API.getLeads(params);
    _leadsTotal = data.total;

    document.getElementById('leads-count').textContent = data.total;
    document.getElementById('badge-leads').textContent = data.total;

    if (!data.leads || data.leads.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" class="empty-state">
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
            <button class="btn-icon" title="Analyze" onclick="analyzeLeadInline(${lead.id}, this)"><i data-lucide="cpu" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i></button>
            <button class="btn-icon" title="Generate Messages" onclick="generateMessagesInline(${lead.id}, this)"><i data-lucide="pencil-line" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i></button>
            <button class="btn-icon" title="Send Email" onclick="openEmailForLead(${lead.id})"><i data-lucide="mail" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i></button>
            <button class="btn-icon" title="Delete" onclick="deleteLeadInline(${lead.id}, this)" style="color:var(--red)"><i data-lucide="trash-2" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i></button>
          </div>
        </td>
      </tr>
    `).join('');

    // Pagination
    renderPagination(data.pages, page);

    if (window.lucide) lucide.createIcons();

  } catch (e) {
    console.error('Load leads error:', e);
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state" style="color:var(--red)">Error loading leads: ${esc(e.message)}</td></tr>`;
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
  btn.innerHTML = '<i data-lucide="loader" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i>';
  if (window.lucide) lucide.createIcons();
  btn.disabled = true;
  try {
    await API.analyzeLead(id);
    toast(`Analysis started for lead #${id}`, 'info');
    btn.innerHTML = '<i data-lucide="check" style="width:14px;height:14px;display:inline-block;vertical-align:middle;color:var(--green)"></i>';
    if (window.lucide) lucide.createIcons();
    setTimeout(() => {
      btn.innerHTML = '<i data-lucide="cpu" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i>';
      if (window.lucide) lucide.createIcons();
      btn.disabled = false;
    }, 3000);
  } catch (e) {
    toast(e.message, 'error');
    btn.innerHTML = '<i data-lucide="cpu" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i>';
    if (window.lucide) lucide.createIcons();
    btn.disabled = false;
  }
}

async function generateMessagesInline(id, btn) {
  btn.innerHTML = '<i data-lucide="loader" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i>';
  if (window.lucide) lucide.createIcons();
  btn.disabled = true;
  try {
    await API.generateMessages(id);
    toast('Generating messages...', 'info');
    btn.innerHTML = '<i data-lucide="check" style="width:14px;height:14px;display:inline-block;vertical-align:middle;color:var(--green)"></i>';
    if (window.lucide) lucide.createIcons();
    setTimeout(() => {
      btn.innerHTML = '<i data-lucide="pencil-line" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i>';
      if (window.lucide) lucide.createIcons();
      btn.disabled = false;
      loadLeads(_leadsPage);
    }, 5000);
  } catch (e) {
    toast(e.message, 'error');
    btn.innerHTML = '<i data-lucide="pencil-line" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></i>';
    if (window.lucide) lucide.createIcons();
    btn.disabled = false;
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
    try { await API.analyzeLead(id); done++; } catch {}
    await new Promise(r => setTimeout(r, 500));
  }
  toast(`Queued analysis for ${done} leads`, 'success');
}

// Filter: search on Enter
document.getElementById('lead-search')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') loadLeads(1);
});

/* outreach.js — Outreach center, logs, follow-up queue */

async function loadOutreach() {
  await Promise.all([
    loadOutreachStats(),
    loadReadyToContact(),
    loadFollowupQueue(),
    loadOutreachLogs(),
  ]);
}

// ── Stats ─────────────────────────────────────────────────
async function loadOutreachStats() {
  try {
    const stats = await API.getOutreachStats();
    document.getElementById('out-sent').textContent    = stats.total_emails_sent;
    document.getElementById('out-today').textContent   = `${stats.sent_today}/${stats.daily_limit}`;
    document.getElementById('out-replies').textContent  = stats.replies_received;
    document.getElementById('out-interested').textContent = stats.interested;

    // Update top quota bar
    const pct = Math.min((stats.sent_today / stats.daily_limit) * 100, 100);
    document.getElementById('quota-text').textContent = `${stats.sent_today} / ${stats.daily_limit} emails today`;
    document.getElementById('quota-fill').style.width = pct + '%';
  } catch (e) {
    console.error('Outreach stats error:', e);
  }
}

// ── Ready to Contact (message_ready leads) ────────────────
async function loadReadyToContact() {
  const el = document.getElementById('outreach-list');
  try {
    const data = await API.getLeads({ status: 'message_ready', page_size: 20 });
    const leads = data.leads || [];

    document.getElementById('ready-count').textContent = data.total;

    if (leads.length === 0) {
      el.innerHTML = '<div class="empty-state">No leads with messages ready.<br>Analyze leads and generate messages first.</div>';
      return;
    }

    el.innerHTML = leads.map(lead => `
      <div class="outreach-item">
        <div class="outreach-info">
          <div class="outreach-biz">
            ${esc(lead.business_name)}
            <span style="margin-left:8px;font-size:11px;color:var(--text-3)">${esc(lead.city || '')} · ${esc(lead.category || '')}</span>
            ${scoreBadge(lead.lead_score)}
          </div>
          ${lead.cold_email_subject
            ? `<div style="font-size:12px;font-weight:600;color:var(--text-2);margin:6px 0 2px"><i data-lucide="mail" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> ${esc(lead.cold_email_subject)}</div>`
            : ''}
          <div class="outreach-preview">${esc(lead.cold_email_body || '—')}</div>
          ${lead.email
            ? `<div style="font-size:11px;color:var(--primary);margin-top:6px"><i data-lucide="send" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> ${esc(lead.email)}</div>`
            : '<div style="font-size:11px;color:var(--amber);margin-top:6px"><i data-lucide="alert-triangle" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> No email address — update manually</div>'}
        </div>
        <div class="outreach-actions">
          <button class="btn btn-sm btn-primary" onclick="sendDirectEmail(${lead.id})" ${!lead.email ? 'disabled title="No email address"' : ''}>
            <i data-lucide="send" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> Send
          </button>
          <button class="btn btn-sm btn-secondary" onclick="openLeadModal(${lead.id})">
            <i data-lucide="eye" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> View
          </button>
          <button class="btn btn-sm btn-ghost" onclick="openEmailForLead(${lead.id})">
            <i data-lucide="edit-2" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> Edit
          </button>
        </div>
      </div>
    `).join('');

    if (window.lucide) lucide.createIcons();

  } catch (e) {
    el.innerHTML = `<div class="empty-state" style="color:var(--red)">Error: ${esc(e.message)}</div>`;
  }
}

// ── Follow-up Queue ───────────────────────────────────────
async function loadFollowupQueue() {
  const el = document.getElementById('followup-list');
  try {
    const data = await API.getLeads({ status: 'contacted', page_size: 20 });
    const leads = (data.leads || []).filter(l => l.next_followup);

    if (leads.length === 0) {
      el.innerHTML = '<div class="empty-state">No follow-ups pending.<br>Scheduler will auto-send when due.</div>';
      return;
    }

    el.innerHTML = leads.map(lead => {
      const due = new Date(lead.next_followup + 'Z');
      const now  = new Date();
      const isPast = due < now;

      return `
        <div class="outreach-item">
          <div class="outreach-info">
            <div class="outreach-biz">${esc(lead.business_name)}
              <span style="margin-left:8px;font-size:11px;color:var(--text-3)">${esc(lead.city || '')}</span>
            </div>
            <div style="font-size:12px;color:${isPast ? 'var(--red)' : 'var(--text-3)'};margin-top:4px">
              ${isPast ? '<i data-lucide="zap" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:2px"></i> Due now' : `<i data-lucide="clock" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:2px"></i> Due ${due.toLocaleDateString()}`}
              · Follow-up #${lead.emails_sent}
            </div>
          </div>
          <div class="outreach-actions">
            ${isPast ? `<button class="btn btn-sm btn-primary" onclick="sendFollowup(${lead.id})"><i data-lucide="send" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> Send Now</button>` : ''}
            <button class="btn btn-sm btn-ghost" onclick="openLeadModal(${lead.id})"><i data-lucide="eye" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px"></i> View</button>
          </div>
        </div>`;
    }).join('');

    if (window.lucide) lucide.createIcons();

  } catch (e) {
    el.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
  }
}

// ── Outreach log table ────────────────────────────────────
async function loadOutreachLogs() {
  const tbody = document.getElementById('outreach-log-tbody');
  try {
    const logs = await API.getOutreachLogs();
    if (!logs || logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No outreach sent yet</td></tr>';
      return;
    }

    // Build a lead ID → name map (use what we have)
    const leadIds = [...new Set(logs.map(l => l.lead_id))];
    const leadMap = {};
    await Promise.all(leadIds.slice(0, 10).map(async id => {
      try {
        const lead = await API.getLead(id);
        leadMap[id] = lead.business_name;
      } catch {}
    }));

    tbody.innerHTML = logs.map(log => `
      <tr>
        <td>
          <span style="font-size:13px;font-weight:600;color:var(--text)">
            ${esc(leadMap[log.lead_id] || `Lead #${log.lead_id}`)}
          </span>
        </td>
        <td><span style="font-size:11px;background:var(--surface-2);padding:3px 8px;border-radius:5px">${log.message_type}</span></td>
        <td style="font-size:12px;color:var(--text-2);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${esc(log.message_subject || '—')}
        </td>
        <td style="text-align:center">
          ${log.follow_up_number === 0
            ? '<span style="color:var(--primary)"># Initial</span>'
            : `<span style="color:var(--amber)"># Follow-up ${log.follow_up_number}</span>`}
        </td>
        <td style="font-size:12px;color:var(--text-3)">${formatDate(log.sent_at)}</td>
        <td>${statusBadge(log.status === 'sent' ? 'contacted' : log.status)}</td>
      </tr>
    `).join('');

    if (window.lucide) lucide.createIcons();

  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Error: ${esc(e.message)}</td></tr>`;
  }
}

// ── Actions ───────────────────────────────────────────────
async function sendDirectEmail(leadId) {
  try {
    const lead = await API.getLead(leadId);
    if (!lead.email) { toast('No email address — update lead first', 'warning'); return; }

    const res = await API.sendEmail({
      lead_id: leadId,
      to_email: lead.email,
      subject:  lead.cold_email_subject || `Quick question about ${lead.business_name}`,
      body:     lead.cold_email_body || '',
      follow_up_number: 0,
    });

    if (res.success) {
      toast(`Email sent to ${lead.business_name}!`, 'success');
      loadOutreach();
    } else {
      toast('Send failed — check Gmail credentials', 'error');
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function sendFollowup(leadId) {
  try {
    const lead = await API.getLead(leadId);
    const followUpNum = lead.emails_sent;
    const body = followUpNum === 1 ? lead.followup_1 : lead.followup_2;
    const subject = `Re: ${lead.cold_email_subject || 'My previous email'}`;

    if (!body) { toast('No follow-up message generated', 'warning'); return; }

    const res = await API.sendEmail({
      lead_id: leadId,
      to_email: lead.email,
      subject,
      body,
      follow_up_number: followUpNum,
    });

    if (res.success) {
      toast(`Follow-up #${followUpNum} sent!`, 'success');
      loadOutreach();
    } else {
      toast('Send failed', 'error');
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

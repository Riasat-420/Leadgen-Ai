/* inbox.js — CRM Conversational split-pane Inbox */

let _inboxConversations = [];
let _activeLeadId = null;

async function loadInbox() {
  const listEl = document.getElementById('inbox-conversations-list');
  listEl.innerHTML = '<div class="empty-state" style="padding:32px 16px;">Loading conversations...</div>';
  
  try {
    const res = await fetch('/api/outreach/inbox/conversations');
    if (!res.ok) throw new Error('Could not fetch conversations');
    
    _inboxConversations = await res.json();
    renderConversationsList();
    
    // Auto-select active lead if we sync
    if (_activeLeadId) {
      selectConversation(_activeLeadId);
    }
  } catch (e) {
    listEl.innerHTML = `<div class="empty-state" style="padding:32px 16px;color:var(--red);">Error: ${e.message}</div>`;
  }
}

function renderConversationsList() {
  const listEl = document.getElementById('inbox-conversations-list');
  
  if (_inboxConversations.length === 0) {
    listEl.innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:center;padding:48px 16px;color:var(--text-3);gap:8px;text-align:center;">
        <i data-lucide="mail" style="width:28px;height:28px;opacity:0.3;"></i>
        <span style="font-size:12px;">No active conversations.<br>Initiate email outreach first!</span>
      </div>`;
    if (window.lucide) lucide.createIcons();
    return;
  }
  
  listEl.innerHTML = _inboxConversations.map(conv => {
    const activeClass = conv.id === _activeLeadId ? 'background:rgba(99, 102, 241, 0.1);border-left:3px solid var(--primary);' : 'border-left:3px solid transparent;';
    const indicatorColor = conv.status === 'replied' ? 'var(--cyan)' : (conv.status === 'interested' ? 'var(--green)' : 'var(--text-3)');
    const lastMsgText = conv.last_message ? esc(conv.last_message) : 'No messages yet';
    const lastMsgTime = conv.last_message_time ? timeAgo(conv.last_message_time) : '';
    const avatar = conv.business_name ? conv.business_name.charAt(0).toUpperCase() : '?';
    
    return `
      <div class="conv-item" onclick="selectConversation(${conv.id})" 
           style="padding:12px 16px;border-bottom:1px solid var(--border);cursor:pointer;transition:all 0.2s;display:flex;gap:12px;align-items:start;${activeClass}">
        <div class="lead-avatar" style="width:34px;height:34px;font-size:13px;flex-shrink:0;">${avatar}</div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">
            <div style="font-size:12px;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:130px;">${esc(conv.business_name)}</div>
            <span style="font-size:10px;color:var(--text-3);flex-shrink:0;">${lastMsgTime}</span>
          </div>
          <div style="font-size:11px;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${lastMsgText}</div>
          <div style="display:flex;align-items:center;gap:6px;margin-top:6px;flex-wrap:wrap;">
            <span class="status-badge status-${conv.status}" style="font-size:9px;padding:1px 6px;">${conv.status.replace('_',' ')}</span>
            ${conv.reply_received ? `<span style="font-size:10px;color:var(--cyan);font-weight:500;display:inline-flex;align-items:center;gap:2px;"><i data-lucide="reply" style="width:10px;height:10px;"></i> Replied</span>` : ''}
          </div>
        </div>
      </div>`;
  }).join('');
  
  if (window.lucide) lucide.createIcons();
}

async function selectConversation(leadId) {
  _activeLeadId = leadId;
  renderConversationsList(); // highlight active
  
  const bodyEl = document.getElementById('inbox-thread-body');
  const footerEl = document.getElementById('inbox-thread-footer');
  
  bodyEl.innerHTML = '<div class="empty-state">Loading message history...</div>';
  
  try {
    const res = await fetch(`/api/outreach/inbox/conversations/${leadId}/thread`);
    if (!res.ok) throw new Error('Could not load thread');
    
    const data = await res.json();
    const lead = data.lead;
    const thread = data.thread;
    
    // Update Header
    document.getElementById('inbox-lead-details').innerHTML = `
      <div style="font-size:14px;font-weight:600;color:var(--text);">${esc(lead.business_name)}</div>
      <div style="font-size:11px;color:var(--text-3);display:flex;gap:10px;align-items:center;margin-top:2px;">
        <span><i data-lucide="mail" style="width:12px;height:12px;vertical-align:middle;margin-right:2px;"></i> ${esc(lead.email || 'No email')}</span>
        <span><i data-lucide="tag" style="width:12px;height:12px;vertical-align:middle;margin-right:2px;"></i> ID: #${lead.id}</span>
      </div>`;
      
    document.getElementById('inbox-lead-status').innerHTML = statusBadge(lead.status);
    
    // Render Thread
    if (thread.length === 0) {
      bodyEl.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--text-3);gap:8px;">
          <i data-lucide="mail-warning" style="width:36px;height:36px;opacity:0.3;"></i>
          <span style="font-size:12px;">No email records found. Send the first cold pitch!</span>
        </div>`;
    } else {
      bodyEl.innerHTML = thread.map(msg => {
        const isIncoming = msg.message_type === 'incoming';
        const alignStyle = isIncoming ? 'align-self:flex-start;max-width:85%;' : 'align-self:flex-end;max-width:85%;';
        const bubbleStyle = isIncoming 
          ? 'background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:12px 12px 12px 2px;' 
          : 'background:var(--primary-dim);border:1px solid rgba(99, 102, 241, 0.2);border-radius:12px 12px 2px 12px;';
        const labelText = isIncoming ? 'Client Reply' : (msg.follow_up_number === 0 ? 'Cold Outreach' : `Follow-up #${msg.follow_up_number}`);
        const labelColor = isIncoming ? 'var(--cyan)' : 'var(--primary)';
        const dateText = formatDate(msg.sent_at);
        
        return `
          <div style="display:flex;flex-direction:column;${alignStyle}">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;padding:0 4px;font-size:10px;">
              <span style="font-weight:600;color:${labelColor};">${labelText}</span>
              <span style="color:var(--text-3);margin-left:12px;">${dateText}</span>
            </div>
            <div style="padding:14px 16px;font-size:13px;color:var(--text);line-height:1.5;white-space:pre-wrap;${bubbleStyle}">${esc(msg.message_body)}</div>
          </div>`;
      }).join('');
      
      // Auto Scroll to bottom
      bodyEl.scrollTop = bodyEl.scrollHeight;
    }
    
    // Enable Footer reply
    footerEl.style.display = 'flex';
    document.getElementById('inbox-reply-subject').value = `Re: ${thread.length > 0 ? thread[0].message_subject : 'Outreach Request'}`;
    
  } catch (e) {
    bodyEl.innerHTML = `<div class="empty-state" style="color:var(--red);">Error: ${e.message}</div>`;
  }
  
  if (window.lucide) lucide.createIcons();
}

async function syncInbox() {
  const syncBtn = document.getElementById('sync-inbox-btn');
  const oldText = syncBtn.innerHTML;
  syncBtn.innerHTML = '<i data-lucide="loader" style="width:12px;height:12px;display:inline-block;vertical-align:middle;animation:spin 1s infinite linear;"></i> Syncing...';
  if (window.lucide) lucide.createIcons();
  syncBtn.disabled = true;
  
  toast('Synchronizing IMAP inbox responses...', 'info');
  
  try {
    const res = await fetch('/api/outreach/inbox/sync', { method: 'POST' });
    if (!res.ok) throw new Error('IMAP mail check error');
    
    const data = await res.json();
    if (data.new_messages > 0) {
      toast(`Sync Complete! Fetched ${data.new_messages} new lead replies! 🎉`, 'success');
    } else {
      toast('Inbox is already up to date!', 'success');
    }
    loadInbox();
  } catch (e) {
    toast('Sync Failed: ' + e.message, 'error');
  } finally {
    syncBtn.innerHTML = oldText;
    if (window.lucide) lucide.createIcons();
    syncBtn.disabled = false;
  }
}

async function sendInboxReply() {
  if (!_activeLeadId) return;
  
  const bodyInput = document.getElementById('inbox-reply-body');
  const subjectInput = document.getElementById('inbox-reply-subject');
  
  const body = bodyInput.value.trim();
  const subject = subjectInput.value.trim();
  
  if (!body) { toast('Please write a message body', 'warning'); return; }
  
  toast('Delivering reply...', 'info');
  
  try {
    const res = await fetch('/api/outreach/send-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lead_id: _activeLeadId,
        to_email: '',
        subject: subject,
        body: body,
        follow_up_number: 99 // manual reply
      })
    });
    
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not deliver email');
    }
    
    toast('Reply sent successfully!', 'success');
    bodyInput.value = ''; // clear input
    
    // Refresh thread
    selectConversation(_activeLeadId);
  } catch (e) {
    toast(e.message, 'error');
  }
}

function filterInbox() {
  const query = document.getElementById('inbox-search').value.toLowerCase().trim();
  const items = document.querySelectorAll('.conv-item');
  
  items.forEach(item => {
    const text = item.textContent.toLowerCase();
    item.style.display = text.includes(query) ? 'flex' : 'none';
  });
}

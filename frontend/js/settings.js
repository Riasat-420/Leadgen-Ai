/* settings.js — Loading, saving, and testing SMTP and IMAP configurations */

async function loadSettings() {
  const saveBtn = document.getElementById('save-sett-btn');
  const testBtn = document.getElementById('test-conn-btn');
  
  if (saveBtn) saveBtn.disabled = true;
  if (testBtn) testBtn.disabled = true;
  
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) throw new Error('Failed to retrieve settings');
    
    const settings = await res.json();
    
    document.getElementById('sett-smtp-host').value = settings.smtp_host || '';
    document.getElementById('sett-smtp-port').value = settings.smtp_port || '';
    document.getElementById('sett-smtp-enc').value = settings.smtp_encryption || 'starttls';
    document.getElementById('sett-smtp-name').value = settings.smtp_sender_name || '';
    document.getElementById('sett-smtp-user').value = settings.smtp_user || '';
    document.getElementById('sett-smtp-pass').value = settings.smtp_password || '';
    
    document.getElementById('sett-imap-host').value = settings.imap_host || '';
    document.getElementById('sett-imap-port').value = settings.imap_port || '';
    
    const geminiInput = document.getElementById('sett-gemini-key');
    if (geminiInput) {
      geminiInput.value = settings.gemini_api_key || '';
    }
    
  } catch (e) {
    toast('Error loading credentials: ' + e.message, 'error');
  } finally {
    if (saveBtn) saveBtn.disabled = false;
    if (testBtn) testBtn.disabled = false;
  }
}

async function saveSettings() {
  const saveBtn = document.getElementById('save-sett-btn');
  const oldText = saveBtn.innerHTML;
  saveBtn.innerHTML = '<i data-lucide="loader" style="width:14px;height:14px;display:inline-block;vertical-align:middle;animation:spin 1s infinite linear;"></i> Saving...';
  if (window.lucide) lucide.createIcons();
  saveBtn.disabled = true;
  
  const payload = {
    smtp_host: document.getElementById('sett-smtp-host').value.trim(),
    smtp_port: document.getElementById('sett-smtp-port').value.trim(),
    smtp_encryption: document.getElementById('sett-smtp-enc').value,
    smtp_sender_name: document.getElementById('sett-smtp-name').value.trim(),
    smtp_user: document.getElementById('sett-smtp-user').value.trim(),
    smtp_password: document.getElementById('sett-smtp-pass').value,
    imap_host: document.getElementById('sett-imap-host').value.trim(),
    imap_port: document.getElementById('sett-imap-port').value.trim(),
    gemini_api_key: document.getElementById('sett-gemini-key') ? document.getElementById('sett-gemini-key').value.trim() : ''
  };
  
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not save configurations');
    }
    
    toast('Configurations saved successfully!', 'success');
    loadSettings();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    saveBtn.innerHTML = oldText;
    if (window.lucide) lucide.createIcons();
    saveBtn.disabled = false;
  }
}

async function testConnection() {
  const testBtn = document.getElementById('test-conn-btn');
  const oldText = testBtn.innerHTML;
  testBtn.innerHTML = '<i data-lucide="loader" style="width:14px;height:14px;display:inline-block;vertical-align:middle;animation:spin 1s infinite linear;"></i> Testing...';
  if (window.lucide) lucide.createIcons();
  testBtn.disabled = true;
  
  const payload = {
    smtp_host: document.getElementById('sett-smtp-host').value.trim(),
    smtp_port: document.getElementById('sett-smtp-port').value.trim(),
    smtp_encryption: document.getElementById('sett-smtp-enc').value,
    smtp_sender_name: document.getElementById('sett-smtp-name').value.trim(),
    smtp_user: document.getElementById('sett-smtp-user').value.trim(),
    smtp_password: document.getElementById('sett-smtp-pass').value,
    imap_host: document.getElementById('sett-imap-host').value.trim(),
    imap_port: document.getElementById('sett-imap-port').value.trim(),
    gemini_api_key: document.getElementById('sett-gemini-key') ? document.getElementById('sett-gemini-key').value.trim() : ''
  };
  
  try {
    const res = await fetch('/api/settings/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'SMTP test authentication failed');
    }
    
    toast(data.message || 'SMTP Authentication Successful!', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    testBtn.innerHTML = oldText;
    if (window.lucide) lucide.createIcons();
    testBtn.disabled = false;
  }
}

async function testGemini() {
  const testBtn = document.getElementById('test-gemini-btn');
  if (!testBtn) return;
  const oldText = testBtn.innerHTML;
  testBtn.innerHTML = '<i data-lucide="loader" style="width:14px;height:14px;display:inline-block;vertical-align:middle;animation:spin 1s infinite linear;"></i> Testing...';
  if (window.lucide) lucide.createIcons();
  testBtn.disabled = true;
  
  const payload = {
    smtp_host: document.getElementById('sett-smtp-host').value.trim(),
    smtp_port: document.getElementById('sett-smtp-port').value.trim(),
    smtp_encryption: document.getElementById('sett-smtp-enc').value,
    smtp_sender_name: document.getElementById('sett-smtp-name').value.trim(),
    smtp_user: document.getElementById('sett-smtp-user').value.trim(),
    smtp_password: document.getElementById('sett-smtp-pass').value,
    imap_host: document.getElementById('sett-imap-host').value.trim(),
    imap_port: document.getElementById('sett-imap-port').value.trim(),
    gemini_api_key: document.getElementById('sett-gemini-key') ? document.getElementById('sett-gemini-key').value.trim() : ''
  };
  
  try {
    const res = await fetch('/api/settings/test-gemini', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Gemini API key validation failed');
    }
    
    toast(data.message || 'Gemini API Key is valid and working!', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    testBtn.innerHTML = oldText;
    if (window.lucide) lucide.createIcons();
    testBtn.disabled = false;
  }
}

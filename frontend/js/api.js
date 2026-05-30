/* api.js — Centralized API client */

const API = {
  BASE: 'https://riasat360-leadgen-backend.hf.space',

  async get(path) {
    const res = await fetch(this.BASE + path);
    if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
    return res.json();
  },

  async post(path, data) {
    const res = await fetch(this.BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `POST ${path} failed: ${res.status}`);
    }
    return res.json();
  },

  async patch(path, data) {
    const res = await fetch(this.BASE + path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`);
    return res.json();
  },

  async del(path) {
    const res = await fetch(this.BASE + path, { method: 'DELETE' });
    if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`);
    return res.json();
  },

  // ── Leads ─────────────────────────────────────────────
  async getLeads(params = {}) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== '' && v !== null && v !== undefined) q.append(k, v);
    }
    return this.get(`/api/leads?${q}`);
  },
  async getLead(id)         { return this.get(`/api/leads/${id}`); },
  async updateLead(id, d)   { return this.patch(`/api/leads/${id}`, d); },
  async analyzeLead(id)     { return this.post(`/api/leads/${id}/analyze`, {}); },
  async generateMessages(id){ return this.post(`/api/leads/${id}/generate-messages`, {}); },
  async deleteLead(id)      { return this.del(`/api/leads/${id}`); },

  // ── Scraper ───────────────────────────────────────────
  async startScrape(d)           { return this.post('/api/scrape/start', d); },
  async startPlatformScrape(d)   { return this.post('/api/scrape/platform', d); },
  async scrapeStatus(id)         { return this.get(`/api/scrape/status/${id}`); },
  async getJobs()                { return this.get('/api/scrape/jobs'); },
  async getTargets()             { return this.get('/api/scrape/targets'); },

  // ── Outreach ──────────────────────────────────────────
  async sendEmail(d)         { return this.post('/api/outreach/send-email', d); },
  async markReply(id, text)  { return this.post(`/api/outreach/${id}/reply`, { reply_text: text }); },
  async getOutreachLogs(lid) { return this.get(`/api/outreach/logs${lid ? '?lead_id=' + lid : ''}`); },
  async getOutreachStats()   { return this.get('/api/outreach/stats'); },

  // ── Dashboard ─────────────────────────────────────────
  async getDashboardStats()  { return this.get('/api/dashboard/stats'); },
};

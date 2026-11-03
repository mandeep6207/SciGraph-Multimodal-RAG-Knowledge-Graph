/**
 * SciGraph API Client
 * Centralized communication layer with error handling and real API contracts.
 */
const API = {
  baseUrl: '',

  async getHealth() {
    const res = await fetch(`${this.baseUrl}/health`);
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
    return res.json();
  },

  async getStats() {
    const res = await fetch(`${this.baseUrl}/stats`);
    if (!res.ok) throw new Error(`Stats fetch failed: ${res.status}`);
    return res.json();
  },

  async getUploads() {
    const res = await fetch(`${this.baseUrl}/uploads`);
    if (!res.ok) throw new Error(`Failed to fetch uploads: ${res.status}`);
    return res.json();
  },

  async uploadFile(file, force = false) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${this.baseUrl}/upload?force=${force}`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async uploadBatch(files, force = false) {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    const res = await fetch(`${this.baseUrl}/upload/batch?force=${force}`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Batch upload failed' }));
      throw new Error(err.detail || 'Batch upload failed');
    }
    return res.json();
  },

  async deleteDocument(filename) {
    const res = await fetch(`${this.baseUrl}/documents/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Delete failed' }));
      throw new Error(err.detail || 'Delete failed');
    }
    return res.json();
  },

  async query(payload) {
    const res = await fetch(`${this.baseUrl}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Query failed' }));
      throw new Error(err.detail || 'Query failed');
    }
    return res.json();
  },

  async getGraph(limit = 300, search = '') {
    const query = new URLSearchParams({ limit, search }).toString();
    const res = await fetch(`${this.baseUrl}/graph?${query}`);
    if (!res.ok) throw new Error(`Graph query failed: ${res.status}`);
    return res.json();
  },

  async getConversations() {
    const res = await fetch(`${this.baseUrl}/conversations`);
    if (!res.ok) return [];
    return res.json();
  },

  async saveConversations(convs) {
    const res = await fetch(`${this.baseUrl}/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(convs),
    });
    return res.json();
  },

  async deleteConversation(id) {
    const res = await fetch(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
    return res.json();
  },

  async getProfile() {
    const res = await fetch(`${this.baseUrl}/profile`);
    if (!res.ok) return null;
    return res.json();
  },

  async saveProfile(data) {
    const res = await fetch(`${this.baseUrl}/profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  async uploadAvatar(file) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${this.baseUrl}/profile/avatar`, {
      method: 'POST',
      body: fd,
    });
    return res.json();
  },

  async getWorkspaces() {
    const res = await fetch(`${this.baseUrl}/workspaces`);
    if (!res.ok) return [];
    return res.json();
  },

  async createWorkspace(data) {
    const res = await fetch(`${this.baseUrl}/workspaces`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  async deleteWorkspace(id) {
    const res = await fetch(`${this.baseUrl}/workspaces/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
    return res.json();
  },

  async clearCache() {
    const res = await fetch(`${this.baseUrl}/data/clear-cache`, {
      method: 'POST',
    });
    return res.json();
  },

  async pauseQueue() {
    const res = await fetch(`${this.baseUrl}/queue/pause`, { method: 'POST' });
    return res.json();
  },

  async resumeQueue() {
    const res = await fetch(`${this.baseUrl}/queue/resume`, { method: 'POST' });
    return res.json();
  },

  async getQueueStatus() {
    const res = await fetch(`${this.baseUrl}/queue/status`);
    return res.json();
  },

  async cancelJob(jobId) {
    const res = await fetch(`${this.baseUrl}/queue/cancel/${encodeURIComponent(jobId)}`, { method: 'POST' });
    return res.json();
  },

  async retryJob(jobId) {
    const res = await fetch(`${this.baseUrl}/queue/retry/${encodeURIComponent(jobId)}`, { method: 'POST' });
    return res.json();
  },

  async removeJob(jobId) {
    const res = await fetch(`${this.baseUrl}/queue/remove/${encodeURIComponent(jobId)}`, { method: 'POST' });
    return res.json();
  },

  async clearCompletedJobs() {
    const res = await fetch(`${this.baseUrl}/queue/completed`, { method: 'DELETE' });
    return res.json();
  },

  async resetAllData(confirmationPhrase) {
    const res = await fetch(`${this.baseUrl}/data/reset-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmation: confirmationPhrase }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Reset failed' }));
      throw new Error(err.detail || 'Reset failed');
    }
    return res.json();
  },
};

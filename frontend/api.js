/**
 * VocalVitals API Client
 * Wraps all backend REST calls. Set VOCALVITALS_API_URL in your environment
 * or replace the default below with your Render service URL.
 */

const API_BASE = window.VOCALVITALS_API_URL || 'http://localhost:8000';

const Api = {
    _token() {
        return localStorage.getItem('vv_token');
    },

    _headers(extra = {}) {
        const h = { 'Content-Type': 'application/json', ...extra };
        const t = this._token();
        if (t) h['Authorization'] = `Bearer ${t}`;
        return h;
    },

    async register(email, password) {
        const r = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify({ email, password }),
        });
        if (!r.ok) throw new Error((await r.json()).detail);
        return r.json();
    },

    async login(email, password) {
        const r = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify({ email, password }),
        });
        if (!r.ok) throw new Error((await r.json()).detail);
        const data = await r.json();
        localStorage.setItem('vv_token', data.access_token);
        return data;
    },

    logout() {
        localStorage.removeItem('vv_token');
    },

    async me() {
        const r = await fetch(`${API_BASE}/auth/me`, { headers: this._headers() });
        if (!r.ok) return null;
        return r.json();
    },

    async saveSession(prediction, confidence, durationMs, features) {
        const r = await fetch(`${API_BASE}/sessions`, {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify({ prediction, confidence, duration_ms: durationMs, features }),
        });
        if (!r.ok) throw new Error((await r.json()).detail);
        return r.json();
    },

    async getSessions(page = 1, pageSize = 20) {
        const r = await fetch(`${API_BASE}/sessions?page=${page}&page_size=${pageSize}`, {
            headers: this._headers(),
        });
        if (!r.ok) throw new Error((await r.json()).detail);
        return r.json();
    },

    async getBaseline() {
        const r = await fetch(`${API_BASE}/baseline`, { headers: this._headers() });
        if (r.status === 404) return null;
        if (!r.ok) throw new Error((await r.json()).detail);
        return r.json();
    },

    async resetBaseline() {
        const r = await fetch(`${API_BASE}/baseline/reset`, {
            method: 'PUT',
            headers: this._headers(),
        });
        if (!r.ok) throw new Error((await r.json()).detail);
        return r.json();
    },

    async getModelVersion() {
        const r = await fetch(`${API_BASE}/model/version`);
        if (!r.ok) return null;
        return r.json();
    },
};

// ═══════════════════════════════════════════════════════════
// TEKKEN TOURNAMENT — SHARED UTILITIES
// ═══════════════════════════════════════════════════════════

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000/api'
  : `${window.location.origin}/api`;

const WS_BASE = API_BASE.replace(/^http/, 'ws').replace('/api', '') + '/api';

// ─── API Client ──────────────────────────────────────────────
const api = {
  async get(path) {
    const res = await fetch(API_BASE + path);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Request failed');
    }
    return res.json();
  },

  async post(path, body) {
    const res = await fetch(API_BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Request failed');
    }
    return res.json();
  },

  async put(path, body) {
    const res = await fetch(API_BASE + path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Request failed');
    }
    return res.json();
  },

  async delete(path) {
    const res = await fetch(API_BASE + path, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Request failed');
    }
    return res.json();
  }
};

// ─── Toast Notifications ─────────────────────────────────────
const Toast = (() => {
  let container;

  function getContainer() {
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function show(msg, type = 'info', duration = 3500) {
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || '📢'}</span>
      <span class="toast-msg">${msg}</span>
    `;
    getContainer().appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'toastOut 0.4s cubic-bezier(0.4,0,0.2,1) forwards';
      setTimeout(() => toast.remove(), 400);
    }, duration);
  }

  return { show, success: m => show(m,'success'), error: m => show(m,'error'),
           info: m => show(m,'info'), warning: m => show(m,'warning') };
})();

// ─── WebSocket Manager ────────────────────────────────────────
class WSClient {
  constructor(path, onMessage) {
    this.path = path;
    this.onMessage = onMessage;
    this.ws = null;
    this.reconnectDelay = 1000;
    this.maxDelay = 30000;
    this.pingInterval = null;
    this.statusEl = null;
    this.connect();
  }

  setStatusEl(el) { this.statusEl = el; }

  connect() {
    try {
      this.ws = new WebSocket(WS_BASE + this.path);

      this.ws.onopen = () => {
        console.log('[WS] Connected');
        this.reconnectDelay = 1000;
        this._setStatus('connected');
        this.pingInterval = setInterval(() => {
          if (this.ws.readyState === WebSocket.OPEN) this.ws.send('ping');
        }, 25000);
      };

      this.ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type !== 'pong') this.onMessage(data);
        } catch (err) { console.warn('[WS] Parse error', err); }
      };

      this.ws.onclose = () => {
        console.log('[WS] Disconnected, reconnecting...');
        this._setStatus('disconnected');
        clearInterval(this.pingInterval);
        setTimeout(() => this.connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxDelay);
      };

      this.ws.onerror = (err) => {
        console.error('[WS] Error', err);
        this.ws.close();
      };
    } catch (e) {
      console.error('[WS] Failed to connect', e);
      setTimeout(() => this.connect(), this.reconnectDelay);
    }
  }

  _setStatus(status) {
    if (this.statusEl) {
      this.statusEl.className = `ws-status-bar ${status}`;
      const dot = this.statusEl.querySelector('.status-dot');
      const label = this.statusEl.querySelector('.ws-label');
      if (dot) dot.className = `status-dot ${status === 'connected' ? 'live' : 'offline'}`;
      if (label) label.textContent = status === 'connected' ? 'LIVE' : 'RECONNECTING...';
    }
  }

  close() {
    clearInterval(this.pingInterval);
    if (this.ws) this.ws.close();
  }
}

// ─── Helpers ──────────────────────────────────────────────────
function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
  });
}

function getRankEmoji(rank) {
  if (rank === 1) return '👑';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return `#${rank}`;
}

function getStreakDisplay(streak) {
  if (streak >= 5) return `🔥${streak}`;
  if (streak >= 3) return `⚡${streak}`;
  if (streak > 0)  return `✨${streak}`;
  return streak;
}

function setLoading(btn, loading) {
  if (loading) {
    btn.disabled = true;
    btn._orig = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> ${btn.dataset.loadingText || 'Processing...'}`;
  } else {
    btn.disabled = false;
    btn.innerHTML = btn._orig || btn.innerHTML;
  }
}

// ─── Nav highlight ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const links = document.querySelectorAll('.nav-links a');
  links.forEach(link => {
    if (link.href === window.location.href) link.classList.add('active');
  });
});
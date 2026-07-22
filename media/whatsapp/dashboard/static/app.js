/* WhatsApp Bot v3 — Dashboard WebSocket client */

const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${location.host}/ws/dashboard`;
let ws = null;
let reconnectInterval = 2000;

function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        document.getElementById('connection-status').textContent = 'Connected';
        document.getElementById('connection-status').className = 'status connected';
        reconnectInterval = 2000;
        console.log('[Dashboard] Connected');
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    ws.onclose = () => {
        document.getElementById('connection-status').textContent = 'Disconnected';
        document.getElementById('connection-status').className = 'status disconnected';
        console.log(`[Dashboard] Disconnected — reconnecting in ${reconnectInterval}ms`);
        setTimeout(connect, reconnectInterval);
        reconnectInterval = Math.min(reconnectInterval * 1.5, 30000);
    };

    ws.onerror = (err) => {
        console.error('[Dashboard] WebSocket error:', err);
        ws.close();
    };
}

function handleMessage(msg) {
    switch (msg.type) {
        case 'connected':
            console.log('[Dashboard] Server acknowledged connection');
            fetchInitialData();
            break;
        case 'ping':
            // Heartbeat — no action needed
            break;
        case 'message_received':
            addFeedEntry('received', msg.data);
            updateMetric('messages-value', (v) => v + 1);
            break;
        case 'message_sent':
            addFeedEntry('sent', msg.data);
            break;
        case 'approval_added':
            addApproval(msg.data);
            updateMetric('pending-value', (v) => v + 1);
            addFeedEntry('decision', {contact: msg.data.contact, text: `Approval needed: ${msg.data.reason}`, risk: msg.data.risk_level});
            break;
        case 'approval_processed':
            removeApproval(msg.data.msg_id);
            updateMetric('pending-value', (v) => Math.max(0, v - 1));
            break;
        case 'keyword_alert':
            addFeedEntry('alert', {contact: msg.data.contact, text: `Keyword alert: ${msg.data.keyword}`});
            break;
        case 'health_update':
            updateHealth(msg.data);
            break;
        case 'metrics_update':
            updateMetrics(msg.data);
            break;
        case 'command_result':
            console.log('[Dashboard] Command result:', msg.data);
            if (msg.data.command === 'approve' && msg.data.success) {
                removeApproval(msg.data.msg_id);
                updateMetric('pending-value', (v) => Math.max(0, v - 1));
            }
            break;
        default:
            console.log('[Dashboard] Unknown message type:', msg.type, msg.data);
    }
}

// ── UI Helpers ──────────────────────────────────────────────────────────────

function addFeedEntry(type, data) {
    const feed = document.getElementById('messages-feed');
    const entry = document.createElement('div');
    entry.className = `msg-entry ${type}`;
    const time = new Date().toLocaleTimeString();
    const riskBadge = data.risk ? `<span class="risk-badge risk-${data.risk.toLowerCase()}">${data.risk}</span>` : '';
    entry.innerHTML = `
        <div class="msg-time">${time} ${riskBadge}</div>
        <div class="msg-contact">${escapeHtml(data.contact || 'Unknown')}</div>
        <div class="msg-text">${escapeHtml(data.text || data.reply_preview || '')}</div>
    `;
    feed.insertBefore(entry, feed.firstChild);
    // Keep last 50 entries
    while (feed.children.length > 50) {
        feed.removeChild(feed.lastChild);
    }
}

function addApproval(data) {
    const list = document.getElementById('approvals-list');
    // Remove "empty" placeholder
    const empty = list.querySelector('.empty');
    if (empty) empty.remove();

    const item = document.createElement('div');
    item.className = `approval-item ${(data.risk_level || '').toLowerCase()}`;
    item.id = `approval-${data.msg_id}`;
    item.innerHTML = `
        <div class="approval-contact">${escapeHtml(data.contact)}</div>
        <div class="approval-reason">${escapeHtml(data.reason || '')} <span class="risk-badge risk-${(data.risk_level||'low').toLowerCase()}">${data.risk_level || 'LOW'}</span></div>
        <div class="approval-preview">${escapeHtml((data.preview || '').substring(0, 100))}</div>
        <div class="approval-actions">
            <button class="btn btn-success btn-sm" onclick="approveMsg(${data.msg_id})">Approve</button>
            <button class="btn btn-danger btn-sm" onclick="rejectMsg(${data.msg_id})">Reject</button>
        </div>
    `;
    list.insertBefore(item, list.firstChild);
}

function removeApproval(msgId) {
    const item = document.getElementById(`approval-${msgId}`);
    if (item) item.remove();
    // Re-add empty placeholder if no items
    const list = document.getElementById('approvals-list');
    if (list.children.length === 0) {
        list.innerHTML = '<div class="empty">No pending approvals</div>';
    }
}

function updateHealth(data) {
    const el = document.getElementById('health-value');
    el.textContent = data.status === 'healthy' ? '✓ Healthy' : '✗ Unhealthy';
    el.style.color = data.status === 'healthy' ? 'var(--success)' : 'var(--danger)';
    document.getElementById('uptime-value').textContent = formatDuration(data.uptime_seconds);
    // Find AI providers check
    const providersCheck = data.checks?.find(c => c.name === 'ai_providers');
    if (providersCheck) {
        document.getElementById('providers-value').textContent = providersCheck.message;
    }
}

function updateMetrics(data) {
    const detail = document.getElementById('metrics-detail');
    if (!data.counters) return;
    let html = '';
    // Show key counters
    const keys = Object.keys(data.counters).filter(k =>
        k.includes('send_success') || k.includes('send_fail') ||
        k.includes('ai_calls') || k.includes('decision') ||
        k.includes('keyword') || k.includes('approval')
    );
    keys.sort();
    for (const k of keys) {
        html += `<div class="metric-row"><span class="metric-key">${escapeHtml(k)}</span><span class="metric-val">${data.counters[k]}</span></div>`;
    }
    detail.innerHTML = html || '<div class="empty">No metrics yet</div>';
}

function updateMetric(id, fn) {
    const el = document.getElementById(id);
    const current = parseInt(el.textContent) || 0;
    el.textContent = fn(current);
}

function formatDuration(secs) {
    if (secs < 60) return `${Math.round(secs)}s`;
    if (secs < 3600) return `${Math.floor(secs/60)}m ${Math.round(secs%60)}s`;
    return `${Math.floor(secs/3600)}h ${Math.floor((secs%3600)/60)}m`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text || '');
    return div.innerHTML;
}

// ── Actions ─────────────────────────────────────────────────────────────────

function approveMsg(msgId) {
    const reply = prompt('Custom reply (leave empty for AI-generated):');
    if (reply === null) return; // Cancelled
    ws.send(JSON.stringify({command: 'approve', msg_id: msgId, custom_reply: reply}));
}

function rejectMsg(msgId) {
    const reason = prompt('Rejection reason:');
    if (reason === null) return;
    ws.send(JSON.stringify({command: 'reject', msg_id: msgId, reason: reason}));
}

function stopBot() {
    if (!confirm('Stop the bot? It will shut down gracefully.')) return;
    ws.send(JSON.stringify({command: 'stop'}));
}

// ── Initial data fetch ──────────────────────────────────────────────────────

function fetchInitialData() {
    // Fetch pending approvals
    fetch('/api/pending').then(r => r.json()).then(data => {
        const list = document.getElementById('approvals-list');
        list.innerHTML = '';
        if (!data.items || data.items.length === 0) {
            list.innerHTML = '<div class="empty">No pending approvals</div>';
        } else {
            document.getElementById('pending-value').textContent = data.count || data.items.length;
            data.items.forEach(item => {
                addApproval({
                    msg_id: item.msg_id,
                    contact: item.contact,
                    reason: item.decision?.reason,
                    risk_level: item.decision?.risk_level,
                    preview: item.messages?.[0]?.content?.substring(0, 100),
                });
            });
        }
    }).catch(() => {});

    // Fetch health
    fetch('/api/health').then(r => r.json()).then(data => {
        updateHealth(data);
    }).catch(() => {});

    // Fetch plugins
    fetch('/api/plugins').then(r => r.json()).then(data => {
        const list = document.getElementById('plugins-list');
        if (data.plugins) {
            list.innerHTML = data.plugins.map(p => `
                <div class="plugin-item">
                    <div class="plugin-name">${escapeHtml(p.name)} v${p.version}</div>
                    <div class="plugin-desc">${escapeHtml(p.description)}</div>
                    <div class="plugin-enabled">● ${p.hooks.length} hooks</div>
                </div>
            `).join('');
        }
    }).catch(() => {});

    // Fetch knowledge sources
    fetch('/api/knowledge/sources').then(r => r.json()).then(data => {
        const list = document.getElementById('knowledge-sources');
        if (data.sources && data.sources.length > 0) {
            list.innerHTML = data.sources.map(s => `<div class="plugin-item"><div class="plugin-name">${escapeHtml(s)}</div></div>`).join('');
        } else {
            list.innerHTML = '<div class="empty">No sources ingested</div>';
        }
    }).catch(() => {});

    // Fetch scheduled messages
    fetch('/api/scheduled').then(r => r.json()).then(data => {
        const list = document.getElementById('scheduled-list');
        if (data.items && data.items.length > 0) {
            list.innerHTML = data.items.map(m => `
                <div class="plugin-item">
                    <div class="plugin-name">${escapeHtml(m.contact_name)}</div>
                    <div class="plugin-desc">${escapeHtml(m.text.substring(0, 60))}</div>
                    <div class="plugin-desc">→ ${new Date(m.scheduled_for).toLocaleString()}</div>
                </div>
            `).join('');
        } else {
            list.innerHTML = '<div class="empty">No scheduled messages</div>';
        }
    }).catch(() => {});
}

// ── Periodic refresh ────────────────────────────────────────────────────────
setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        fetch('/api/health').then(r => r.json()).then(data => updateHealth(data)).catch(() => {});
        fetch('/api/metrics').then(r => r.json()).then(data => updateMetrics(data)).catch(() => {});
    }
}, 5000);

// ── Start ───────────────────────────────────────────────────────────────────
connect();

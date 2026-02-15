/**
 * Popup UI for Multi-Region Description Consistency Checker
 * Provides quick ASIN search, last result status, and check history.
 */
(function () {
    'use strict';

    const API_PROD = 'https://raashid-project-production-55d9.up.railway.app';
    const API_LOCAL = 'http://localhost:5000';
    let API_BASE = API_PROD; // Default to production
    const HISTORY_KEY = 'mrdcc_history';

    const RISK_ICONS = { LOW: '\u2705', MEDIUM: '\u26A0\uFE0F', HIGH: '\u274C' };

    // DOM refs
    const asinInput = document.getElementById('asinInput');
    const checkBtn = document.getElementById('checkBtn');
    const statusSection = document.getElementById('statusSection');
    const historySection = document.getElementById('historySection');
    const scrapeToggle = document.getElementById('scrapeToggle');
    const bulkInput = document.getElementById('bulkInput');
    const bulkCheckBtn = document.getElementById('bulkCheckBtn');
    const bulkExportBtn = document.getElementById('bulkExportBtn');
    const bulkStatus = document.getElementById('bulkStatus');
    const bulkResults = document.getElementById('bulkResults');

    let lastBulkAsins = [];

    /**
     * Detect best API URL — prefer local dev server if available, else production.
     */
    async function detectApiUrl() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1500);
            const resp = await fetch(`${API_LOCAL}/health`, { signal: controller.signal });
            clearTimeout(timeoutId);
            if (resp.ok) {
                API_BASE = API_LOCAL;
                console.log('[MRCC Popup] Using local API:', API_LOCAL);
                return;
            }
        } catch {
            // Local not available
        }
        API_BASE = API_PROD;
        console.log('[MRCC Popup] Using production API:', API_PROD);
    }

    // ── History helpers ──────────────────────────────────────────────
    function getHistory() {
        try {
            return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
        } catch {
            return [];
        }
    }

    function saveToHistory(result) {
        const history = getHistory();
        // Remove duplicate
        const idx = history.findIndex(h => h.asin === result.asin);
        if (idx !== -1) history.splice(idx, 1);
        history.unshift({
            asin: result.asin,
            risk_level: result.risk_level,
            average_similarity: result.average_similarity,
            checked_at: new Date().toISOString()
        });
        // Keep last 20
        if (history.length > 20) history.length = 20;
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    }

    // ── Render History ───────────────────────────────────────────────
    function renderHistory() {
        const history = getHistory();
        if (history.length === 0) {
            historySection.innerHTML = `
                <h3>Recent Checks</h3>
                <div class="no-history">No checks yet. Enter an ASIN above to get started.</div>
            `;
            return;
        }

        const items = history.slice(0, 8).map(h => {
            const rClass = h.risk_level.toLowerCase();
            const icon = RISK_ICONS[h.risk_level] || '❓';
            const pct = (h.average_similarity * 100).toFixed(0);
            return `
                <div class="history-item" data-asin="${h.asin}">
                    <span class="h-icon">${icon}</span>
                    <span class="h-asin">${h.asin}</span>
                    <span class="h-risk ${rClass}">${h.risk_level}</span>
                    <span class="h-score">${pct}%</span>
                </div>
            `;
        }).join('');

        historySection.innerHTML = `
            <h3>
                Recent Checks
                <button class="clear-btn" id="clearHistoryBtn">Clear</button>
            </h3>
            ${items}
        `;

        // Clear button
        const clearBtn = document.getElementById('clearHistoryBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                localStorage.removeItem(HISTORY_KEY);
                renderHistory();
            });
        }

        // Click history item to re-check
        historySection.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => {
                const asin = item.dataset.asin;
                asinInput.value = asin;
                runCheck(asin);
            });
        });
    }

    // ── Run Check ────────────────────────────────────────────────────
    async function runCheck(asin) {
        asin = asin.trim().toUpperCase();
        if (!/^[A-Z0-9]{10}$/.test(asin)) {
            showStatus('error', 'Invalid ASIN format. Must be exactly 10 alphanumeric characters.');
            return;
        }

        const scrape = scrapeToggle && scrapeToggle.checked ? '&scrape=true' : '';
        showStatus('loading', `Checking ${asin} across 9 regions…`);
        checkBtn.disabled = true;

        try {
            const resp = await fetch(`${API_BASE}/check?asin=${asin}${scrape}`);
            if (!resp.ok) {
                throw new Error(`API returned ${resp.status}`);
            }
            const result = await resp.json();
            saveToHistory(result);
            showResult(result);
            renderHistory();
        } catch (err) {
            showStatus('error', `Failed: ${err.message}`);
        } finally {
            checkBtn.disabled = false;
        }
    }

    // ── Show Status ──────────────────────────────────────────────────
    function showStatus(type, message) {
        statusSection.style.display = 'block';
        if (type === 'loading') {
            statusSection.innerHTML = `<div class="status-msg"><span class="loading-spinner"></span>${message}</div>`;
        } else if (type === 'error') {
            statusSection.innerHTML = `<div class="status-msg error">${message}</div>`;
        }
    }

    function showResult(result) {
        statusSection.style.display = 'block';
        const rClass = result.risk_level.toLowerCase();
        const icon = RISK_ICONS[result.risk_level] || '❓';
        const pct = (result.average_similarity * 100).toFixed(1);
        const pairs = result.comparisons ? result.comparisons.length : '—';

        statusSection.innerHTML = `
            <div class="status-card risk-${rClass}">
                <div class="status-icon">${icon}</div>
                <div class="status-info">
                    <div class="risk-label ${rClass}">${result.risk_level} Risk</div>
                    <div class="asin-text">ASIN: ${result.asin} · ${pairs} comparisons</div>
                    <div class="score-text">Average Similarity: ${pct}%</div>
                </div>
            </div>
        `;
    }

    // ── Events ───────────────────────────────────────────────────────
    checkBtn.addEventListener('click', () => {
        runCheck(asinInput.value);
    });

    asinInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            runCheck(asinInput.value);
        }
    });

    // Auto-uppercase
    asinInput.addEventListener('input', () => {
        asinInput.value = asinInput.value.toUpperCase();
    });

    // ── Tab switching ────────────────────────────────────────────────
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            this.classList.add('active');
            const pane = document.getElementById('tab-' + this.dataset.tab);
            if (pane) pane.classList.add('active');
        });
    });

    // ── Bulk Check ───────────────────────────────────────────────────
    if (bulkCheckBtn) {
        bulkCheckBtn.addEventListener('click', async () => {
            const raw = bulkInput.value.trim();
            if (!raw) return;
            const asins = raw.split(/[\n,]+/).map(a => a.trim().toUpperCase()).filter(a => /^[A-Z0-9]{10}$/.test(a));
            if (asins.length === 0) {
                bulkStatus.style.display = 'block';
                bulkStatus.innerHTML = '<div class="status-msg error">No valid ASINs found. Each must be 10 alphanumeric characters.</div>';
                return;
            }
            if (asins.length > 50) {
                bulkStatus.style.display = 'block';
                bulkStatus.innerHTML = '<div class="status-msg error">Maximum 50 ASINs allowed.</div>';
                return;
            }

            lastBulkAsins = asins;
            bulkCheckBtn.disabled = true;
            bulkExportBtn.disabled = true;
            bulkStatus.style.display = 'block';
            bulkStatus.innerHTML = `<div class="status-msg"><span class="loading-spinner"></span>Checking ${asins.length} ASINs…</div>`;
            bulkResults.innerHTML = '';

            try {
                const resp = await fetch(`${API_BASE}/bulk-check`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ asins }),
                });
                if (!resp.ok) throw new Error(`API returned ${resp.status}`);
                const data = await resp.json();
                bulkStatus.style.display = 'none';
                bulkExportBtn.disabled = false;

                if (data.results && data.results.length > 0) {
                    const rows = data.results.map(r => {
                        const rc = r.risk_level.toLowerCase();
                        const pct = (r.average_similarity * 100).toFixed(0);
                        return `<tr><td style="font-family:monospace;font-weight:600;">${r.asin}</td><td><span class="b-risk ${rc}">${r.risk_level}</span></td><td>${pct}%</td></tr>`;
                    }).join('');
                    bulkResults.innerHTML = `<table><thead><tr><th>ASIN</th><th>Risk</th><th>Score</th></tr></thead><tbody>${rows}</tbody></table>`;
                    data.results.forEach(r => saveToHistory(r));
                    renderHistory();
                }
            } catch (err) {
                bulkStatus.style.display = 'block';
                bulkStatus.innerHTML = `<div class="status-msg error">Bulk check failed: ${err.message}</div>`;
            } finally {
                bulkCheckBtn.disabled = false;
            }
        });
    }

    // Bulk Export CSV
    if (bulkExportBtn) {
        bulkExportBtn.addEventListener('click', async () => {
            if (lastBulkAsins.length === 0) return;
            try {
                const resp = await fetch(`${API_BASE}/bulk-check/csv`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ asins: lastBulkAsins }),
                });
                if (!resp.ok) throw new Error('Export failed');
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'bulk-check-results.csv';
                a.click();
                URL.revokeObjectURL(url);
            } catch (err) {
                alert('CSV export failed: ' + err.message);
            }
        });
    }

    // ── Init ─────────────────────────────────────────────────────────
    detectApiUrl().then(() => {
        renderHistory();
    });
})();

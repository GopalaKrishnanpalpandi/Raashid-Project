/**
 * Multi-Region Description Consistency Checker
 * Chrome Extension Content Script - Enhanced UI Version
 * 
 * Features:
 * - Animated floating badge with pulse effect
 * - Glassmorphism modal design
 * - Detailed metrics visualization
 * - Smooth animations and transitions
 */

(function() {
    'use strict';

    // Configuration
    const API_BASE_URL = 'https://raashid-project-production.up.railway.app';
    const BADGE_ID = 'mrcc-consistency-badge';
    const MODAL_ID = 'mrcc-details-modal';
    const OVERLAY_ID = 'mrcc-modal-overlay';

    // ASIN Detection Patterns
    const ASIN_PATTERNS = [
        /ASIN[:\s]+([A-Z0-9]{10})/i,
        /\/dp\/([A-Z0-9]{10})/i,
        /\/gp\/product\/([A-Z0-9]{10})/i,
        /\/exec\/obidos\/asin\/([A-Z0-9]{10})/i,
        /\/product\/([A-Z0-9]{10})/i,
        /data-asin="([A-Z0-9]{10})"/i
    ];

    // Store the current result
    let currentResult = null;
    let currentASIN = null;

    /**
     * Listen for manual ASIN search from page
     */
    window.addEventListener('message', async function(event) {
        if (event.data && event.data.type === 'MRCC_SEARCH_ASIN') {
            const asin = event.data.asin;
            if (asin && /^[A-Z0-9]{10}$/.test(asin)) {
                currentASIN = asin;
                const result = await checkConsistency(asin);
                if (result) {
                    currentResult = result;
                    createBadge(result);
                }
            }
        }
    });

    /**
     * Inject CSS styles for the enhanced UI
     */
    function injectStyles() {
        if (document.getElementById('mrcc-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'mrcc-styles';
        styles.textContent = `
            /* ========== FLOATING BADGE ========== */
            #${BADGE_ID} {
                position: fixed;
                top: 140px;
                right: 20px;
                z-index: 2147483647;
                padding: 10px 14px;
                border-radius: 8px;
                font-family: "Amazon Ember", Arial, sans-serif;
                font-size: 13px;
                color: #0F1111;
                background: #fff;
                border: 1px solid #D5D9D9;
                box-shadow: 0 2px 5px rgba(213,217,217,.5);
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 10px;
                transition: all 0.1s ease-in;
            }

            #${BADGE_ID}:hover {
                background-color: #F7FAFA;
                border-color: #D5D9D9;
                box-shadow: 0 2px 5px rgba(213,217,217,.5);
            }

            #${BADGE_ID} .badge-icon {
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
                border-radius: 50%;
            }

            #${BADGE_ID}.risk-low .badge-icon { color: #007600; background: #e6f4e6; }
            #${BADGE_ID}.risk-medium .badge-icon { color: #C45500; background: #fff4e5; }
            #${BADGE_ID}.risk-high .badge-icon { color: #B12704; background: #fbe9e7; }

            #${BADGE_ID} .badge-content {
                display: flex;
                flex-direction: column;
                line-height: 1.2;
            }

            #${BADGE_ID} .badge-title {
                font-size: 11px;
                color: #565959;
            }

            #${BADGE_ID} .badge-value {
                font-weight: 700;
                font-size: 13px;
            }

            #${BADGE_ID} .badge-score {
                font-size: 11px;
                color: #565959;
            }

            #${BADGE_ID} .badge-arrow {
                color: #565959;
                font-size: 12px;
                margin-left: 4px;
            }

            /* ========== MODAL OVERLAY ========== */
            #${OVERLAY_ID} {
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 2147483646;
            }

            /* ========== MODAL ========== */
            #${MODAL_ID} {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                z-index: 2147483647;
                background: #fff;
                width: 600px;
                max-width: 90%;
                max-height: 90vh;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                font-family: "Amazon Ember", Arial, sans-serif;
                display: flex;
                flex-direction: column;
            }

            #${MODAL_ID} .modal-header {
                padding: 16px 24px;
                background: #f0f2f2;
                border-bottom: 1px solid #D5D9D9;
                border-radius: 8px 8px 0 0;
            }

            #${MODAL_ID} .modal-header-content {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            #${MODAL_ID} .modal-title {
                font-size: 16px;
                font-weight: 700;
                color: #0F1111;
                margin: 0;
            }

            #${MODAL_ID} .modal-close {
                background: none;
                border: none;
                font-size: 24px;
                color: #565959;
                cursor: pointer;
                padding: 0;
                line-height: 1;
            }

            #${MODAL_ID} .modal-close:hover {
                color: #0F1111;
            }

            #${MODAL_ID} .modal-body {
                padding: 24px;
                overflow-y: auto;
            }

            /* Risk Banner */
            #${MODAL_ID} .risk-banner {
                padding: 16px;
                border-radius: 4px;
                border: 1px solid;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            #${MODAL_ID} .risk-banner.low {
                background-color: #f0f8f0;
                border-color: #007600;
            }
            #${MODAL_ID} .risk-banner.medium {
                background-color: #fff4e5;
                border-color: #C45500;
            }
            #${MODAL_ID} .risk-banner.high {
                background-color: #fbe9e7;
                border-color: #B12704;
            }

            #${MODAL_ID} .risk-info h3 {
                margin: 0 0 4px 0;
                font-size: 16px;
                font-weight: 700;
            }

            #${MODAL_ID} .risk-banner.low h3 { color: #007600; }
            #${MODAL_ID} .risk-banner.medium h3 { color: #C45500; }
            #${MODAL_ID} .risk-banner.high h3 { color: #B12704; }

            #${MODAL_ID} .risk-info p {
                margin: 0;
                font-size: 13px;
                color: #0F1111;
            }

            #${MODAL_ID} .risk-score-value {
                font-size: 24px;
                font-weight: 700;
                color: #0F1111;
            }

            /* Info Grid */
            #${MODAL_ID} .info-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
                margin-bottom: 24px;
                border: 1px solid #D5D9D9;
                border-radius: 4px;
                padding: 16px;
            }

            #${MODAL_ID} .info-card-label {
                font-size: 12px;
                color: #565959;
                margin-bottom: 2px;
            }

            #${MODAL_ID} .info-card-value {
                font-size: 14px;
                color: #0F1111;
                font-weight: 700;
            }

            /* Section Title */
            #${MODAL_ID} .section-title {
                font-size: 18px;
                font-weight: 700;
                color: #0F1111;
                margin-bottom: 12px;
                padding-bottom: 8px;
                border-bottom: 1px solid #D5D9D9;
            }

            /* Comparison Cards */
            #${MODAL_ID} .comparison-card {
                border: 1px solid #D5D9D9;
                border-radius: 4px;
                padding: 16px;
                margin-bottom: 12px;
            }

            #${MODAL_ID} .comparison-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }

            #${MODAL_ID} .region-badge {
                font-weight: 700;
                color: #0F1111;
            }

            #${MODAL_ID} .comparison-score {
                font-weight: 700;
                font-size: 14px;
            }
            #${MODAL_ID} .comparison-score.high { color: #007600; }
            #${MODAL_ID} .comparison-score.medium { color: #C45500; }
            #${MODAL_ID} .comparison-score.low { color: #B12704; }

            /* Metrics */
            #${MODAL_ID} .metrics-grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 12px;
            }

            #${MODAL_ID} .metric-bar-container {
                height: 6px;
                background: #e7e7e7;
                border-radius: 3px;
                margin-bottom: 4px;
            }

            #${MODAL_ID} .metric-bar {
                height: 100%;
                border-radius: 3px;
                background: #007185;
            }

            #${MODAL_ID} .metric-label {
                font-size: 11px;
                color: #565959;
            }

            #${MODAL_ID} .metric-value {
                font-size: 13px;
                font-weight: 700;
                color: #0F1111;
            }

            /* Footer */
            #${MODAL_ID} .modal-footer {
                padding: 16px 24px;
                border-top: 1px solid #D5D9D9;
                background: #fcfcfc;
                border-radius: 0 0 8px 8px;
                text-align: right;
            }

            #${MODAL_ID} .footer-btn {
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 13px;
                cursor: pointer;
                border: 1px solid;
                box-shadow: 0 2px 5px rgba(213,217,217,.5);
            }

            #${MODAL_ID} .footer-btn.secondary {
                background: #fff;
                border-color: #D5D9D9;
                color: #0F1111;
            }

            #${MODAL_ID} .footer-btn.secondary:hover {
                background: #F7FAFA;
            }

            /* Title Mismatch Section */
            #${MODAL_ID} .title-mismatch-section {
                margin-bottom: 20px;
                border: 1px solid #B12704;
                border-radius: 4px;
                overflow: hidden;
            }

            #${MODAL_ID} .mismatch-alert-header {
                background-color: #fbe9e7;
                padding: 10px 16px;
                display: flex;
                align-items: center;
                gap: 10px;
                border-bottom: 1px solid #B12704;
            }

            #${MODAL_ID} .mismatch-alert-header h4 {
                color: #B12704;
                font-size: 14px;
                font-weight: 700;
                margin: 0;
            }

            #${MODAL_ID} .mismatch-list {
                background-color: #fff;
            }

            #${MODAL_ID} .mismatch-item {
                padding: 12px 16px;
                border-bottom: 1px solid #D5D9D9;
            }

            #${MODAL_ID} .mismatch-item:last-child {
                border-bottom: none;
            }

            #${MODAL_ID} .mismatch-header {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
            }

            #${MODAL_ID} .mismatch-score {
                font-size: 12px;
                font-weight: 700;
                color: #B12704;
                background: #fbe9e7;
                padding: 2px 6px;
                border-radius: 4px;
                margin-left: auto;
            }

            #${MODAL_ID} .mismatch-titles {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }

            #${MODAL_ID} .mismatch-title-row {
                display: flex;
                gap: 8px;
                font-size: 13px;
                align-items: baseline;
            }

            #${MODAL_ID} .region-label {
                font-weight: 700;
                color: #565959;
                min-width: 30px;
            }
            
            #${MODAL_ID} .title-text {
                color: #0F1111;
            }

            /* Diff Styles */
            #${MODAL_ID} .diff-content {
                margin-top: 8px;
                padding: 8px;
                background: #f8f9fa;
                border-radius: 4px;
                font-size: 13px;
                line-height: 1.5;
            }
            
            #${MODAL_ID} .diff-label {
                font-size: 11px;
                color: #565959;
                margin-bottom: 4px;
                font-weight: 700;
                text-transform: uppercase;
            }

            #${MODAL_ID} .diff-text span {
                padding: 2px 0;
                border-radius: 2px;
            }

            #${MODAL_ID} .diff-insert {
                background-color: #e6ffec;
                color: #007600;
                text-decoration: none;
                padding: 0 2px !important;
                border: 1px solid #b7ebc3;
            }

            #${MODAL_ID} .diff-delete {
                background-color: #ffebe9;
                color: #cf222e;
                text-decoration: line-through;
                padding: 0 2px !important;
                border: 1px solid #ffc1c0;
            }
        `;
        document.head.appendChild(styles);
    }

    /**
     * Detect ASIN from page URL or content
     */
    function detectASIN() {
        // First, try to find ASIN in URL
        const url = window.location.href;
        for (const pattern of ASIN_PATTERNS) {
            const match = url.match(pattern);
            if (match && match[1]) {
                return match[1].toUpperCase();
            }
        }

        // Then, try to find in page content
        const pageHTML = document.documentElement.innerHTML;
        for (const pattern of ASIN_PATTERNS) {
            const match = pageHTML.match(pattern);
            if (match && match[1]) {
                return match[1].toUpperCase();
            }
        }

        // Finally, look for visible text containing "ASIN:"
        const bodyText = document.body ? document.body.innerText : '';
        const asinTextMatch = bodyText.match(/ASIN[:\s]+([A-Z0-9]{10})/i);
        if (asinTextMatch && asinTextMatch[1]) {
            return asinTextMatch[1].toUpperCase();
        }

        return null;
    }

    /**
     * Call backend API to check consistency
     */
    async function checkConsistency(asin) {
        try {
            const response = await fetch(`${API_BASE_URL}/check?asin=${asin}`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('[MRCC] API call failed:', error);
            return null;
        }
    }

    /**
     * Get icon based on risk level
     */
    function getRiskIcon(riskLevel) {
        switch (riskLevel) {
            case 'LOW': return '✓';
            case 'MEDIUM': return '⚠';
            case 'HIGH': return '✗';
            default: return '?';
        }
    }

    /**
     * Get risk description
     */
    function getRiskDescription(riskLevel) {
        switch (riskLevel) {
            case 'LOW': return 'Descriptions are consistent across regions';
            case 'MEDIUM': return 'Some differences detected, review recommended';
            case 'HIGH': return 'Significant discrepancies found!';
            default: return 'Unknown status';
        }
    }

    /**
     * Create and display the floating badge
     */
    function createBadge(result) {
        const existingBadge = document.getElementById(BADGE_ID);
        if (existingBadge) {
            existingBadge.remove();
        }

        const badge = document.createElement('div');
        badge.id = BADGE_ID;
        badge.className = `risk-${result.risk_level.toLowerCase()}`;
        
        const scorePercent = (result.average_similarity * 100).toFixed(0);
        
        badge.innerHTML = `
            <div class="badge-icon">${getRiskIcon(result.risk_level)}</div>
            <div class="badge-content">
                <span class="badge-title">Description Variance</span>
                <span class="badge-value">${result.risk_level}</span>
                <span class="badge-score">${scorePercent}% similarity</span>
            </div>
            <span class="badge-arrow">→</span>
        `;

        badge.addEventListener('click', () => showDetailsModal(result));
        document.body.appendChild(badge);
    }

    /**
     * Get score class based on similarity value
     */
    function getScoreClass(score) {
        if (score >= 0.75) return 'high';
        if (score >= 0.45) return 'medium';
        return 'low';
    }

    /**
     * Show detailed comparison modal
     */
    function showDetailsModal(result) {
        closeModal();

        // Create overlay
        const overlay = document.createElement('div');
        overlay.id = OVERLAY_ID;
        overlay.addEventListener('click', closeModal);
        document.body.appendChild(overlay);

        // Create modal
        const modal = document.createElement('div');
        modal.id = MODAL_ID;

        const riskClass = result.risk_level.toLowerCase();
        const avgScore = (result.average_similarity * 100).toFixed(1);
        const minScore = ((result.min_similarity || result.average_similarity) * 100).toFixed(1);
        const maxScore = ((result.max_similarity || result.average_similarity) * 100).toFixed(1);

        const comparisonsHTML = result.comparisons.map(comp => {
            const scorePercent = (comp.similarity_score * 100).toFixed(1);
            const scoreClass = getScoreClass(comp.similarity_score);
            
            // Detailed metrics for complex analysis
            const tfidf = ((comp.tfidf_score !== undefined ? comp.tfidf_score : comp.similarity_score) * 100).toFixed(0);
            const jaccard = ((comp.jaccard_score !== undefined ? comp.jaccard_score : comp.similarity_score) * 100).toFixed(0);
            const sequence = ((comp.sequence_score !== undefined ? comp.sequence_score : comp.similarity_score) * 100).toFixed(0);
            const features = ((comp.feature_overlap !== undefined ? comp.feature_overlap : 1) * 100).toFixed(0);

            return `
                <div class="comparison-card">
                    <div class="comparison-header">
                        <div class="comparison-regions">
                            <span class="region-badge">${comp.region_1} vs ${comp.region_2}</span>
                        </div>
                        <span class="comparison-score ${scoreClass}">${scorePercent}% Match</span>
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-item">
                            <div class="metric-bar-container">
                                <div class="metric-bar" style="width: ${tfidf}%"></div>
                            </div>
                            <div class="metric-label">Keywords (TF-IDF)</div>
                            <div class="metric-value">${tfidf}%</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-bar-container">
                                <div class="metric-bar" style="width: ${jaccard}%"></div>
                            </div>
                            <div class="metric-label">Content (Jaccard)</div>
                            <div class="metric-value">${jaccard}%</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-bar-container">
                                <div class="metric-bar" style="width: ${sequence}%"></div>
                            </div>
                            <div class="metric-label">Structure (Seq)</div>
                            <div class="metric-value">${sequence}%</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-bar-container">
                                <div class="metric-bar" style="width: ${features}%"></div>
                            </div>
                            <div class="metric-label">Specs (Features)</div>
                            <div class="metric-value">${features}%</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        let titleAnalysisHTML = '';
        if (result.title_analysis) {
            if (result.title_analysis.is_mismatch) {
                const mismatches = result.title_analysis.mismatches.map(m => {
                    const score = (m.similarity * 100).toFixed(0);
                    
                    // Generate diff HTML if available
                    let diffHTML = '';
                    if (m.diff) {
                        const diffSpans = m.diff.map(part => {
                            if (part.type === 'equal') return `<span>${part.text}</span>`;
                            if (part.type === 'insert') return `<span class="diff-insert" title="Added in ${m.region_2}">${part.text}</span>`;
                            if (part.type === 'delete') return `<span class="diff-delete" title="Removed from ${m.region_1}">${part.text}</span>`;
                            return '';
                        }).join(' ');
                        
                        diffHTML = `
                            <div class="diff-content">
                                <div class="diff-label">Difference Analysis (${m.region_1} → ${m.region_2})</div>
                                <div class="diff-text">${diffSpans}</div>
                            </div>
                        `;
                    }

                    return `
                        <div class="mismatch-item">
                            <div class="mismatch-header">
                                <span class="region-badge">${m.region_1} vs ${m.region_2}</span>
                                <span class="mismatch-score">${score}% Match</span>
                            </div>
                            <div class="mismatch-titles">
                                <div class="mismatch-title-row">
                                    <span class="region-label">${m.region_1}:</span>
                                    <span class="title-text">${m.title_1}</span>
                                </div>
                                <div class="mismatch-title-row">
                                    <span class="region-label">${m.region_2}:</span>
                                    <span class="title-text">${m.title_2}</span>
                                </div>
                            </div>
                            ${diffHTML}
                        </div>
                    `;
                }).join('');

                titleAnalysisHTML = `
                    <div class="title-mismatch-section">
                        <div class="mismatch-alert-header">
                            <span class="alert-icon">⚠️</span>
                            <h4>Title Inconsistencies Detected</h4>
                        </div>
                        <div class="mismatch-list">
                            ${mismatches}
                        </div>
                    </div>
                `;
            } else {
                // Consistent titles
                titleAnalysisHTML = `
                    <div class="title-mismatch-section" style="border-color: #007600;">
                        <div class="mismatch-alert-header" style="background-color: #f0f8f0; border-bottom-color: #007600;">
                            <span class="alert-icon">✓</span>
                            <h4 style="color: #007600;">Product Titles are Consistent</h4>
                        </div>
                        <div class="mismatch-list" style="padding: 12px 16px; font-size: 13px; color: #565959;">
                            Titles match across all analyzed regions.
                        </div>
                    </div>
                `;
            }
        }

        modal.innerHTML = `
            <div class="modal-header">
                <div class="modal-header-content">
                    <h2 class="modal-title">Description Consistency Report</h2>
                    <button class="modal-close" aria-label="Close">×</button>
                </div>
            </div>
            
            <div class="modal-body">
                <div class="risk-banner ${riskClass}">
                    <div class="risk-info">
                        <h3>${result.risk_level} RISK</h3>
                        <p>${getRiskDescription(result.risk_level)}</p>
                    </div>
                    <div class="risk-score-value">${avgScore}%</div>
                </div>

                <div class="info-grid">
                    <div class="info-card-label">ASIN</div>
                    <div class="info-card-value">${result.asin}</div>
                    
                    <div class="info-card-label">Regions Analyzed</div>
                    <div class="info-card-value">${result.regions_analyzed.join(', ')}</div>
                    
                    <div class="info-card-label">Score Range</div>
                    <div class="info-card-value">${minScore}% — ${maxScore}%</div>
                    
                    <div class="info-card-label">Confidence</div>
                    <div class="info-card-value">${result.confidence || 'MEDIUM'}</div>
                </div>

                ${titleAnalysisHTML}

                <div class="section-title">Regional Comparisons</div>
                ${comparisonsHTML}
            </div>

            <div class="modal-footer">
                <button class="footer-btn secondary" onclick="document.getElementById('${MODAL_ID}').querySelector('.modal-close').click()">Close</button>
            </div>
        `;

        modal.querySelector('.modal-close').addEventListener('click', closeModal);
        document.body.appendChild(modal);
        document.addEventListener('keydown', handleEscapeKey);
    }

    /**
     * Close the modal
     */
    function closeModal() {
        const modal = document.getElementById(MODAL_ID);
        const overlay = document.getElementById(OVERLAY_ID);
        if (modal) modal.remove();
        if (overlay) overlay.remove();
        document.removeEventListener('keydown', handleEscapeKey);
    }

    /**
     * Handle Escape key to close modal
     */
    function handleEscapeKey(event) {
        if (event.key === 'Escape') {
            closeModal();
        }
    }

    /**
     * Main initialization function
     */
    async function init() {
        // Inject styles
        injectStyles();

        // Detect ASIN
        const asin = detectASIN();
        if (!asin) {
            console.log('[MRCC] No ASIN detected on this page');
            return;
        }

        console.log(`[MRCC] Detected ASIN: ${asin}`);

        // Check consistency via API
        const result = await checkConsistency(asin);
        if (!result) {
            console.log('[MRCC] Failed to get consistency data');
            return;
        }

        console.log('[MRCC] Consistency result:', result);
        currentResult = result;

        // Create and display badge
        createBadge(result);
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

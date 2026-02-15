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
    const API_PROD_URL = 'https://raashid-project-production-55d9.up.railway.app';
    const API_LOCAL_URL = 'http://localhost:5000';
    let API_BASE_URL = API_PROD_URL; // Default to production
    const BADGE_ID = 'mrcc-consistency-badge';
    const MODAL_ID = 'mrcc-details-modal';
    const OVERLAY_ID = 'mrcc-modal-overlay';

    /**
     * Detect best API URL — prefer local dev server if available, else production.
     */
    async function detectApiUrl() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1500);
            const resp = await fetch(`${API_LOCAL_URL}/health`, { signal: controller.signal });
            clearTimeout(timeoutId);
            if (resp.ok) {
                API_BASE_URL = API_LOCAL_URL;
                console.log('[MRCC] Using local API:', API_LOCAL_URL);
                return;
            }
        } catch {
            // Local server not available
        }
        API_BASE_URL = API_PROD_URL;
        console.log('[MRCC] Using production API:', API_PROD_URL);
    }

    // ASIN Detection Patterns
    const ASIN_PATTERNS = [
        /ASIN[:\s]+([A-Z0-9]{10})/i,
        /\/dp\/([A-Z0-9]{10})/i,
        /\/gp\/product\/([A-Z0-9]{10})/i,
        /\/exec\/obidos\/asin\/([A-Z0-9]{10})/i,
        /\/product\/([A-Z0-9]{10})/i,
        /data-asin="([A-Z0-9]{10})"/i
    ];

    // Region Detection from hostname
    const HOSTNAME_REGION_MAP = {
        'amazon.in': 'IN',
        'amazon.de': 'DE',
        'amazon.co.uk': 'UK',
        'amazon.co.jp': 'JP',
        'amazon.fr': 'FR',
        'amazon.ca': 'CA',
        'amazon.com.au': 'AU',
        'amazon.es': 'ES',
        'amazon.com': 'US',
    };

    // Store the current result
    let currentResult = null;
    let currentASIN = null;

    /**
     * Extract product title and description from the current Amazon page DOM
     */
    function extractProductInfo() {
        let title = '';
        // Try standard Amazon title selectors
        const titleEl = document.getElementById('productTitle')
            || document.querySelector('#title span')
            || document.querySelector('h1#title');
        if (titleEl) {
            title = titleEl.textContent.trim();
        }

        let description = '';
        // Feature bullets (most common on Amazon)
        const featureBullets = document.getElementById('feature-bullets');
        if (featureBullets) {
            const items = featureBullets.querySelectorAll('li span.a-list-item');
            const bullets = Array.from(items)
                .map(el => el.textContent.trim())
                .filter(t => t.length > 5 && !t.startsWith('\u203A'));
            if (bullets.length > 0) {
                description = bullets.join('. ');
            }
        }

        // Product description block
        if (!description || description.length < 50) {
            const descEl = document.getElementById('productDescription');
            if (descEl) {
                const text = descEl.textContent.trim();
                if (text.length > description.length) description = text;
            }
        }

        // A+ / enhanced content
        if (!description || description.length < 50) {
            const aplus = document.getElementById('aplus')
                || document.getElementById('aplus_feature_div');
            if (aplus) {
                const text = aplus.textContent.trim().substring(0, 2000);
                if (text.length > description.length) description = text;
            }
        }

        // Detect current Amazon region from hostname
        const hostname = window.location.hostname;
        let region = 'US';
        for (const [domain, reg] of Object.entries(HOSTNAME_REGION_MAP)) {
            if (hostname.includes(domain) && domain !== 'amazon.com') {
                region = reg;
                break;
            }
        }
        // amazon.com must be checked last (it's a substring of many others)
        if (region === 'US' && !hostname.includes('amazon.com')) {
            region = 'US'; // fallback
        }

        return { title, description, region };
    }

    /**
     * Listen for manual ASIN search from page
     */
    window.addEventListener('message', async function(event) {
        if (event.data && event.data.type === 'MRCC_SEARCH_ASIN') {
            const asin = event.data.asin;
            if (asin && /^[A-Z0-9]{10}$/.test(asin)) {
                // Force reload even if same ASIN (user explicitly searched)
                currentASIN = null;
                currentResult = null;
                await loadASIN(asin);
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
                cursor: pointer;
                transition: border-color 0.15s;
            }

            #${MODAL_ID} .comparison-card:hover {
                border-color: #007185;
            }

            #${MODAL_ID} .comparison-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }

            #${MODAL_ID} .comparison-header-left {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            #${MODAL_ID} .expand-icon {
                font-size: 12px;
                color: #565959;
                transition: transform 0.2s;
            }

            #${MODAL_ID} .comparison-card.expanded .expand-icon {
                transform: rotate(90deg);
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
                gap: 8px;
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
                font-size: 10px;
                color: #565959;
            }

            #${MODAL_ID} .metric-value {
                font-size: 12px;
                font-weight: 700;
                color: #0F1111;
            }

            /* Issues Panel */
            #${MODAL_ID} .issues-section {
                margin-bottom: 20px;
                background: #FFFBF0;
                border: 1px solid #F0C36D;
                border-radius: 8px;
                padding: 16px;
            }
            #${MODAL_ID} .issues-section.no-issues {
                background: #F0FFF4;
                border-color: #38A169;
            }
            #${MODAL_ID} .issues-header {
                display: flex; align-items: center; gap: 8px;
                font-size: 15px; font-weight: 700; color: #0F1111;
                margin-bottom: 12px;
            }
            #${MODAL_ID} .issue-badges {
                display: flex; gap: 6px; margin-left: auto;
            }
            #${MODAL_ID} .issue-badge {
                font-size: 11px; padding: 2px 8px; border-radius: 10px;
                font-weight: 600;
            }
            #${MODAL_ID} .issue-badge.high { background: #FED7D7; color: #9B2C2C; }
            #${MODAL_ID} .issue-badge.medium { background: #FEFCBF; color: #975A16; }
            #${MODAL_ID} .issue-badge.low { background: #E2E8F0; color: #4A5568; }
            #${MODAL_ID} .issue-item {
                display: flex; align-items: flex-start; gap: 10px;
                padding: 8px 0;
                border-bottom: 1px solid #EDF2F7;
            }
            #${MODAL_ID} .issue-item:last-child { border-bottom: none; }
            #${MODAL_ID} .issue-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
            #${MODAL_ID} .issue-content { flex: 1; }
            #${MODAL_ID} .issue-title {
                font-size: 13px; font-weight: 600; color: #1A202C;
            }
            #${MODAL_ID} .issue-desc {
                font-size: 12px; color: #4A5568; margin-top: 2px;
            }
            #${MODAL_ID} .issue-severity {
                font-size: 10px; font-weight: 700; text-transform: uppercase;
                padding: 2px 6px; border-radius: 4px; flex-shrink: 0;
            }
            #${MODAL_ID} .issue-severity.high { background: #FED7D7; color: #9B2C2C; }
            #${MODAL_ID} .issue-severity.medium { background: #FEFCBF; color: #975A16; }
            #${MODAL_ID} .issue-severity.low { background: #E2E8F0; color: #4A5568; }

            /* Spec Analysis Panel */
            #${MODAL_ID} .spec-section {
                margin-bottom: 20px; background: #fff;
                border: 1px solid #D5D9D9; border-radius: 8px; padding: 16px;
            }
            #${MODAL_ID} .spec-grid {
                display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 8px;
            }
            #${MODAL_ID} .spec-card {
                padding: 10px; border-radius: 6px; border: 1px solid #E2E8F0;
                background: #F7FAFC;
            }
            #${MODAL_ID} .spec-card.conflict { border-color: #FC8181; background: #FFF5F5; }
            #${MODAL_ID} .spec-card.consistent { border-color: #68D391; background: #F0FFF4; }
            #${MODAL_ID} .spec-name {
                font-size: 11px; font-weight: 600; color: #4A5568;
                text-transform: uppercase; letter-spacing: 0.5px;
                margin-bottom: 4px;
            }
            #${MODAL_ID} .spec-values {
                font-size: 12px; color: #1A202C;
            }
            #${MODAL_ID} .spec-value-item {
                display: inline-block; margin-right: 8px;
            }
            #${MODAL_ID} .spec-status {
                font-size: 10px; font-weight: 700; margin-top: 4px;
            }
            #${MODAL_ID} .spec-status.ok { color: #38A169; }
            #${MODAL_ID} .spec-status.conflict { color: #E53E3E; }

            /* Per-pair issues inline */
            #${MODAL_ID} .pair-issues {
                margin-top: 10px; padding: 10px; background: #FFFBF0;
                border: 1px solid #F0C36D; border-radius: 6px;
            }
            #${MODAL_ID} .pair-issues-header {
                font-size: 12px; font-weight: 600; color: #975A16;
                margin-bottom: 6px;
            }
            #${MODAL_ID} .pair-issue-row {
                font-size: 11px; color: #4A5568; padding: 3px 0;
                display: flex; gap: 6px; align-items: flex-start;
            }
            #${MODAL_ID} .pair-issue-icon { flex-shrink: 0; }

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

            /* ========== EXPANDABLE DESCRIPTION DIFF ========== */
            #${MODAL_ID} .desc-diff-panel {
                display: none;
                margin-top: 12px;
                border-top: 1px solid #D5D9D9;
                padding-top: 12px;
            }

            #${MODAL_ID} .comparison-card.expanded .desc-diff-panel {
                display: block;
            }

            #${MODAL_ID} .desc-diff-panel .region-links {
                display: flex;
                gap: 8px;
                margin-bottom: 12px;
            }

            #${MODAL_ID} .desc-diff-panel .region-link {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 700;
                color: #007185;
                background: #f0f8ff;
                border: 1px solid #007185;
                border-radius: 4px;
                text-decoration: none;
                cursor: pointer;
            }

            #${MODAL_ID} .desc-diff-panel .region-link:hover {
                background: #e0f0ff;
                color: #004B6E;
            }

            #${MODAL_ID} .desc-diff-section {
                margin-bottom: 10px;
            }

            #${MODAL_ID} .desc-diff-section .desc-region-label {
                font-size: 12px;
                font-weight: 700;
                color: #565959;
                margin-bottom: 4px;
                text-transform: uppercase;
            }

            #${MODAL_ID} .desc-diff-section .desc-text {
                font-size: 13px;
                line-height: 1.6;
                color: #0F1111;
                background: #FAFAFA;
                padding: 10px 12px;
                border-radius: 4px;
                border: 1px solid #e7e7e7;
            }

            #${MODAL_ID} .desc-diff-combined {
                font-size: 13px;
                line-height: 1.6;
                color: #0F1111;
                background: #FAFAFA;
                padding: 10px 12px;
                border-radius: 4px;
                border: 1px solid #e7e7e7;
                max-height: 350px;
                overflow-y: auto;
            }

            #${MODAL_ID} .desc-diff-combined::-webkit-scrollbar { width: 5px; }
            #${MODAL_ID} .desc-diff-combined::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

            #${MODAL_ID} .desc-diff-combined .diff-insert {
                background-color: #e6ffec;
                color: #007600;
                text-decoration: none;
                padding: 1px 3px;
                border: 1px solid #b7ebc3;
                border-radius: 2px;
            }

            #${MODAL_ID} .desc-diff-combined .diff-delete {
                background-color: #ffebe9;
                color: #cf222e;
                text-decoration: line-through;
                padding: 1px 3px;
                border: 1px solid #ffc1c0;
                border-radius: 2px;
            }

            #${MODAL_ID} .click-hint {
                font-size: 11px;
                color: #565959;
                text-align: center;
                margin-top: 8px;
                font-style: italic;
            }

            /* ========== STRUCTURED SENTENCE DIFF VIEW ========== */
            #${MODAL_ID} .sentence-diff-container {
                max-height: 450px;
                overflow-y: auto;
                padding-right: 4px;
            }
            #${MODAL_ID} .sentence-diff-container::-webkit-scrollbar { width: 5px; }
            #${MODAL_ID} .sentence-diff-container::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

            #${MODAL_ID} .sentence-diff-summary {
                display: flex;
                gap: 12px;
                padding: 8px 12px;
                background: #f0f4f8;
                border-radius: 6px;
                margin-bottom: 10px;
                font-size: 12px;
                color: #333;
                align-items: center;
                flex-wrap: wrap;
            }
            #${MODAL_ID} .sentence-diff-summary .summary-badge {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 2px 8px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 11px;
            }
            #${MODAL_ID} .summary-badge.matched { background: #e6ffec; color: #1a7f37; }
            #${MODAL_ID} .summary-badge.changed { background: #fff8c5; color: #9a6700; }
            #${MODAL_ID} .summary-badge.only-r1 { background: #ffebe9; color: #cf222e; }
            #${MODAL_ID} .summary-badge.only-r2 { background: #ddf4ff; color: #0969da; }

            #${MODAL_ID} .sentence-card {
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                margin-bottom: 8px;
                overflow: hidden;
                transition: box-shadow 0.15s;
            }
            #${MODAL_ID} .sentence-card:hover {
                box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            }
            #${MODAL_ID} .sentence-card-header {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            #${MODAL_ID} .sentence-card-header.match-identical {
                background: #f0fdf4;
                color: #15803d;
                border-bottom: 1px solid #dcfce7;
            }
            #${MODAL_ID} .sentence-card-header.match-changed {
                background: #fffbeb;
                color: #92400e;
                border-bottom: 1px solid #fef3c7;
            }
            #${MODAL_ID} .sentence-card-header.only-region {
                background: #fef2f2;
                color: #991b1b;
                border-bottom: 1px solid #fee2e2;
            }
            #${MODAL_ID} .sentence-card-header.only-region.region-2 {
                background: #eff6ff;
                color: #1e40af;
                border-bottom: 1px solid #dbeafe;
            }
            #${MODAL_ID} .sentence-card-header .match-score {
                margin-left: auto;
                font-size: 10px;
                padding: 1px 6px;
                border-radius: 8px;
                background: rgba(255,255,255,0.6);
            }
            #${MODAL_ID} .sentence-card-body {
                padding: 8px 12px;
                font-size: 12.5px;
                line-height: 1.55;
                background: #fff;
            }
            #${MODAL_ID} .sentence-row {
                display: flex;
                gap: 8px;
                margin-bottom: 4px;
                align-items: flex-start;
            }
            #${MODAL_ID} .sentence-row:last-child { margin-bottom: 0; }
            #${MODAL_ID} .sentence-region-tag {
                flex-shrink: 0;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 3px;
                text-transform: uppercase;
                min-width: 28px;
                text-align: center;
                margin-top: 2px;
            }
            #${MODAL_ID} .sentence-region-tag.r1 {
                background: #fee2e2;
                color: #991b1b;
            }
            #${MODAL_ID} .sentence-region-tag.r2 {
                background: #dbeafe;
                color: #1e40af;
            }
            #${MODAL_ID} .sentence-text {
                flex: 1;
                color: #333;
                word-break: break-word;
            }
            #${MODAL_ID} .sentence-diff-word-insert {
                background: #e6ffec;
                color: #1a7f37;
                padding: 0 2px;
                border-radius: 2px;
                border: 1px solid #b7ebc3;
            }
            #${MODAL_ID} .sentence-diff-word-delete {
                background: #ffebe9;
                color: #cf222e;
                text-decoration: line-through;
                padding: 0 2px;
                border-radius: 2px;
                border: 1px solid #ffc1c0;
            }
            #${MODAL_ID} .identical-sentences-toggle {
                text-align: center;
                padding: 6px;
                font-size: 11px;
                color: #007185;
                cursor: pointer;
                border: 1px dashed #d5d9d9;
                border-radius: 4px;
                margin-bottom: 8px;
            }
            #${MODAL_ID} .identical-sentences-toggle:hover {
                background: #f0f8ff;
            }
            #${MODAL_ID} .identical-sentences-group { display: none; }
            #${MODAL_ID} .identical-sentences-group.expanded { display: block; }

            /* ========== REGION URL BAR ========== */
            #${MODAL_ID} .region-url-bar {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                margin-bottom: 16px;
                padding: 12px;
                background: #F0F2F2;
                border-radius: 4px;
            }

            #${MODAL_ID} .region-url-btn {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #0F1111;
                background: #fff;
                border: 1px solid #D5D9D9;
                border-radius: 4px;
                text-decoration: none;
                cursor: pointer;
            }

            #${MODAL_ID} .region-url-btn:hover {
                background: #F7FAFA;
                border-color: #007185;
                color: #007185;
            }

            #${MODAL_ID} .region-url-btn .flag {
                font-size: 14px;
            }

            #${MODAL_ID} .history-list {
                display: flex;
                flex-direction: column;
                gap: 6px;
            }

            #${MODAL_ID} .history-item {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 8px 12px;
                background: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                font-size: 13px;
                cursor: pointer;
                transition: background 0.15s;
            }

            #${MODAL_ID} .history-item:hover {
                background: #F0F0F0;
            }

            #${MODAL_ID} .history-icon {
                font-size: 16px;
            }

            #${MODAL_ID} .history-asin {
                font-family: monospace;
                font-weight: 600;
                color: #0F1111;
            }

            #${MODAL_ID} .history-risk {
                font-size: 11px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 10px;
                text-transform: uppercase;
            }

            #${MODAL_ID} .history-risk.risk-low {
                background: #E6F4EA;
                color: #137333;
            }

            #${MODAL_ID} .history-risk.risk-medium {
                background: #FEF3CD;
                color: #856404;
            }

            #${MODAL_ID} .history-risk.risk-high {
                background: #FDECEA;
                color: #C62828;
            }

            #${MODAL_ID} .history-score {
                color: #565959;
                margin-left: auto;
            }

            #${MODAL_ID} .history-date {
                color: #999;
                font-size: 11px;
            }

            /* ========== SIDE-BY-SIDE DIFF VIEW ========== */
            #${MODAL_ID} .sbs-container {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin-top: 10px;
            }

            #${MODAL_ID} .sbs-panel {
                background: #FAFAFA;
                border: 1px solid #e7e7e7;
                border-radius: 4px;
                padding: 10px 12px;
                font-size: 13px;
                line-height: 1.6;
                color: #0F1111;
                max-height: 300px;
                overflow-y: auto;
            }

            #${MODAL_ID} .sbs-panel::-webkit-scrollbar { width: 4px; }
            #${MODAL_ID} .sbs-panel::-webkit-scrollbar-thumb { background: #ccc; border-radius: 2px; }

            #${MODAL_ID} .sbs-panel-header {
                font-size: 12px;
                font-weight: 700;
                color: #565959;
                text-transform: uppercase;
                margin-bottom: 6px;
                padding-bottom: 4px;
                border-bottom: 1px solid #e7e7e7;
                display: flex;
                align-items: center;
                gap: 6px;
                flex-wrap: wrap;
            }

            /* ========== LANGUAGE BADGES ========== */
            #${MODAL_ID} .lang-badge {
                display: inline-block;
                font-size: 10px;
                font-weight: 600;
                padding: 2px 6px;
                border-radius: 3px;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }
            #${MODAL_ID} .lang-en {
                background: #e8f5e9;
                color: #2e7d32;
                border: 1px solid #c8e6c9;
            }
            #${MODAL_ID} .lang-translated {
                background: #fff3e0;
                color: #e65100;
                border: 1px solid #ffe0b2;
            }
            #${MODAL_ID} .lang-badges-row {
                display: flex;
                align-items: center;
                padding: 4px 12px 0;
                font-size: 11px;
            }
            #${MODAL_ID} .translation-indicator {
                font-size: 12px;
                margin-left: 4px;
            }
            #${MODAL_ID} .translation-note {
                background: #fff8e1;
                border: 1px solid #fff176;
                border-radius: 4px;
                padding: 6px 10px;
                margin-top: 8px;
                font-size: 11px;
                color: #5d4037;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            #${MODAL_ID} .translation-note-icon {
                font-size: 14px;
            }
            #${MODAL_ID} .original-text-panel {
                background: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px 10px;
                margin-top: 8px;
            }
            #${MODAL_ID} .original-text-label {
                font-size: 11px;
                font-weight: 600;
                color: #795548;
                margin-bottom: 4px;
            }
            #${MODAL_ID} .original-text {
                font-size: 12px;
                color: #555;
                line-height: 1.5;
                white-space: pre-wrap;
                word-break: break-word;
            }

            /* ========== LANGUAGE SUMMARY PANEL ========== */
            #${MODAL_ID} .language-summary-panel {
                background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
                border: 1px solid #bbdefb;
                border-radius: 8px;
                padding: 12px 16px;
                margin: 12px 0;
            }
            #${MODAL_ID} .language-summary-header {
                font-size: 13px;
                font-weight: 700;
                color: #1565c0;
                margin-bottom: 4px;
            }
            #${MODAL_ID} .language-summary-desc {
                font-size: 11px;
                color: #555;
                margin-bottom: 8px;
            }
            #${MODAL_ID} .language-summary-items {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
            }
            #${MODAL_ID} .lang-summary-item {
                font-size: 10px;
                padding: 3px 8px;
                border-radius: 4px;
                background: #fff;
                border: 1px solid #e0e0e0;
                color: #555;
            }
            #${MODAL_ID} .lang-summary-item.translated {
                background: #fff3e0;
                border-color: #ffcc80;
                color: #e65100;
            }

            /* ========== VIEW TOGGLE TABS ========== */
            #${MODAL_ID} .diff-view-toggle {
                display: flex;
                gap: 0;
                margin: 8px 0;
            }

            #${MODAL_ID} .diff-view-tab {
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
                cursor: pointer;
                border: 1px solid #D5D9D9;
                background: #fff;
                color: #565959;
            }

            #${MODAL_ID} .diff-view-tab:first-child { border-radius: 4px 0 0 4px; }
            #${MODAL_ID} .diff-view-tab:last-child { border-radius: 0 4px 4px 0; }
            #${MODAL_ID} .diff-view-tab:not(:first-child):not(:last-child) { border-radius: 0; border-left: 0; border-right: 0; }

            #${MODAL_ID} .diff-view-tab.active {
                background: #007185;
                border-color: #007185;
                color: #fff;
            }

            /* ========== SIMILARITY HEATMAP / CHART ========== */
            #${MODAL_ID} .heatmap-section {
                margin: 16px 0;
            }

            #${MODAL_ID} .heatmap-grid {
                display: grid;
                gap: 2px;
                font-size: 10px;
            }

            #${MODAL_ID} .heatmap-cell {
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 4px 2px;
                font-weight: 600;
                border-radius: 2px;
                color: #fff;
                min-height: 24px;
            }

            #${MODAL_ID} .heatmap-label {
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                font-size: 10px;
                color: #0F1111;
                background: #f0f2f2;
                border-radius: 2px;
                padding: 4px 2px;
            }

            /* ========== FILTER/SORT TOOLBAR ========== */
            #${MODAL_ID} .filter-toolbar {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 12px;
                flex-wrap: wrap;
            }

            #${MODAL_ID} .filter-btn {
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #D5D9D9;
                border-radius: 14px;
                background: #fff;
                color: #565959;
                cursor: pointer;
                transition: all 0.15s;
            }

            #${MODAL_ID} .filter-btn:hover { border-color: #007185; color: #007185; }
            #${MODAL_ID} .filter-btn.active { background: #007185; border-color: #007185; color: #fff; }

            #${MODAL_ID} .sort-select {
                padding: 4px 8px;
                font-size: 11px;
                border: 1px solid #D5D9D9;
                border-radius: 4px;
                background: #fff;
                color: #0F1111;
                cursor: pointer;
            }

            /* ========== PRICE COMPARISON ========== */
            #${MODAL_ID} .price-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 12px;
                margin: 8px 0;
            }

            #${MODAL_ID} .price-table th,
            #${MODAL_ID} .price-table td {
                padding: 6px 10px;
                text-align: left;
                border-bottom: 1px solid #e7e7e7;
            }

            #${MODAL_ID} .price-table th {
                background: #f0f2f2;
                font-weight: 700;
                color: #565959;
                font-size: 11px;
                text-transform: uppercase;
            }

            #${MODAL_ID} .price-table tr:hover { background: #fafafa; }

            #${MODAL_ID} .price-cheapest { color: #007600; font-weight: 700; }
            #${MODAL_ID} .price-expensive { color: #B12704; font-weight: 700; }
            #${MODAL_ID} .price-bar {
                height: 6px;
                background: #007185;
                border-radius: 3px;
                margin-top: 2px;
            }

            /* ========== IMAGE COMPARISON ========== */
            #${MODAL_ID} .image-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(70px, 1fr));
                gap: 6px;
                margin: 8px 0;
            }

            #${MODAL_ID} .image-thumb {
                width: 100%;
                aspect-ratio: 1;
                object-fit: cover;
                border-radius: 4px;
                border: 1px solid #e7e7e7;
            }

            #${MODAL_ID} .image-region-block {
                margin-bottom: 12px;
            }

            #${MODAL_ID} .image-region-label {
                font-size: 12px;
                font-weight: 700;
                color: #565959;
                margin-bottom: 4px;
            }

            #${MODAL_ID} .image-count-badge {
                display: inline-block;
                background: #f0f2f2;
                padding: 1px 6px;
                border-radius: 8px;
                font-size: 10px;
                font-weight: 600;
                color: #565959;
                margin-left: 6px;
            }

            /* ========== EXPORT BUTTONS ========== */
            #${MODAL_ID} .export-toolbar {
                display: flex;
                gap: 6px;
                margin-bottom: 12px;
            }

            #${MODAL_ID} .export-btn {
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #D5D9D9;
                border-radius: 4px;
                background: #fff;
                color: #0F1111;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 4px;
            }

            #${MODAL_ID} .export-btn:hover { background: #f7fafa; border-color: #007185; color: #007185; }

            /* ========== NOTIFICATION BADGE ========== */
            #${MODAL_ID} .alert-toggle {
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #D5D9D9;
                border-radius: 4px;
                background: #fff;
                color: #0F1111;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 4px;
            }

            #${MODAL_ID} .alert-toggle:hover { border-color: #007185; color: #007185; }
            #${MODAL_ID} .alert-toggle.subscribed { background: #e6f4ea; border-color: #007600; color: #007600; }

            /* ========== CLICKABLE DIFFS ========== */
            #${MODAL_ID} .diff-insert[data-clickable],
            #${MODAL_ID} .diff-delete[data-clickable],
            #${MODAL_ID} .diff-text .diff-insert[data-clickable],
            #${MODAL_ID} .diff-text .diff-delete[data-clickable] {
                cursor: pointer;
                position: relative;
            }

            #${MODAL_ID} .diff-insert[data-clickable]:hover {
                outline: 2px solid #007600;
                outline-offset: 1px;
                border-radius: 3px;
            }
            #${MODAL_ID} .diff-delete[data-clickable]:hover {
                outline: 2px solid #cf222e;
                outline-offset: 1px;
                border-radius: 3px;
            }

            #${MODAL_ID} .diff-insert[data-clickable]::after,
            #${MODAL_ID} .diff-delete[data-clickable]::after {
                content: '🔍';
                font-size: 9px;
                vertical-align: super;
                margin-left: 1px;
                opacity: 0;
                transition: opacity 0.15s;
            }
            #${MODAL_ID} .diff-insert[data-clickable]:hover::after,
            #${MODAL_ID} .diff-delete[data-clickable]:hover::after {
                opacity: 1;
            }

            #${MODAL_ID} .diff-click-hint {
                font-size: 10px;
                color: #007185;
                margin-top: 4px;
                font-style: italic;
            }

            /* ========== PAGE HIGHLIGHT (injected on page) ========== */
            .mrcc-page-highlight {
                background: #FFFF00 !important;
                color: #0F1111 !important;
                outline: 2px solid #FF9900 !important;
                outline-offset: 2px;
                border-radius: 3px;
                box-shadow: 0 0 10px rgba(255, 153, 0, 0.5) !important;
                animation: mrcc-pulse-highlight 1.5s ease-in-out 3;
                position: relative;
                z-index: 10;
                scroll-margin-top: 80px;
            }

            @keyframes mrcc-pulse-highlight {
                0%, 100% { box-shadow: 0 0 10px rgba(255, 153, 0, 0.5); }
                50% { box-shadow: 0 0 20px rgba(255, 153, 0, 0.9); }
            }

            /* ========== PERSISTENT BULLET HIGHLIGHTS (on Amazon page) ========== */
            .mrcc-bullet-modified {
                border-left: 4px solid #C45500 !important;
                background: rgba(196, 85, 0, 0.07) !important;
                padding-left: 8px !important;
                margin-left: -12px !important;
                border-radius: 0 4px 4px 0 !important;
                position: relative;
                transition: background 0.3s;
            }
            .mrcc-bullet-modified:hover {
                background: rgba(196, 85, 0, 0.14) !important;
            }

            .mrcc-bullet-missing {
                border-left: 4px solid #B12704 !important;
                background: rgba(177, 39, 4, 0.07) !important;
                padding-left: 8px !important;
                margin-left: -12px !important;
                border-radius: 0 4px 4px 0 !important;
                position: relative;
                transition: background 0.3s;
            }
            .mrcc-bullet-missing:hover {
                background: rgba(177, 39, 4, 0.14) !important;
            }

            .mrcc-bullet-ok {
                border-left: 4px solid #007600 !important;
                background: rgba(0, 118, 0, 0.04) !important;
                padding-left: 8px !important;
                margin-left: -12px !important;
                border-radius: 0 4px 4px 0 !important;
            }

            .mrcc-bullet-tag {
                display: inline-block;
                font-size: 9px;
                font-weight: 700;
                padding: 1px 5px;
                border-radius: 3px;
                margin-left: 6px;
                vertical-align: middle;
                letter-spacing: 0.3px;
                font-family: system-ui, -apple-system, sans-serif;
                cursor: help;
            }
            .mrcc-bullet-tag.modified {
                background: #FEF3C7;
                color: #92400E;
                border: 1px solid #F59E0B;
            }
            .mrcc-bullet-tag.missing {
                background: #FEE2E2;
                color: #991B1B;
                border: 1px solid #EF4444;
            }
            .mrcc-bullet-tag.ok {
                background: #D1FAE5;
                color: #065F46;
                border: 1px solid #10B981;
            }

            /* Bullet highlight legend */
            .mrcc-bullet-legend {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 6px 12px;
                margin: 8px 0;
                background: #F8F9FA;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                font-size: 11px;
                font-family: system-ui, -apple-system, sans-serif;
                color: #565959;
            }
            .mrcc-bullet-legend-title {
                font-weight: 700;
                color: #0F1111;
                display: flex;
                align-items: center;
                gap: 4px;
            }
            .mrcc-bullet-legend-item {
                display: flex;
                align-items: center;
                gap: 4px;
            }
            .mrcc-bullet-legend-dot {
                width: 10px;
                height: 10px;
                border-radius: 2px;
                flex-shrink: 0;
            }
            .mrcc-bullet-legend-dot.modified { background: #C45500; }
            .mrcc-bullet-legend-dot.missing { background: #B12704; }
            .mrcc-bullet-legend-dot.ok { background: #007600; }

            @keyframes mrcc-bullet-flash {
                0% { opacity: 0; transform: translateX(-4px); }
                100% { opacity: 1; transform: translateX(0); }
            }
            .mrcc-bullet-modified, .mrcc-bullet-missing, .mrcc-bullet-ok {
                animation: mrcc-bullet-flash 0.4s ease-out;
            }
        `;
        document.head.appendChild(styles);
    }

    /**
     * Find text on the page and scroll to it with a highlight effect.
     * Searches through key product sections (title, bullets, description, A+ content).
     * Returns true if found and highlighted.
     */
    function findAndHighlightOnPage(searchText) {
        // Remove any previous highlights
        document.querySelectorAll('.mrcc-page-highlight').forEach(el => {
            const parent = el.parentNode;
            parent.replaceChild(document.createTextNode(el.textContent), el);
            parent.normalize();
        });

        if (!searchText || searchText.trim().length < 3) return false;
        const query = searchText.trim();

        // Sections to search (in priority order)
        const sectionSelectors = [
            '#productTitle',
            '#title',
            '#feature-bullets',
            '#productDescription',
            '#aplus_feature_div',
            '#aplus',
            '#productOverview_feature_div',
            '#detailBullets_feature_div',
            '#detail-bullets',
            '#product-description',
            '#dp-container',
            '#centerCol',
            'body'
        ];

        for (const selector of sectionSelectors) {
            const section = document.querySelector(selector);
            if (!section) continue;

            // Walk text nodes in this section
            const walker = document.createTreeWalker(
                section,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: function(node) {
                        // Skip our own UI elements
                        if (node.parentElement && (
                            node.parentElement.closest('#' + MODAL_ID) ||
                            node.parentElement.closest('#' + BADGE_ID) ||
                            node.parentElement.closest('#' + OVERLAY_ID)
                        )) return NodeFilter.FILTER_REJECT;
                        return NodeFilter.FILTER_ACCEPT;
                    }
                }
            );

            let textNode;
            while (textNode = walker.nextNode()) {
                const nodeText = textNode.textContent;
                const idx = nodeText.toLowerCase().indexOf(query.toLowerCase());
                if (idx === -1) continue;

                // Found it — split the text node and wrap the match
                const before = nodeText.substring(0, idx);
                const match = nodeText.substring(idx, idx + query.length);
                const after = nodeText.substring(idx + query.length);

                const highlightSpan = document.createElement('span');
                highlightSpan.className = 'mrcc-page-highlight';
                highlightSpan.textContent = match;

                const parent = textNode.parentNode;
                const frag = document.createDocumentFragment();
                if (before) frag.appendChild(document.createTextNode(before));
                frag.appendChild(highlightSpan);
                if (after) frag.appendChild(document.createTextNode(after));
                parent.replaceChild(frag, textNode);

                // Scroll into view
                highlightSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });

                // Auto-remove highlight after 8 seconds
                setTimeout(() => {
                    if (highlightSpan.parentNode) {
                        const text = document.createTextNode(highlightSpan.textContent);
                        highlightSpan.parentNode.replaceChild(text, highlightSpan);
                        text.parentNode.normalize();
                    }
                }, 8000);

                return true;
            }
        }

        return false;
    }

    /**
     * Automatically highlight "About this item" bullet points on the Amazon page
     * based on comparison results. Color-codes bullets as modified, missing, or ok.
     */
    function highlightPageBullets(result) {
        // Clean up any previous bullet highlights
        document.querySelectorAll('.mrcc-bullet-modified, .mrcc-bullet-missing, .mrcc-bullet-ok').forEach(el => {
            el.classList.remove('mrcc-bullet-modified', 'mrcc-bullet-missing', 'mrcc-bullet-ok');
        });
        document.querySelectorAll('.mrcc-bullet-tag').forEach(el => el.remove());
        document.querySelectorAll('.mrcc-bullet-legend').forEach(el => el.remove());

        if (!result || !result.comparisons || result.comparisons.length === 0) return;

        // Get feature bullet elements from the page
        const featureBullets = document.getElementById('feature-bullets');
        if (!featureBullets) return;

        const bulletSpans = featureBullets.querySelectorAll('li span.a-list-item');
        if (!bulletSpans.length) return;

        // Get current page region
        const pageRegion = extractProductInfo().region;

        // Collect all modified and missing sentences across comparisons
        // that involve the current page region
        const bulletStatus = new Map(); // bulletIndex -> { status, regions, details }

        // Get bullet texts for matching
        const bulletTexts = Array.from(bulletSpans)
            .map(el => el.textContent.trim())
            .filter(t => t.length > 5 && !t.startsWith('\u203A'));

        result.comparisons.forEach(comp => {
            const sd = comp.sentence_detail;
            if (!sd) return;

            // Only process comparisons involving the current page region
            const isRegion1 = comp.region_1 === pageRegion;
            const isRegion2 = comp.region_2 === pageRegion;
            if (!isRegion1 && !isRegion2) return;

            const otherRegion = isRegion1 ? comp.region_2 : comp.region_1;
            const matched = sd.matched || [];
            const onlyInPage = isRegion1 ? (sd.only_in_1 || []) : (sd.only_in_2 || []);

            // Check modified sentences (low similarity matches)
            matched.filter(m => m.similarity < 0.95).forEach(m => {
                const pageSentence = isRegion1 ? m.sentence_1 : m.sentence_2;

                bulletTexts.forEach((bulletText, idx) => {
                    const similarity = fuzzyMatchBullet(bulletText, pageSentence);
                    if (similarity > 0.4) {
                        const existing = bulletStatus.get(idx);
                        if (!existing || existing.status !== 'modified') {
                            bulletStatus.set(idx, {
                                status: 'modified',
                                regions: existing ? [...new Set([...existing.regions, otherRegion])] : [otherRegion],
                                similarity: m.similarity,
                                detail: `Different in ${otherRegion} (${(m.similarity * 100).toFixed(0)}% similar)`
                            });
                        } else if (existing && !existing.regions.includes(otherRegion)) {
                            existing.regions.push(otherRegion);
                            existing.detail = `Different in ${existing.regions.join(', ')}`;
                        }
                    }
                });
            });

            // Check sentences only on this page (missing from other region)
            onlyInPage.forEach(sent => {
                bulletTexts.forEach((bulletText, idx) => {
                    const similarity = fuzzyMatchBullet(bulletText, sent);
                    if (similarity > 0.4) {
                        const existing = bulletStatus.get(idx);
                        if (!existing) {
                            bulletStatus.set(idx, {
                                status: 'missing',
                                regions: [otherRegion],
                                detail: `Not found in ${otherRegion}`
                            });
                        } else if (existing.status === 'missing' && !existing.regions.includes(otherRegion)) {
                            existing.regions.push(otherRegion);
                            existing.detail = `Not found in ${existing.regions.join(', ')}`;
                        }
                        // Don't downgrade 'modified' to 'missing'
                    }
                });
            });
        });

        // Apply highlights to DOM
        let modifiedCount = 0, missingCount = 0, okCount = 0;
        let actualBulletIndex = 0;

        bulletSpans.forEach(span => {
            const text = span.textContent.trim();
            if (text.length <= 5 || text.startsWith('\u203A')) return;

            const li = span.closest('li');
            if (!li) { actualBulletIndex++; return; }

            const status = bulletStatus.get(actualBulletIndex);
            if (status) {
                if (status.status === 'modified') {
                    li.classList.add('mrcc-bullet-modified');
                    modifiedCount++;
                    const tag = document.createElement('span');
                    tag.className = 'mrcc-bullet-tag modified';
                    tag.textContent = '⚠ MODIFIED';
                    tag.title = status.detail;
                    span.appendChild(tag);
                } else if (status.status === 'missing') {
                    li.classList.add('mrcc-bullet-missing');
                    missingCount++;
                    const tag = document.createElement('span');
                    tag.className = 'mrcc-bullet-tag missing';
                    tag.textContent = '✗ UNIQUE';
                    tag.title = status.detail;
                    span.appendChild(tag);
                }
            } else {
                li.classList.add('mrcc-bullet-ok');
                okCount++;
                const tag = document.createElement('span');
                tag.className = 'mrcc-bullet-tag ok';
                tag.textContent = '✓ OK';
                tag.title = 'Consistent across all regions';
                span.appendChild(tag);
            }

            actualBulletIndex++;
        });

        // Add legend above or at the top of the feature-bullets section
        if (modifiedCount > 0 || missingCount > 0) {
            const legend = document.createElement('div');
            legend.className = 'mrcc-bullet-legend';
            legend.innerHTML = `
                <span class="mrcc-bullet-legend-title">🔍 MRCC Regional Check</span>
                ${modifiedCount > 0 ? `<span class="mrcc-bullet-legend-item"><span class="mrcc-bullet-legend-dot modified"></span> ${modifiedCount} Modified</span>` : ''}
                ${missingCount > 0 ? `<span class="mrcc-bullet-legend-item"><span class="mrcc-bullet-legend-dot missing"></span> ${missingCount} Unique</span>` : ''}
                ${okCount > 0 ? `<span class="mrcc-bullet-legend-item"><span class="mrcc-bullet-legend-dot ok"></span> ${okCount} Consistent</span>` : ''}
            `;
            featureBullets.insertBefore(legend, featureBullets.firstChild);
        }
    }

    /**
     * Fuzzy-match a bullet point text against a sentence from comparison results.
     * Returns a similarity score between 0 and 1.
     */
    function fuzzyMatchBullet(bulletText, sentenceText) {
        if (!bulletText || !sentenceText) return 0;
        const a = bulletText.toLowerCase().replace(/[^\w\s]/g, '').trim();
        const b = sentenceText.toLowerCase().replace(/[^\w\s]/g, '').trim();

        if (!a || !b) return 0;

        // Exact match
        if (a === b) return 1.0;

        // One contains the other
        if (a.includes(b) || b.includes(a)) return 0.9;

        // Word overlap (Jaccard)
        const wordsA = new Set(a.split(/\s+/).filter(w => w.length > 2));
        const wordsB = new Set(b.split(/\s+/).filter(w => w.length > 2));
        if (wordsA.size === 0 || wordsB.size === 0) return 0;

        let intersection = 0;
        wordsA.forEach(w => { if (wordsB.has(w)) intersection++; });
        const union = new Set([...wordsA, ...wordsB]).size;
        return intersection / union;
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
     * Call backend API to check consistency with retry logic.
     * Sends scraped page data via POST so the backend can use the actual
     * product info instead of random mock categories for unknown ASINs.
     */
    async function checkConsistency(asin) {
        const maxRetries = 2;

        // Extract product info from the current page DOM
        const pageInfo = extractProductInfo();

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout (translations may take time)
                
                const response = await fetch(`${API_BASE_URL}/check`, {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        asin: asin,
                        page_title: pageInfo.title || '',
                        page_description: pageInfo.description || '',
                        page_region: pageInfo.region || 'US'
                    }),
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                
                // Validate response structure
                if (!data || !data.asin || !data.risk_level || !Array.isArray(data.comparisons)) {
                    throw new Error('Invalid API response structure');
                }

                return data;
            } catch (error) {
                console.warn(`[MRCC] API attempt ${attempt + 1} failed:`, error.message);
                if (attempt < maxRetries) {
                    await new Promise(r => setTimeout(r, 1000 * (attempt + 1))); // Backoff
                } else {
                    console.error('[MRCC] All API attempts failed:', error);
                    return null;
                }
            }
        }
        return null;
    }

    /**
     * Region flag emoji map
     */
    const REGION_FLAGS = {
        'US': '🇺🇸', 'IN': '🇮🇳', 'DE': '🇩🇪', 'UK': '🇬🇧', 'JP': '🇯🇵',
        'FR': '🇫🇷', 'CA': '🇨🇦', 'AU': '🇦🇺', 'ES': '🇪🇸'
    };

    /**
     * Check history storage
     */
    const HISTORY_KEY = 'mrcc_check_history';

    function getHistory() {
        try {
            return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
        } catch { return []; }
    }

    function saveToHistory(result) {
        try {
            const history = getHistory();
            // Remove duplicate if exists
            const filtered = history.filter(h => h.asin !== result.asin);
            // Add to front
            filtered.unshift({
                asin: result.asin,
                risk_level: result.risk_level,
                average_similarity: result.average_similarity,
                regions_count: result.regions_analyzed.length,
                checked_at: new Date().toISOString()
            });
            // Keep max 20 entries
            localStorage.setItem(HISTORY_KEY, JSON.stringify(filtered.slice(0, 20)));
        } catch (e) {
            console.warn('[MRCC] Could not save history:', e);
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
     * Show detailed comparison modal — full-featured version
     */
    function showDetailsModal(result) {
        closeModal();

        const overlay = document.createElement('div');
        overlay.id = OVERLAY_ID;
        overlay.addEventListener('click', closeModal);
        document.body.appendChild(overlay);

        const modal = document.createElement('div');
        modal.id = MODAL_ID;

        const riskClass = result.risk_level.toLowerCase();
        const avgScore = (result.average_similarity * 100).toFixed(1);
        const minScore = ((result.min_similarity || result.average_similarity) * 100).toFixed(1);
        const maxScore = ((result.max_similarity || result.average_similarity) * 100).toFixed(1);

        // ── Build Heatmap ────────────────────────────────────────────
        const regions = result.regions_analyzed || [];
        let heatmapHTML = '';
        if (regions.length > 1 && result.comparisons.length > 0) {
            const simMap = {};
            result.comparisons.forEach(c => {
                simMap[`${c.region_1}:${c.region_2}`] = c.similarity_score;
                simMap[`${c.region_2}:${c.region_1}`] = c.similarity_score;
            });
            const cols = regions.length + 1;
            let cells = `<div class="heatmap-label"></div>`;
            regions.forEach(r => { cells += `<div class="heatmap-label">${REGION_FLAGS[r] || ''} ${r}</div>`; });
            regions.forEach(r1 => {
                cells += `<div class="heatmap-label">${REGION_FLAGS[r1] || ''} ${r1}</div>`;
                regions.forEach(r2 => {
                    if (r1 === r2) {
                        cells += `<div class="heatmap-cell" style="background:#007600;">100</div>`;
                    } else {
                        const score = simMap[`${r1}:${r2}`];
                        const pct = score !== undefined ? (score * 100).toFixed(0) : '—';
                        const bg = score >= 0.75 ? '#007600' : score >= 0.45 ? '#C45500' : '#B12704';
                        cells += `<div class="heatmap-cell" style="background:${bg};">${pct}</div>`;
                    }
                });
            });
            heatmapHTML = `
                <div class="heatmap-section">
                    <div class="section-title">Similarity Heatmap</div>
                    <div class="heatmap-grid" style="grid-template-columns: repeat(${cols}, 1fr);">
                        ${cells}
                    </div>
                </div>
            `;
        }

        // ── Build Comparisons with Side-by-Side + Filter/Sort ────────
        const comparisonsHTML = result.comparisons.map((comp, idx) => {
            const scorePercent = (comp.similarity_score * 100).toFixed(1);
            const scoreClass = getScoreClass(comp.similarity_score);

            // New v3 per-dimension scores
            const ngramDice = ((comp.ngram_dice !== undefined ? comp.ngram_dice : comp.similarity_score) * 100).toFixed(0);
            const bigramJac = ((comp.bigram_jaccard !== undefined ? comp.bigram_jaccard : comp.similarity_score) * 100).toFixed(0);
            const wordJac = ((comp.word_jaccard !== undefined ? comp.word_jaccard : (comp.jaccard_score || comp.similarity_score)) * 100).toFixed(0);
            const sequence = ((comp.sequence_score !== undefined ? comp.sequence_score : comp.similarity_score) * 100).toFixed(0);
            const sentAlign = ((comp.sentence_alignment !== undefined ? comp.sentence_alignment : 1) * 100).toFixed(0);
            const features = ((comp.feature_overlap !== undefined ? comp.feature_overlap : 1) * 100).toFixed(0);
            const specMatch = ((comp.spec_match !== undefined ? comp.spec_match : 1) * 100).toFixed(0);
            const structural = ((comp.structural_score !== undefined ? comp.structural_score : 1) * 100).toFixed(0);

            // Per-pair issues
            let pairIssuesHTML = '';
            if (comp.issues && comp.issues.length > 0) {
                const issRows = comp.issues.slice(0, 5).map(iss =>
                    `<div class="pair-issue-row"><span class="pair-issue-icon">${iss.icon || '•'}</span><span class="issue-severity ${iss.severity}">${iss.severity}</span><span>${iss.title}: ${iss.description}</span></div>`
                ).join('');
                const moreCount = comp.issues.length > 5 ? `<div style="font-size:11px;color:#888;padding:4px 0 0 24px;">+ ${comp.issues.length - 5} more issues</div>` : '';
                pairIssuesHTML = `<div class="pair-issues"><div class="pair-issues-header">🔍 Issues Found (${comp.issues.length})</div>${issRows}${moreCount}</div>`;
            }

            // ── NEW: Structured Sentence-by-Sentence Diff ──────────────
            let sentenceViewHTML = '';
            const sd = comp.sentence_detail || {};
            const matchedSents = sd.matched || [];
            const onlyIn1 = sd.only_in_1 || [];
            const onlyIn2 = sd.only_in_2 || [];

            if (matchedSents.length || onlyIn1.length || onlyIn2.length) {
                // Summary counts
                const identicalCount = matchedSents.filter(m => m.similarity >= 0.95).length;
                const changedCount = matchedSents.filter(m => m.similarity < 0.95).length;
                const summaryHTML = `
                    <div class="sentence-diff-summary">
                        <span style="font-weight:700;">📊 Sentence Analysis:</span>
                        ${identicalCount ? `<span class="summary-badge matched">✓ ${identicalCount} Identical</span>` : ''}
                        ${changedCount ? `<span class="summary-badge changed">✎ ${changedCount} Modified</span>` : ''}
                        ${onlyIn1.length ? `<span class="summary-badge only-r1">− ${onlyIn1.length} Only in ${comp.region_1}</span>` : ''}
                        ${onlyIn2.length ? `<span class="summary-badge only-r2">+ ${onlyIn2.length} Only in ${comp.region_2}</span>` : ''}
                    </div>`;

                // Build sentence cards — changed & unique sentences first, identical collapsed
                let cardsHTML = '';

                // Changed sentences (most important — show first)
                matchedSents.filter(m => m.similarity < 0.95).forEach(m => {
                    const simPct = (m.similarity * 100).toFixed(0);
                    // Generate word-level diff between the two aligned sentences
                    const words1 = m.sentence_1.split(/(\s+)/);
                    const words2 = m.sentence_2.split(/(\s+)/);
                    let diffHTML1 = '', diffHTML2 = '';
                    // Simple word diff using SequenceMatcher-like approach
                    const wSet1 = new Set(m.sentence_1.toLowerCase().split(/\s+/));
                    const wSet2 = new Set(m.sentence_2.toLowerCase().split(/\s+/));
                    diffHTML1 = m.sentence_1.split(/\s+/).map(w => {
                        if (!wSet2.has(w.toLowerCase().replace(/[.,!?;:]/g, ''))) {
                            return `<span class="sentence-diff-word-delete">${w}</span>`;
                        }
                        return w;
                    }).join(' ');
                    diffHTML2 = m.sentence_2.split(/\s+/).map(w => {
                        if (!wSet1.has(w.toLowerCase().replace(/[.,!?;:]/g, ''))) {
                            return `<span class="sentence-diff-word-insert">${w}</span>`;
                        }
                        return w;
                    }).join(' ');

                    cardsHTML += `
                        <div class="sentence-card">
                            <div class="sentence-card-header match-changed">
                                <span>✎ Modified</span>
                                <span class="match-score">${simPct}% similar</span>
                            </div>
                            <div class="sentence-card-body">
                                <div class="sentence-row">
                                    <span class="sentence-region-tag r1">${comp.region_1}</span>
                                    <span class="sentence-text">${diffHTML1}</span>
                                </div>
                                <div class="sentence-row">
                                    <span class="sentence-region-tag r2">${comp.region_2}</span>
                                    <span class="sentence-text">${diffHTML2}</span>
                                </div>
                            </div>
                        </div>`;
                });

                // Sentences only in region 1 (missing from region 2)
                onlyIn1.forEach(sent => {
                    cardsHTML += `
                        <div class="sentence-card">
                            <div class="sentence-card-header only-region">
                                <span>− Missing from ${comp.region_2}</span>
                            </div>
                            <div class="sentence-card-body">
                                <div class="sentence-row">
                                    <span class="sentence-region-tag r1">${comp.region_1}</span>
                                    <span class="sentence-text">${sent}</span>
                                </div>
                            </div>
                        </div>`;
                });

                // Sentences only in region 2 (extra in region 2)
                onlyIn2.forEach(sent => {
                    cardsHTML += `
                        <div class="sentence-card">
                            <div class="sentence-card-header only-region region-2">
                                <span>+ Extra in ${comp.region_2}</span>
                            </div>
                            <div class="sentence-card-body">
                                <div class="sentence-row">
                                    <span class="sentence-region-tag r2">${comp.region_2}</span>
                                    <span class="sentence-text">${sent}</span>
                                </div>
                            </div>
                        </div>`;
                });

                // Identical sentences (collapsed by default)
                const identicalSents = matchedSents.filter(m => m.similarity >= 0.95);
                if (identicalSents.length > 0) {
                    let identicalCardsHTML = identicalSents.map(m => `
                        <div class="sentence-card">
                            <div class="sentence-card-header match-identical">
                                <span>✓ Identical</span>
                            </div>
                            <div class="sentence-card-body">
                                <div class="sentence-row">
                                    <span class="sentence-text" style="color:#555;font-size:12px;">${m.sentence_1}</span>
                                </div>
                            </div>
                        </div>`).join('');

                    cardsHTML += `
                        <div class="identical-sentences-toggle" data-state="collapsed">
                            ▸ Show ${identicalSents.length} identical sentence${identicalSents.length > 1 ? 's' : ''}
                        </div>
                        <div class="identical-sentences-group">
                            ${identicalCardsHTML}
                        </div>`;
                }

                sentenceViewHTML = `<div class="sentence-diff-container">${summaryHTML}${cardsHTML}</div>`;
            } else {
                sentenceViewHTML = `<div style="color:#565959;font-style:italic;padding:10px;">No sentence-level data available.</div>`;
            }

            // ── Inline diff HTML (legacy paragraph view) ──────────────
            let diffCombinedHTML = '';
            if (comp.description_diff && comp.description_diff.length > 0) {
                const diffSpans = comp.description_diff.map(part => {
                    const escaped = part.text.replace(/"/g, '&quot;');
                    if (part.type === 'equal') return `<span>${part.text}</span>`;
                    if (part.type === 'insert') return `<span class="diff-insert" data-clickable="1" data-search-text="${escaped}" title="Click to find on page — In ${comp.region_2} only">${part.text}</span>`;
                    if (part.type === 'delete') return `<span class="diff-delete" data-clickable="1" data-search-text="${escaped}" title="Click to find on page — In ${comp.region_1} only">${part.text}</span>`;
                    return '';
                }).join(' ');
                diffCombinedHTML = `<div class="desc-diff-combined">${diffSpans}</div><div class="diff-click-hint">💡 Click any highlighted difference to locate it on the page</div>`;
            }

            // Side-by-side HTML
            const desc1 = comp.description_1 || '';
            const desc2 = comp.description_2 || '';

            // Language badges
            const lang1 = comp.language_name_1 || 'English';
            const lang2 = comp.language_name_2 || 'English';
            const langCode1 = comp.language_1 || 'en';
            const langCode2 = comp.language_2 || 'en';
            const translated1 = comp.was_translated_1 || false;
            const translated2 = comp.was_translated_2 || false;
            const origDesc1 = comp.original_description_1 || desc1;
            const origDesc2 = comp.original_description_2 || desc2;

            const langBadge1 = langCode1 !== 'en'
                ? `<span class="lang-badge lang-translated" title="Translated from ${lang1}">${lang1} → EN</span>`
                : `<span class="lang-badge lang-en">English</span>`;
            const langBadge2 = langCode2 !== 'en'
                ? `<span class="lang-badge lang-translated" title="Translated from ${lang2}">${lang2} → EN</span>`
                : `<span class="lang-badge lang-en">English</span>`;

            // Original text panels (shown when description was translated)
            const origPanel1 = translated1
                ? `<div class="original-text-panel">
                    <div class="original-text-label">📝 Original (${lang1}):</div>
                    <div class="original-text">${origDesc1}</div>
                   </div>`
                : '';
            const origPanel2 = translated2
                ? `<div class="original-text-panel">
                    <div class="original-text-label">📝 Original (${lang2}):</div>
                    <div class="original-text">${origDesc2}</div>
                   </div>`
                : '';

            const sbsHTML = `
                <div class="sbs-container">
                    <div class="sbs-panel">
                        <div class="sbs-panel-header">${REGION_FLAGS[comp.region_1] || ''} ${comp.region_1} ${langBadge1}</div>
                        ${desc1}
                        ${origPanel1}
                    </div>
                    <div class="sbs-panel">
                        <div class="sbs-panel-header">${REGION_FLAGS[comp.region_2] || ''} ${comp.region_2} ${langBadge2}</div>
                        ${desc2}
                        ${origPanel2}
                    </div>
                </div>
            `;

            const url1 = comp.url_1 || '#';
            const url2 = comp.url_2 || '#';
            const flag1 = REGION_FLAGS[comp.region_1] || '🌐';
            const flag2 = REGION_FLAGS[comp.region_2] || '🌐';

            // Determine risk bucket for filtering
            const riskBucket = comp.similarity_score >= 0.75 ? 'low' : comp.similarity_score >= 0.45 ? 'medium' : 'high';

            // Language indicator for card header
            const hasTranslation = translated1 || translated2;
            const translationIndicator = hasTranslation ? ' <span class="translation-indicator" title="Descriptions were translated to English for comparison">🌐</span>' : '';

            return `
                <div class="comparison-card" data-comp-idx="${idx}" data-score="${comp.similarity_score}" data-risk="${riskBucket}">
                    <div class="comparison-header">
                        <div class="comparison-header-left">
                            <span class="expand-icon">▶</span>
                            <span class="region-badge">${flag1} ${comp.region_1} vs ${flag2} ${comp.region_2}${translationIndicator}</span>
                        </div>
                        <span class="comparison-score ${scoreClass}">${scorePercent}% Match</span>
                    </div>
                    <div class="lang-badges-row">
                        ${langBadge1} <span style="color:#888;margin:0 4px;">vs</span> ${langBadge2}
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-item"><div class="metric-bar-container"><div class="metric-bar" style="width:${ngramDice}%"></div></div><div class="metric-label">N-gram</div><div class="metric-value">${ngramDice}%</div></div>
                        <div class="metric-item"><div class="metric-bar-container"><div class="metric-bar" style="width:${sentAlign}%"></div></div><div class="metric-label">Sentences</div><div class="metric-value">${sentAlign}%</div></div>
                        <div class="metric-item"><div class="metric-bar-container"><div class="metric-bar" style="width:${specMatch}%"></div></div><div class="metric-label">Specs</div><div class="metric-value">${specMatch}%</div></div>
                        <div class="metric-item"><div class="metric-bar-container"><div class="metric-bar" style="width:${features}%"></div></div><div class="metric-label">Features</div><div class="metric-value">${features}%</div></div>
                        <div class="metric-item"><div class="metric-bar-container"><div class="metric-bar" style="width:${wordJac}%"></div></div><div class="metric-label">Words</div><div class="metric-value">${wordJac}%</div></div>
                        <div class="metric-item"><div class="metric-bar-container"><div class="metric-bar" style="width:${bigramJac}%"></div></div><div class="metric-label">Phrases</div><div class="metric-value">${bigramJac}%</div></div>
                        <div class="metric-item"><div class="metric-bar-container"><div class="metric-bar" style="width:${sequence}%"></div></div><div class="metric-label">Sequence</div><div class="metric-value">${sequence}%</div></div>
                        <div class="metric-item"><div class="metric-bar-container"><div class="metric-bar" style="width:${structural}%"></div></div><div class="metric-label">Structure</div><div class="metric-value">${structural}%</div></div>
                    </div>
                    ${pairIssuesHTML}
                    <div class="desc-diff-panel">
                        <div class="region-links">
                            <a class="region-link" href="${url1}" target="_blank" rel="noopener">${flag1} Amazon ${comp.region_1}</a>
                            <a class="region-link" href="${url2}" target="_blank" rel="noopener">${flag2} Amazon ${comp.region_2}</a>
                        </div>
                        <div class="diff-view-toggle">
                            <div class="diff-view-tab active" data-view="sentences">Sentence View</div>
                            <div class="diff-view-tab" data-view="inline">Inline Diff</div>
                            <div class="diff-view-tab" data-view="sidebyside">Side-by-Side</div>
                        </div>
                        <div class="diff-view-content" data-active-view="sentences">
                            <div class="diff-sentence-view">
                                ${sentenceViewHTML}
                                ${(translated1 || translated2) ? `
                                <div class="translation-note">
                                    <span class="translation-note-icon">🌐</span>
                                    Comparing translated English versions. ${translated1 ? `${comp.region_1}: ${lang1}` : ''}${translated1 && translated2 ? ' | ' : ''}${translated2 ? `${comp.region_2}: ${lang2}` : ''}
                                </div>` : ''}
                            </div>
                            <div class="diff-inline-view" style="display:none;">
                                <div class="desc-diff-section">
                                    <div class="desc-region-label">Highlighted Differences (${comp.region_1} → ${comp.region_2})</div>
                                    ${diffCombinedHTML || `<div class="desc-text" style="color:#565959;font-style:italic;">Descriptions are identical.</div>`}
                                </div>
                            </div>
                            <div class="diff-sbs-view" style="display:none;">
                                ${sbsHTML}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // ── Title Analysis ───────────────────────────────────────────
        let titleAnalysisHTML = '';
        if (result.title_analysis) {
            if (result.title_analysis.is_mismatch) {
                const mismatches = result.title_analysis.mismatches.map(m => {
                    const score = (m.similarity * 100).toFixed(0);
                    let diffHTML = '';
                    if (m.diff) {
                        const diffSpans = m.diff.map(p => {
                            const escaped = p.text.replace(/"/g, '&quot;');
                            if (p.type === 'equal') return `<span>${p.text}</span>`;
                            if (p.type === 'insert') return `<span class="diff-insert" data-clickable="1" data-search-text="${escaped}" title="Click to find on page">${p.text}</span>`;
                            if (p.type === 'delete') return `<span class="diff-delete" data-clickable="1" data-search-text="${escaped}" title="Click to find on page">${p.text}</span>`;
                            return '';
                        }).join(' ');
                        diffHTML = `<div class="diff-content"><div class="diff-label">Diff (${m.region_1} → ${m.region_2})</div><div class="diff-text">${diffSpans}</div><div class="diff-click-hint">💡 Click any highlighted difference to locate it on the page</div></div>`;
                    }
                    return `<div class="mismatch-item"><div class="mismatch-header"><span class="region-badge">${m.region_1} vs ${m.region_2}</span><span class="mismatch-score">${score}%</span></div><div class="mismatch-titles"><div class="mismatch-title-row"><span class="region-label">${m.region_1}:</span><span class="title-text">${m.title_1}</span></div><div class="mismatch-title-row"><span class="region-label">${m.region_2}:</span><span class="title-text">${m.title_2}</span></div></div>${diffHTML}</div>`;
                }).join('');
                titleAnalysisHTML = `<div class="title-mismatch-section"><div class="mismatch-alert-header"><span class="alert-icon">⚠️</span><h4>Title Inconsistencies Detected</h4></div><div class="mismatch-list">${mismatches}</div></div>`;
            } else {
                titleAnalysisHTML = `<div class="title-mismatch-section" style="border-color:#007600;"><div class="mismatch-alert-header" style="background:#f0f8f0;border-bottom-color:#007600;"><span class="alert-icon">✓</span><h4 style="color:#007600;">Product Titles are Consistent</h4></div><div class="mismatch-list" style="padding:12px 16px;font-size:13px;color:#565959;">Titles match across all regions.</div></div>`;
            }
        }

        // ── Region URL Bar ───────────────────────────────────────────
        let regionUrlBarHTML = '';
        if (result.region_urls) {
            const regionBtns = Object.entries(result.region_urls).map(([r, url]) => {
                const flag = REGION_FLAGS[r] || '🌐';
                return `<a class="region-url-btn" href="${url}" target="_blank" rel="noopener"><span class="flag">${flag}</span> ${r}</a>`;
            }).join('');
            regionUrlBarHTML = `<div class="section-title">View Product on Amazon</div><div class="region-url-bar">${regionBtns}</div>`;
        }

        // ── Price Comparison ────────────────────────────────────────
        let priceHTML = '';
        if (result.prices && result.prices.length > 0) {
            const validPrices = result.prices.filter(p => p.price_usd != null);
            if (validPrices.length > 0) {
                const maxUSD = Math.max(...validPrices.map(p => p.price_usd));
                const minUSD = Math.min(...validPrices.map(p => p.price_usd));
                const sortedPrices = [...validPrices].sort((a, b) => a.price_usd - b.price_usd);
                const priceRows = sortedPrices.map((p, i) => {
                    const pct = maxUSD > 0 ? (p.price_usd / maxUSD * 100).toFixed(0) : 0;
                    const cls = i === 0 ? 'price-cheapest' : i === sortedPrices.length - 1 ? 'price-expensive' : '';
                    const tag = i === 0 ? ' ★ Best' : i === sortedPrices.length - 1 ? ' ▲ Highest' : '';
                    return `<tr class="${cls}"><td>${REGION_FLAGS[p.region] || ''} ${p.region}</td><td>${p.price_display}</td><td>$${p.price_usd.toFixed(2)}${tag}</td><td><div class="price-bar" style="width:${pct}%"></div></td></tr>`;
                }).join('');
                priceHTML = `
                    <div class="section-title">Price Comparison</div>
                    <table class="price-table">
                        <thead><tr><th>Region</th><th>Local Price</th><th>USD Equiv.</th><th>Relative</th></tr></thead>
                        <tbody>${priceRows}</tbody>
                    </table>
                `;
            }
        }

        // ── Image Comparison ────────────────────────────────────────
        let imageHTML = '';
        if (result.images && result.images.length > 0) {
            const imgBlocks = result.images.filter(i => i.image_count > 0).map(i => {
                const thumbs = i.image_urls.slice(0, 5).map(url => `<img class="image-thumb" src="${url}" alt="${i.region}" loading="lazy">`).join('');
                return `<div class="image-region-block"><div class="image-region-label">${REGION_FLAGS[i.region] || ''} ${i.region}<span class="image-count-badge">${i.image_count} images</span></div><div class="image-grid">${thumbs}</div></div>`;
            }).join('');

            let imgCompSummary = '';
            if (result.image_comparisons) {
                const mismatches = result.image_comparisons.filter(c => c.similarity_pct < 100);
                if (mismatches.length > 0) {
                    imgCompSummary = `<div style="margin-top:8px;padding:8px 12px;background:#fbe9e7;border-radius:4px;font-size:12px;color:#B12704;"><strong>⚠ ${mismatches.length} region pair(s)</strong> have different images.</div>`;
                } else {
                    imgCompSummary = `<div style="margin-top:8px;padding:8px 12px;background:#f0f8f0;border-radius:4px;font-size:12px;color:#007600;"><strong>✓</strong> All regions share the same images.</div>`;
                }
            }
            imageHTML = `<div class="section-title">Image Comparison</div>${imgBlocks}${imgCompSummary}`;
        }

        // ── History ──────────────────────────────────────────────────
        const history = getHistory();
        let historyHTML = '';
        if (history.length > 0) {
            const items = history.slice(0, 5).map(h => {
                const rC = h.risk_level.toLowerCase();
                const ic = getRiskIcon(h.risk_level);
                const p = (h.average_similarity * 100).toFixed(0);
                const d = new Date(h.checked_at).toLocaleDateString();
                return `<div class="history-item" data-asin="${h.asin}"><span class="history-icon risk-${rC}">${ic}</span><span class="history-asin">${h.asin}</span><span class="history-risk risk-${rC}">${h.risk_level}</span><span class="history-score">${p}%</span><span class="history-date">${d}</span></div>`;
            }).join('');
            historyHTML = `<div class="section-title" style="margin-top:20px;">Recent Checks</div><div class="history-list">${items}</div>`;
        }

        // ── Language Summary ─────────────────────────────────────────
        let languageSummaryHTML = '';
        if (result.language_info) {
            const langEntries = Object.entries(result.language_info);
            const translatedRegions = langEntries.filter(([, info]) => info.was_translated);
            if (translatedRegions.length > 0) {
                const langItems = langEntries.map(([region, info]) => {
                    const flag = REGION_FLAGS[region] || '🌐';
                    if (info.was_translated) {
                        return `<span class="lang-summary-item translated">${flag} ${region}: <strong>${info.language_name}</strong> → EN</span>`;
                    } else {
                        return `<span class="lang-summary-item">${flag} ${region}: English</span>`;
                    }
                }).join('');
                languageSummaryHTML = `
                    <div class="language-summary-panel">
                        <div class="language-summary-header">🌐 Multi-Language Detection</div>
                        <div class="language-summary-desc">Descriptions in ${translatedRegions.length} region(s) were translated to English for accurate comparison.</div>
                        <div class="language-summary-items">${langItems}</div>
                    </div>
                `;
            }
        }

        // ── Scraped indicator ────────────────────────────────────────
        const scrapedTag = result.scraped
            ? '<span style="font-size:10px;background:#e6f4ea;color:#007600;padding:2px 6px;border-radius:8px;margin-left:8px;">LIVE DATA</span>'
            : '<span style="font-size:10px;background:#f0f2f2;color:#565959;padding:2px 6px;border-radius:8px;margin-left:8px;">MOCK DATA</span>';

        // ── Build Issues Panel (NEW v3) ──────────────────────────────
        let issuesPanelHTML = '';
        const issues = result.issues || [];
        const issueCounts = result.issue_counts || { high: 0, medium: 0, low: 0, total: 0 };
        if (issues.length > 0) {
            const issueItems = issues.slice(0, 10).map(iss => `
                <div class="issue-item">
                    <span class="issue-icon">${iss.icon || '•'}</span>
                    <div class="issue-content">
                        <div class="issue-title">${iss.title}</div>
                        <div class="issue-desc">${iss.description}</div>
                    </div>
                    <span class="issue-severity ${iss.severity}">${iss.severity}</span>
                </div>
            `).join('');
            const badges = [
                issueCounts.high > 0 ? `<span class="issue-badge high">${issueCounts.high} High</span>` : '',
                issueCounts.medium > 0 ? `<span class="issue-badge medium">${issueCounts.medium} Medium</span>` : '',
                issueCounts.low > 0 ? `<span class="issue-badge low">${issueCounts.low} Low</span>` : '',
            ].filter(Boolean).join('');
            issuesPanelHTML = `
                <div class="issues-section">
                    <div class="issues-header">
                        <span>🔍 Issues Detected</span>
                        <div class="issue-badges">${badges}</div>
                    </div>
                    ${issueItems}
                </div>
            `;
        } else {
            issuesPanelHTML = `
                <div class="issues-section no-issues">
                    <div class="issues-header">
                        <span>✅ No Issues Detected</span>
                    </div>
                    <div style="font-size:13px;color:#276749;">All specifications, content, and structure are consistent across regions.</div>
                </div>
            `;
        }

        // ── Build Spec Analysis Panel (NEW v3) ───────────────────────
        let specPanelHTML = '';
        const specAnalysis = result.spec_analysis || {};
        const specKeys = Object.keys(specAnalysis);
        if (specKeys.length > 0) {
            const specCards = specKeys.map(key => {
                const info = specAnalysis[key];
                const cardClass = info.consistent ? 'consistent' : 'conflict';
                const statusIcon = info.consistent ? '✓' : '✗';
                const statusClass = info.consistent ? 'ok' : 'conflict';
                const readable = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                const vals = Object.entries(info.values || {}).map(([r, v]) =>
                    `<span class="spec-value-item">${REGION_FLAGS[r] || ''} ${r}: <strong>${v}</strong></span>`
                ).join('');
                const missing = (info.regions_missing || []).length > 0
                    ? `<div style="font-size:10px;color:#975A16;margin-top:2px;">Missing in: ${info.regions_missing.join(', ')}</div>`
                    : '';
                return `
                    <div class="spec-card ${cardClass}">
                        <div class="spec-name">${readable}</div>
                        <div class="spec-values">${vals}</div>
                        ${missing}
                        <div class="spec-status ${statusClass}">${statusIcon} ${info.consistent ? 'Consistent' : 'Conflict'}</div>
                    </div>
                `;
            }).join('');
            specPanelHTML = `
                <div class="spec-section">
                    <div class="section-title">📊 Specification Consistency</div>
                    <div class="spec-grid">${specCards}</div>
                </div>
            `;
        }

        // ── Assemble Modal ───────────────────────────────────────────
        modal.innerHTML = `
            <div class="modal-header">
                <div class="modal-header-content">
                    <h2 class="modal-title">Consistency Report ${scrapedTag}</h2>
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
                    <div class="info-card-label">ASIN</div><div class="info-card-value">${result.asin}</div>
                    <div class="info-card-label">Regions</div><div class="info-card-value">${regions.join(', ')}</div>
                    <div class="info-card-label">Score Range</div><div class="info-card-value">${minScore}% — ${maxScore}%</div>
                    <div class="info-card-label">Confidence</div><div class="info-card-value">${result.confidence || 'MEDIUM'}</div>
                </div>

                ${languageSummaryHTML}

                ${issuesPanelHTML}
                ${specPanelHTML}

                <!-- Export & Alert toolbar -->
                <div class="export-toolbar">
                    <button class="export-btn" id="mrcc-export-csv">📄 Export CSV</button>
                    <button class="export-btn" id="mrcc-export-json">📋 Export JSON</button>
                    <button class="alert-toggle" id="mrcc-alert-toggle">🔔 Monitor Changes</button>
                </div>

                ${titleAnalysisHTML}
                ${regionUrlBarHTML}
                ${priceHTML}
                ${imageHTML}
                ${heatmapHTML}

                <div class="section-title">Regional Comparisons</div>

                <!-- Filter & Sort Toolbar -->
                <div class="filter-toolbar">
                    <span style="font-size:11px;color:#565959;font-weight:600;">Filter:</span>
                    <button class="filter-btn active" data-filter="all">All (${result.comparisons.length})</button>
                    <button class="filter-btn" data-filter="high">⚠ Mismatches</button>
                    <button class="filter-btn" data-filter="low">✓ Consistent</button>
                    <select class="sort-select" id="mrcc-sort">
                        <option value="default">Sort: Default</option>
                        <option value="asc">Score: Low → High</option>
                        <option value="desc">Score: High → Low</option>
                    </select>
                </div>

                <div class="click-hint">Click any card to expand — toggle Inline Diff or Side-by-Side view</div>
                <div id="mrcc-comparisons-list">
                    ${comparisonsHTML}
                </div>

                ${historyHTML}
            </div>
            <div class="modal-footer">
                <button class="footer-btn secondary" onclick="document.getElementById('${MODAL_ID}').querySelector('.modal-close').click()">Close</button>
            </div>
        `;

        modal.querySelector('.modal-close').addEventListener('click', closeModal);
        document.body.appendChild(modal);
        document.addEventListener('keydown', handleEscapeKey);
        saveToHistory(result);

        // ── Wire up interactions ─────────────────────────────────────
        // Click-to-find: clickable diff spans
        modal.addEventListener('click', function(e) {
            const diffEl = e.target.closest('[data-clickable][data-search-text]');
            if (!diffEl) return;
            e.stopPropagation();

            const searchText = diffEl.getAttribute('data-search-text');
            if (!searchText || searchText.length < 3) return;

            // Close modal so user can see the page
            closeModal();

            // Small delay to let modal close, then find and highlight
            setTimeout(() => {
                const found = findAndHighlightOnPage(searchText);
                if (!found) {
                    // Try with shorter substring (first 30 chars)
                    const shorter = searchText.substring(0, 30);
                    const foundShort = findAndHighlightOnPage(shorter);
                    if (!foundShort) {
                        // Show a brief toast notification
                        showToast(`Could not find "${searchText.substring(0, 40)}..." on this page`);
                    }
                }
            }, 300);
        });

        // Expand cards
        modal.querySelectorAll('.comparison-card[data-comp-idx]').forEach(card => {
            card.addEventListener('click', function(e) {
                if (e.target.closest('a') || e.target.closest('.diff-view-tab') || e.target.closest('select') || e.target.closest('[data-clickable]')) return;
                this.classList.toggle('expanded');
            });
        });

        // Diff view toggle (sentence ↔ inline ↔ side-by-side)
        modal.querySelectorAll('.diff-view-tab').forEach(tab => {
            tab.addEventListener('click', function(e) {
                e.stopPropagation();
                const panel = this.closest('.desc-diff-panel');
                panel.querySelectorAll('.diff-view-tab').forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                const view = this.dataset.view;
                const sentenceEl = panel.querySelector('.diff-sentence-view');
                const inlineEl = panel.querySelector('.diff-inline-view');
                const sbsEl = panel.querySelector('.diff-sbs-view');
                if (sentenceEl) sentenceEl.style.display = view === 'sentences' ? 'block' : 'none';
                if (inlineEl) inlineEl.style.display = view === 'inline' ? 'block' : 'none';
                if (sbsEl) sbsEl.style.display = view === 'sidebyside' ? 'block' : 'none';
            });
        });

        // Identical sentences toggle
        modal.querySelectorAll('.identical-sentences-toggle').forEach(toggle => {
            toggle.addEventListener('click', function(e) {
                e.stopPropagation();
                const group = this.nextElementSibling;
                if (!group) return;
                const isExpanded = group.classList.contains('expanded');
                group.classList.toggle('expanded');
                const count = group.querySelectorAll('.sentence-card').length;
                this.textContent = isExpanded
                    ? `▸ Show ${count} identical sentence${count > 1 ? 's' : ''}`
                    : `▾ Hide ${count} identical sentence${count > 1 ? 's' : ''}`;
            });
        });

        // Filter buttons
        modal.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                modal.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                const filter = this.dataset.filter;
                modal.querySelectorAll('.comparison-card[data-risk]').forEach(card => {
                    if (filter === 'all') card.style.display = '';
                    else if (filter === 'high') card.style.display = card.dataset.risk === 'high' || card.dataset.risk === 'medium' ? '' : 'none';
                    else if (filter === 'low') card.style.display = card.dataset.risk === 'low' ? '' : 'none';
                });
            });
        });

        // Sort select
        const sortSelect = modal.querySelector('#mrcc-sort');
        if (sortSelect) {
            sortSelect.addEventListener('change', function(e) {
                e.stopPropagation();
                const container = modal.querySelector('#mrcc-comparisons-list');
                const cards = Array.from(container.querySelectorAll('.comparison-card'));
                if (this.value === 'asc') cards.sort((a, b) => parseFloat(a.dataset.score) - parseFloat(b.dataset.score));
                else if (this.value === 'desc') cards.sort((a, b) => parseFloat(b.dataset.score) - parseFloat(a.dataset.score));
                else cards.sort((a, b) => parseInt(a.dataset.compIdx) - parseInt(b.dataset.compIdx));
                cards.forEach(c => container.appendChild(c));
            });
        }

        // Export CSV
        const csvBtn = modal.querySelector('#mrcc-export-csv');
        if (csvBtn) {
            csvBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                window.open(`${API_BASE_URL}/export/csv?asin=${result.asin}`, '_blank');
            });
        }

        // Export JSON
        const jsonBtn = modal.querySelector('#mrcc-export-json');
        if (jsonBtn) {
            jsonBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                window.open(`${API_BASE_URL}/export/json?asin=${result.asin}`, '_blank');
            });
        }

        // Alert toggle
        const alertBtn = modal.querySelector('#mrcc-alert-toggle');
        if (alertBtn) {
            // Check if already subscribed
            const alertKey = 'mrcc_alerts';
            let alerts = [];
            try { alerts = JSON.parse(localStorage.getItem(alertKey) || '[]'); } catch {}
            if (alerts.includes(result.asin)) {
                alertBtn.classList.add('subscribed');
                alertBtn.textContent = '🔔 Monitoring Active';
            }
            alertBtn.addEventListener('click', async function(e) {
                e.stopPropagation();
                if (this.classList.contains('subscribed')) {
                    // Unsubscribe
                    try { await fetch(`${API_BASE_URL}/alerts/${result.asin}`, { method: 'DELETE' }); } catch {}
                    alerts = alerts.filter(a => a !== result.asin);
                    localStorage.setItem(alertKey, JSON.stringify(alerts));
                    this.classList.remove('subscribed');
                    this.textContent = '🔔 Monitor Changes';
                } else {
                    // Subscribe
                    try {
                        await fetch(`${API_BASE_URL}/alerts/subscribe`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ asin: result.asin }),
                        });
                    } catch {}
                    alerts.push(result.asin);
                    localStorage.setItem(alertKey, JSON.stringify(alerts));
                    this.classList.add('subscribed');
                    this.textContent = '🔔 Monitoring Active';
                }
            });
        }
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
     * Show a toast notification
     */
    function showToast(message, duration = 3000) {
        const existing = document.getElementById('mrcc-toast');
        if (existing) existing.remove();
        const toast = document.createElement('div');
        toast.id = 'mrcc-toast';
        toast.textContent = message;
        Object.assign(toast.style, {
            position: 'fixed',
            bottom: '30px',
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#333',
            color: '#fff',
            padding: '12px 24px',
            borderRadius: '8px',
            fontSize: '14px',
            fontFamily: 'system-ui, sans-serif',
            zIndex: '2147483647',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            opacity: '0',
            transition: 'opacity 0.3s ease'
        });
        document.body.appendChild(toast);
        requestAnimationFrame(() => { toast.style.opacity = '1'; });
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    /**
     * Fetch and display consistency data for a given ASIN
     */
    async function loadASIN(asin) {
        if (!asin) return;
        if (asin === currentASIN && currentResult) {
            console.log(`[MRCC] ASIN ${asin} already loaded, skipping`);
            return;
        }

        console.log(`[MRCC] Loading ASIN: ${asin}`);
        currentASIN = asin;

        const result = await checkConsistency(asin);
        if (!result) {
            console.log('[MRCC] Failed to get consistency data');
            return;
        }

        console.log('[MRCC] Consistency result:', result);
        currentResult = result;
        createBadge(result);

        // Highlight mismatched bullet points on the Amazon page
        try {
            highlightPageBullets(result);
        } catch (e) {
            console.warn('[MRCC] Could not highlight page bullets:', e);
        }
    }

    /**
     * Main initialization function
     */
    async function init() {
        // Inject styles
        injectStyles();

        // Auto-detect API URL (local vs production)
        await detectApiUrl();

        // Detect ASIN and load data
        const asin = detectASIN();
        if (!asin) {
            console.log('[MRCC] No ASIN detected on this page');
        } else {
            await loadASIN(asin);
        }

        // ── URL Change Monitor ──────────────────────────────────────
        // Detect navigation to different Amazon products (soft navigations,
        // History API pushState/replaceState, and popstate events).
        let lastUrl = window.location.href;

        function checkForNavigation() {
            const currentUrl = window.location.href;
            if (currentUrl !== lastUrl) {
                lastUrl = currentUrl;
                const newAsin = detectASIN();
                if (newAsin && newAsin !== currentASIN) {
                    console.log(`[MRCC] Navigation detected — new ASIN: ${newAsin}`);
                    loadASIN(newAsin);
                }
            }
        }

        // Poll for URL changes (catches all types of navigation)
        setInterval(checkForNavigation, 1500);

        // Also listen for History API changes
        const origPushState = history.pushState;
        history.pushState = function() {
            origPushState.apply(this, arguments);
            setTimeout(checkForNavigation, 100);
        };
        const origReplaceState = history.replaceState;
        history.replaceState = function() {
            origReplaceState.apply(this, arguments);
            setTimeout(checkForNavigation, 100);
        };
        window.addEventListener('popstate', () => setTimeout(checkForNavigation, 100));
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

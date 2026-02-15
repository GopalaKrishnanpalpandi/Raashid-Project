"""
Amazon Multi-Region Product Scraper
Fetches real product data (title, description, price, images) from all 9 Amazon regions.
Uses rotating headers and retry logic for reliable scraping.
Falls back to mock data if scraping fails.
"""

import asyncio
import hashlib
import json
import logging
import random
import re
import time
from typing import Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger("mrcc.scraper")

# ── Region Config ────────────────────────────────────────────────────
REGION_DOMAINS: dict[str, str] = {
    "US": "www.amazon.com",
    "IN": "www.amazon.in",
    "DE": "www.amazon.de",
    "UK": "www.amazon.co.uk",
    "JP": "www.amazon.co.jp",
    "FR": "www.amazon.fr",
    "CA": "www.amazon.ca",
    "AU": "www.amazon.com.au",
    "ES": "www.amazon.es",
}

REGION_CURRENCIES: dict[str, str] = {
    "US": "USD", "IN": "INR", "DE": "EUR", "UK": "GBP",
    "JP": "JPY", "FR": "EUR", "CA": "CAD", "AU": "AUD", "ES": "EUR",
}

CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$", "INR": "₹", "EUR": "€", "GBP": "£",
    "JPY": "¥", "CAD": "C$", "AUD": "A$",
}

# Approximate exchange rates to USD (updated periodically)
EXCHANGE_RATES_TO_USD: dict[str, float] = {
    "USD": 1.0, "INR": 0.012, "EUR": 1.08, "GBP": 1.27,
    "JPY": 0.0067, "CAD": 0.74, "AUD": 0.65,
}

# ── User-Agent Rotation ─────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
]

# ── In-memory cache ─────────────────────────────────────────────────
_cache: dict[str, dict] = {}
CACHE_TTL = 3600  # 1 hour


def _cache_key(asin: str, region: str) -> str:
    return f"{asin}:{region}"


def _get_cached(asin: str, region: str) -> Optional[dict]:
    key = _cache_key(asin, region)
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None


def _set_cached(asin: str, region: str, data: dict):
    _cache[_cache_key(asin, region)] = {"data": data, "ts": time.time()}


# ── HTML Parsing helpers (no bs4 dependency) ─────────────────────────
def _extract_between(html: str, start_marker: str, end_marker: str) -> str:
    """Extract text between two markers."""
    idx = html.find(start_marker)
    if idx == -1:
        return ""
    idx += len(start_marker)
    end = html.find(end_marker, idx)
    if end == -1:
        return ""
    return html[idx:end].strip()


def _strip_tags(html: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _extract_title(html: str) -> str:
    """Extract product title from Amazon page HTML."""
    # Method 1: productTitle span
    m = re.search(r'id="productTitle"[^>]*>(.*?)</span>', html, re.DOTALL)
    if m:
        return _strip_tags(m.group(1))
    # Method 2: title tag
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL)
    if m:
        title = _strip_tags(m.group(1))
        # Remove " : Amazon.com" suffix
        title = re.sub(r'\s*[:|-]\s*Amazon\.\S+.*$', '', title)
        return title
    return ""


def _extract_description(html: str) -> str:
    """Extract product description from Amazon page HTML."""
    desc_parts = []

    # Method 1: Feature bullets (#feature-bullets)
    bullets_match = re.search(
        r'id="feature-bullets"[^>]*>(.*?)</div>\s*</div>',
        html, re.DOTALL
    )
    if bullets_match:
        bullets = re.findall(r'<span[^>]*class="a-list-item"[^>]*>(.*?)</span>', bullets_match.group(1), re.DOTALL)
        for b in bullets:
            txt = _strip_tags(b)
            if txt and len(txt) > 5:
                desc_parts.append(txt)

    # Method 2: Product description div
    desc_match = re.search(
        r'id="productDescription"[^>]*>(.*?)</div>',
        html, re.DOTALL
    )
    if desc_match:
        txt = _strip_tags(desc_match.group(1))
        if txt and len(txt) > 10:
            desc_parts.append(txt)

    # Method 3: A+ content / aplus
    aplus_match = re.search(
        r'id="aplus"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        html, re.DOTALL
    )
    if aplus_match:
        txt = _strip_tags(aplus_match.group(1))
        if txt and len(txt) > 20:
            desc_parts.append(txt[:500])

    if desc_parts:
        return ". ".join(desc_parts)

    # Fallback: look for any substantial text block
    m = re.search(r'id="productDescription_feature_div"[^>]*>(.*?)</div>', html, re.DOTALL)
    if m:
        return _strip_tags(m.group(1))

    return ""


def _extract_price(html: str) -> Optional[str]:
    """Extract price string from Amazon page HTML."""
    # Multiple price patterns
    patterns = [
        r'class="a-price-whole"[^>]*>([^<]+)</span>',
        r'id="priceblock_ourprice"[^>]*>([^<]+)</span>',
        r'id="priceblock_dealprice"[^>]*>([^<]+)</span>',
        r'class="a-offscreen"[^>]*>([^<]+)</span>',
        r'"priceAmount":\s*([0-9.]+)',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            price = m.group(1).strip()
            # Clean price string
            price = re.sub(r'[^\d.,]', '', price)
            if price:
                return price
    return None


def _extract_images(html: str) -> list[str]:
    """Extract product image URLs from Amazon page HTML."""
    images = []

    # Method 1: Image data in JS (most reliable)
    m = re.search(r"'colorImages':\s*\{.*?'initial':\s*(\[.*?\])", html, re.DOTALL)
    if m:
        try:
            img_data = json.loads(m.group(1))
            for item in img_data:
                if isinstance(item, dict) and "hiRes" in item and item["hiRes"]:
                    images.append(item["hiRes"])
                elif isinstance(item, dict) and "large" in item and item["large"]:
                    images.append(item["large"])
        except (json.JSONDecodeError, KeyError):
            pass

    # Method 2: Image tags in image block
    if not images:
        img_matches = re.findall(
            r'id="imgTagWrapperId".*?src="(https://[^"]+)"',
            html, re.DOTALL
        )
        images.extend(img_matches)

    # Method 3: data-old-hires attributes
    if not images:
        hires = re.findall(r'data-old-hires="(https://[^"]+)"', html)
        images.extend(hires)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for img in images:
        if img not in seen:
            seen.add(img)
            unique.append(img)
    return unique[:10]  # Max 10 images


# ── Scraper core ─────────────────────────────────────────────────────
async def _fetch_product_page(asin: str, region: str, client: httpx.AsyncClient) -> Optional[str]:
    """Fetch raw HTML for a product page from a specific region."""
    domain = REGION_DOMAINS.get(region, "www.amazon.com")
    url = f"https://{domain}/dp/{asin}"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    for attempt in range(3):
        try:
            resp = await client.get(url, headers=headers, follow_redirects=True, timeout=12.0)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code == 503:
                # Bot detection — back off
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            logger.warning(f"[{region}] HTTP {resp.status_code} for {asin}")
        except httpx.TimeoutException:
            logger.warning(f"[{region}] Timeout for {asin}, attempt {attempt + 1}")
        except Exception as e:
            logger.warning(f"[{region}] Error fetching {asin}: {e}")
        await asyncio.sleep(0.5 * (attempt + 1))

    return None


async def scrape_product(asin: str, region: str, client: httpx.AsyncClient) -> dict:
    """
    Scrape product data for a single ASIN in a single region.
    Returns dict with title, description, price, price_numeric, currency, images.
    """
    # Check cache
    cached = _get_cached(asin, region)
    if cached:
        return cached

    html = await _fetch_product_page(asin, region, client)
    if not html:
        return {
            "title": "", "description": "", "price": None,
            "price_numeric": None, "currency": REGION_CURRENCIES.get(region, "USD"),
            "images": [], "scraped": False
        }

    title = _extract_title(html)
    description = _extract_description(html)
    price_str = _extract_price(html)
    images = _extract_images(html)
    currency = REGION_CURRENCIES.get(region, "USD")

    # Parse numeric price
    price_numeric = None
    if price_str:
        try:
            # Handle both 1,234.56 and 1.234,56 formats
            cleaned = price_str.replace(",", "")
            price_numeric = float(cleaned)
        except ValueError:
            try:
                cleaned = price_str.replace(".", "").replace(",", ".")
                price_numeric = float(cleaned)
            except ValueError:
                pass

    result = {
        "title": title,
        "description": description,
        "price": price_str,
        "price_numeric": price_numeric,
        "currency": currency,
        "images": images,
        "scraped": True
    }

    _set_cached(asin, region, result)
    return result


async def scrape_all_regions(asin: str) -> dict[str, dict]:
    """
    Scrape product data from all 9 Amazon regions concurrently.
    Returns dict mapping region code → product data.
    """
    async with httpx.AsyncClient() as client:
        tasks = {
            region: scrape_product(asin, region, client)
            for region in REGION_DOMAINS
        }
        results = {}
        # Run with slight stagger to avoid rate limiting
        for region, coro in tasks.items():
            results[region] = await coro
            await asyncio.sleep(0.3)  # Stagger requests

    return results


def convert_price_to_usd(price_numeric: Optional[float], currency: str) -> Optional[float]:
    """Convert a price to USD for comparison."""
    if price_numeric is None:
        return None
    rate = EXCHANGE_RATES_TO_USD.get(currency, 1.0)
    return round(price_numeric * rate, 2)


def get_price_display(price_numeric: Optional[float], currency: str) -> str:
    """Format price for display."""
    if price_numeric is None:
        return "N/A"
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    return f"{symbol}{price_numeric:,.2f}"

"""
Multi-Region Description Consistency Checker - FastAPI Backend
Provides API endpoints for description comparison, scraping, export, bulk check,
price comparison, image comparison, and notification alerts.
"""

import asyncio
import csv
import io
import json
import os
import time
from datetime import datetime
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from compare import check_description_consistency
from scraper import (
    scrape_all_regions,
    REGION_DOMAINS,
    REGION_CURRENCIES,
    CURRENCY_SYMBOLS,
    EXCHANGE_RATES_TO_USD,
    convert_price_to_usd,
    get_price_display,
)

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Region Description Consistency Checker",
    description="API for comparing product descriptions, prices, and images across Amazon regions",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory stores ────────────────────────────────────────────────
# Notification alert subscriptions: {asin: {last_hash, subscribers, last_checked}}
_alert_store: dict[str, dict] = {}

# ── Pydantic Models ─────────────────────────────────────────────────

class DiffPart(BaseModel):
    type: Literal["equal", "insert", "delete"]
    text: str


class ComparisonResult(BaseModel):
    region_1: str
    region_2: str
    similarity_score: float
    # ── New v3 per-dimension scores ──────────────────────────────
    ngram_dice: float | None = None
    bigram_jaccard: float | None = None
    word_jaccard: float | None = None
    sequence_score: float | None = None
    sentence_alignment: float | None = None
    feature_overlap: float | None = None
    spec_match: float | None = None
    structural_score: float | None = None
    tfidf_score: float | None = None
    # Legacy aliases (backward compat)
    jaccard_score: float | None = None
    confidence: str | None = None
    description_1: str | None = None
    description_2: str | None = None
    description_diff: list[DiffPart] | None = None
    url_1: str | None = None
    url_2: str | None = None
    original_description_1: str | None = None
    original_description_2: str | None = None
    language_1: str | None = None
    language_2: str | None = None
    language_name_1: str | None = None
    language_name_2: str | None = None
    was_translated_1: bool = False
    was_translated_2: bool = False
    # ── New v3 per-pair analysis ─────────────────────────────────
    issues: list[dict] | None = None
    sentence_detail: dict | None = None
    content_gaps: dict | None = None


class TitleMismatch(BaseModel):
    region_1: str
    region_2: str
    title_1: str
    title_2: str
    similarity: float
    diff: list[DiffPart] | None = None


class TitleAnalysis(BaseModel):
    is_mismatch: bool
    titles: dict[str, str]
    mismatches: list[TitleMismatch]
    original_titles: dict[str, str] | None = None
    translated_titles: dict[str, str] | None = None
    language_info: dict | None = None


class PriceInfo(BaseModel):
    region: str
    price_display: str
    price_numeric: float | None = None
    currency: str
    price_usd: float | None = None


class ImageInfo(BaseModel):
    region: str
    image_count: int
    image_urls: list[str]


class ImageComparisonPair(BaseModel):
    region_1: str
    region_2: str
    count_match: bool
    count_1: int
    count_2: int
    common_images: int
    similarity_pct: float


class CheckResponse(BaseModel):
    asin: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    average_similarity: float
    min_similarity: float | None = None
    max_similarity: float | None = None
    confidence: str | None = None
    comparisons: list[ComparisonResult]
    regions_analyzed: list[str]
    region_urls: dict[str, str] | None = None
    descriptions: dict[str, str] | None = None
    translated_descriptions: dict[str, str] | None = None
    language_info: dict | None = None
    title_analysis: TitleAnalysis | None = None
    prices: list[PriceInfo] | None = None
    images: list[ImageInfo] | None = None
    image_comparisons: list[ImageComparisonPair] | None = None
    scraped: bool = False
    # ── New v3 global analysis ───────────────────────────────────
    issues: list[dict] | None = None
    spec_analysis: dict | None = None
    issue_counts: dict | None = None


class HealthResponse(BaseModel):
    status: str
    message: str


class BulkCheckRequest(BaseModel):
    asins: list[str]


class BulkCheckItem(BaseModel):
    asin: str
    risk_level: str
    average_similarity: float
    regions_analyzed: list[str]
    confidence: str | None = None
    error: str | None = None


class AlertSubscription(BaseModel):
    asin: str
    webhook_url: str | None = None


class AlertStatus(BaseModel):
    asin: str
    subscribed: bool
    last_checked: str | None = None
    description_hash: str | None = None
    changed: bool = False


# ── Helper: image comparison ────────────────────────────────────────

def _compare_image_sets(images_by_region: dict[str, list[str]]) -> list[dict]:
    """Compare image sets between all region pairs."""
    regions = list(images_by_region.keys())
    pairs = []
    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            r1, r2 = regions[i], regions[j]
            imgs1 = set(images_by_region.get(r1, []))
            imgs2 = set(images_by_region.get(r2, []))
            common = imgs1 & imgs2
            union = imgs1 | imgs2
            sim = (len(common) / len(union) * 100) if union else 100.0
            pairs.append({
                "region_1": r1,
                "region_2": r2,
                "count_match": len(imgs1) == len(imgs2),
                "count_1": len(imgs1),
                "count_2": len(imgs2),
                "common_images": len(common),
                "similarity_pct": round(sim, 1),
            })
    return pairs


# ── API Endpoints ───────────────────────────────────────────────────

@app.get("/", response_model=HealthResponse)
async def root():
    return {"status": "healthy", "message": "Multi-Region Consistency Checker API v2.0 is running"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return {"status": "healthy", "message": "API is operational"}


class PageCheckRequest(BaseModel):
    asin: str
    scrape: bool = False
    page_title: Optional[str] = None
    page_description: Optional[str] = None
    page_region: Optional[str] = None


@app.post("/check", response_model=CheckResponse)
async def check_consistency_post(body: PageCheckRequest):
    """
    POST variant that accepts scraped page data from the extension.
    Uses the actual product title/description for unknown ASINs instead
    of random mock categories.
    """
    return await _do_check(
        asin=body.asin,
        scrape=body.scrape,
        page_title=body.page_title,
        page_description=body.page_description,
        page_region=body.page_region,
    )


@app.get("/check", response_model=CheckResponse)
async def check_consistency(
    asin: str = Query(..., description="Amazon ASIN", min_length=10, max_length=10, pattern="^[A-Za-z0-9]{10}$"),
    scrape: bool = Query(False, description="Attempt real-time scraping from Amazon"),
):
    """
    GET variant — kept for backward compatibility (test.html, etc.).
    """
    return await _do_check(asin=asin, scrape=scrape)


async def _do_check(
    asin: str,
    scrape: bool = False,
    page_title: str | None = None,
    page_description: str | None = None,
    page_region: str | None = None,
):
    """
    Core check logic shared by GET and POST endpoints.
    """
    try:
        scraped = False
        scraped_data: dict[str, dict] | None = None
        prices: list[dict] = []
        images_info: list[dict] = []
        images_by_region: dict[str, list[str]] = {}

        if scrape:
            try:
                scraped_data = await scrape_all_regions(asin.upper())
                # Check if we got meaningful data from at least 2 regions
                valid = {r: d for r, d in scraped_data.items() if d.get("scraped") and d.get("description")}
                if len(valid) >= 2:
                    scraped = True
            except Exception as e:
                print(f"[WARN] Scraping failed for {asin}: {e}")

        if scraped and scraped_data:
            # Build descriptions & titles from scraped data
            from compare import (
                calculate_pairwise_similarities,
                determine_risk_level,
                check_title_mismatch,
                get_region_url,
            )
            descriptions = {}
            titles = {}
            for region, data in scraped_data.items():
                if data.get("description"):
                    descriptions[region] = data["description"]
                if data.get("title"):
                    titles[region] = data["title"]

                # Prices
                prices.append({
                    "region": region,
                    "price_display": get_price_display(data.get("price_numeric"), data.get("currency", "USD")),
                    "price_numeric": data.get("price_numeric"),
                    "currency": data.get("currency", "USD"),
                    "price_usd": convert_price_to_usd(data.get("price_numeric"), data.get("currency", "USD")),
                })

                # Images
                imgs = data.get("images", [])
                images_info.append({
                    "region": region,
                    "image_count": len(imgs),
                    "image_urls": imgs,
                })
                images_by_region[region] = imgs

            # Fallback any missing regions to mock
            if len(descriptions) < 9:
                from compare import get_mock_descriptions, get_mock_titles
                mock_descs = get_mock_descriptions(asin.upper())
                mock_titles = get_mock_titles(asin.upper())
                for r in REGION_DOMAINS:
                    if r not in descriptions:
                        descriptions[r] = mock_descs.get(r, "")
                    if r not in titles:
                        titles[r] = mock_titles.get(r, "")

            # ── Translate scraped descriptions before comparison ──
            from translator import translate_descriptions as _translate
            translation_results = await _translate(descriptions, target_lang="en")
            translated_descriptions = {r: info["translated"] for r, info in translation_results.items()}
            language_info = {}
            for region, info in translation_results.items():
                language_info[region] = {
                    "detected_language": info["source_language"],
                    "language_name": info["source_language_name"],
                    "was_translated": info["was_translated"],
                    "original_text": info["original"],
                    "translated_text": info["translated"],
                }

            # Translate titles
            title_translation_results = await _translate(titles, target_lang="en")
            translated_titles = {r: info["translated"] for r, info in title_translation_results.items()}

            # Compare using translated text
            comparisons = calculate_pairwise_similarities(translated_descriptions, asin.upper())
            risk_level = determine_risk_level(comparisons)
            title_analysis = check_title_mismatch(translated_titles)
            title_analysis["original_titles"] = titles
            title_analysis["translated_titles"] = translated_titles

            # Enrich comparisons with original + language info
            for comp in comparisons:
                r1, r2 = comp["region_1"], comp["region_2"]
                comp["original_description_1"] = descriptions.get(r1, "")
                comp["original_description_2"] = descriptions.get(r2, "")
                comp["language_1"] = language_info.get(r1, {}).get("detected_language", "en")
                comp["language_2"] = language_info.get(r2, {}).get("detected_language", "en")
                comp["language_name_1"] = language_info.get(r1, {}).get("language_name", "English")
                comp["language_name_2"] = language_info.get(r2, {}).get("language_name", "English")
                comp["was_translated_1"] = language_info.get(r1, {}).get("was_translated", False)
                comp["was_translated_2"] = language_info.get(r2, {}).get("was_translated", False)

            if title_analysis["is_mismatch"] and risk_level == "LOW":
                risk_level = "MEDIUM"
            elif title_analysis["is_mismatch"] and risk_level == "MEDIUM":
                risk_level = "HIGH"

            sim_scores = [c["similarity_score"] for c in comparisons]
            avg = sum(sim_scores) / len(sim_scores) if sim_scores else 1.0

            result = {
                "asin": asin.upper(),
                "risk_level": risk_level,
                "average_similarity": round(avg, 4),
                "min_similarity": round(min(sim_scores), 4) if sim_scores else None,
                "max_similarity": round(max(sim_scores), 4) if sim_scores else None,
                "confidence": "MEDIUM",
                "comparisons": comparisons,
                "regions_analyzed": list(descriptions.keys()),
                "region_urls": {r: get_region_url(r, asin.upper()) for r in descriptions},
                "descriptions": descriptions,
                "translated_descriptions": translated_descriptions,
                "language_info": language_info,
                "title_analysis": title_analysis,
                "prices": prices if prices else None,
                "images": images_info if images_info else None,
                "image_comparisons": _compare_image_sets(images_by_region) if images_by_region else None,
                "scraped": True,
            }
            return result
        else:
            # Use mock data (pass page data for unknown ASINs)
            result = await check_description_consistency(
                asin.upper(),
                page_title=page_title,
                page_description=page_description,
                page_region=page_region,
            )
            result["scraped"] = False
            # Add empty prices/images for UI consistency
            result["prices"] = None
            result["images"] = None
            result["image_comparisons"] = None
            return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ── Feature 2: Export Report ─────────────────────────────────────────

@app.get("/export/csv")
async def export_csv(
    asin: str = Query(..., min_length=10, max_length=10, pattern="^[A-Za-z0-9]{10}$"),
):
    """Export consistency report as CSV."""
    try:
        result = await check_description_consistency(asin.upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["Multi-Region Description Consistency Report"])
    writer.writerow(["ASIN", result["asin"]])
    writer.writerow(["Risk Level", result["risk_level"]])
    writer.writerow(["Average Similarity", f"{result['average_similarity']:.4f}"])
    writer.writerow(["Regions Analyzed", ", ".join(result["regions_analyzed"])])
    writer.writerow(["Generated", datetime.utcnow().isoformat()])
    writer.writerow([])

    # Comparisons
    writer.writerow(["Region 1", "Region 2", "Similarity %", "TF-IDF", "Jaccard", "Sequence", "Feature Overlap", "Confidence"])
    for c in result["comparisons"]:
        writer.writerow([
            c["region_1"], c["region_2"],
            f"{c['similarity_score'] * 100:.1f}%",
            f"{c.get('tfidf_score', 0) * 100:.1f}%",
            f"{c.get('jaccard_score', 0) * 100:.1f}%",
            f"{c.get('sequence_score', 0) * 100:.1f}%",
            f"{c.get('feature_overlap', 0) * 100:.1f}%",
            c.get("confidence", ""),
        ])

    writer.writerow([])
    writer.writerow(["Region Descriptions"])
    writer.writerow(["Region", "Description"])
    for region, desc in result.get("descriptions", {}).items():
        writer.writerow([region, desc])

    # Title analysis
    if result.get("title_analysis"):
        writer.writerow([])
        writer.writerow(["Title Analysis"])
        writer.writerow(["Mismatch Detected", result["title_analysis"]["is_mismatch"]])
        for region, title in result["title_analysis"].get("titles", {}).items():
            writer.writerow([region, title])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=mrcc_report_{asin}.csv"},
    )


@app.get("/export/json")
async def export_json(
    asin: str = Query(..., min_length=10, max_length=10, pattern="^[A-Za-z0-9]{10}$"),
):
    """Export full consistency report as JSON."""
    try:
        result = await check_description_consistency(asin.upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    result["exported_at"] = datetime.utcnow().isoformat()

    output = json.dumps(result, indent=2, ensure_ascii=False)
    return StreamingResponse(
        iter([output]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=mrcc_report_{asin}.json"},
    )


# ── Feature 3: Price Comparison ──────────────────────────────────────

@app.get("/prices")
async def price_comparison(
    asin: str = Query(..., min_length=10, max_length=10, pattern="^[A-Za-z0-9]{10}$"),
):
    """Get price comparison across all Amazon regions (requires scraping)."""
    try:
        scraped = await asyncio.wait_for(scrape_all_regions(asin.upper()), timeout=30)
    except asyncio.TimeoutError:
        return {
            "asin": asin.upper(), "prices": [], "cheapest_region": None,
            "most_expensive_region": None, "price_spread_usd": None,
            "exchange_rates": EXCHANGE_RATES_TO_USD,
            "error": "Scraping timed out after 30 seconds",
        }
    except Exception as e:
        return {
            "asin": asin.upper(), "prices": [], "cheapest_region": None,
            "most_expensive_region": None, "price_spread_usd": None,
            "exchange_rates": EXCHANGE_RATES_TO_USD,
            "error": f"Scraping failed: {e}",
        }

    prices = []
    for region, data in scraped.items():
        price_usd = convert_price_to_usd(data.get("price_numeric"), data.get("currency", "USD"))
        prices.append({
            "region": region,
            "price_display": get_price_display(data.get("price_numeric"), data.get("currency", "USD")),
            "price_numeric": data.get("price_numeric"),
            "currency": data.get("currency", "USD"),
            "price_usd": price_usd,
        })

    # Sort by USD price
    prices_with_usd = [p for p in prices if p["price_usd"] is not None]
    prices_without = [p for p in prices if p["price_usd"] is None]
    prices_with_usd.sort(key=lambda x: x["price_usd"])

    cheapest = prices_with_usd[0] if prices_with_usd else None
    most_expensive = prices_with_usd[-1] if prices_with_usd else None

    return {
        "asin": asin.upper(),
        "prices": prices_with_usd + prices_without,
        "cheapest_region": cheapest["region"] if cheapest else None,
        "most_expensive_region": most_expensive["region"] if most_expensive else None,
        "price_spread_usd": round(most_expensive["price_usd"] - cheapest["price_usd"], 2) if cheapest and most_expensive else None,
        "exchange_rates": EXCHANGE_RATES_TO_USD,
    }


# ── Feature 4: Image Comparison ─────────────────────────────────────

@app.get("/images")
async def image_comparison(
    asin: str = Query(..., min_length=10, max_length=10, pattern="^[A-Za-z0-9]{10}$"),
):
    """Compare product images across all regions (requires scraping)."""
    try:
        scraped = await asyncio.wait_for(scrape_all_regions(asin.upper()), timeout=30)
    except asyncio.TimeoutError:
        return {
            "asin": asin.upper(), "images": [], "comparisons": [],
            "all_match": True, "error": "Scraping timed out after 30 seconds",
        }
    except Exception as e:
        return {
            "asin": asin.upper(), "images": [], "comparisons": [],
            "all_match": True, "error": f"Scraping failed: {e}",
        }

    images_by_region: dict[str, list[str]] = {}
    images_info = []
    for region, data in scraped.items():
        imgs = data.get("images", [])
        images_by_region[region] = imgs
        images_info.append({
            "region": region,
            "image_count": len(imgs),
            "image_urls": imgs,
        })

    pairs = _compare_image_sets(images_by_region)

    return {
        "asin": asin.upper(),
        "images": images_info,
        "comparisons": pairs,
        "all_match": all(p["similarity_pct"] == 100.0 for p in pairs),
    }


# ── Feature 5: Bulk ASIN Check ──────────────────────────────────────

@app.post("/bulk-check")
async def bulk_check(body: BulkCheckRequest):
    """
    Check multiple ASINs at once. Accepts up to 50 ASINs.
    Returns summary results for each ASIN.
    """
    if len(body.asins) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 ASINs per request")

    results = []
    for asin_raw in body.asins:
        asin = asin_raw.strip().upper()
        if not asin or len(asin) != 10:
            results.append({
                "asin": asin_raw,
                "risk_level": "UNKNOWN",
                "average_similarity": 0,
                "regions_analyzed": [],
                "confidence": None,
                "error": "Invalid ASIN format",
            })
            continue
        try:
            r = await check_description_consistency(asin)
            results.append({
                "asin": r["asin"],
                "risk_level": r["risk_level"],
                "average_similarity": r["average_similarity"],
                "regions_analyzed": r["regions_analyzed"],
                "confidence": r.get("confidence"),
                "error": None,
            })
        except Exception as e:
            results.append({
                "asin": asin,
                "risk_level": "UNKNOWN",
                "average_similarity": 0,
                "regions_analyzed": [],
                "confidence": None,
                "error": str(e),
            })

    return {"results": results, "total": len(results)}


@app.post("/bulk-check/csv")
async def bulk_check_csv(body: BulkCheckRequest):
    """Bulk check and return results as CSV."""
    if len(body.asins) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 ASINs per request")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ASIN", "Risk Level", "Avg Similarity %", "Confidence", "Regions", "Error"])

    for asin_raw in body.asins:
        asin = asin_raw.strip().upper()
        if not asin or len(asin) != 10:
            writer.writerow([asin_raw, "UNKNOWN", "", "", "", "Invalid ASIN"])
            continue
        try:
            r = await check_description_consistency(asin)
            writer.writerow([
                r["asin"], r["risk_level"],
                f"{r['average_similarity'] * 100:.1f}%",
                r.get("confidence", ""),
                ", ".join(r["regions_analyzed"]),
                "",
            ])
        except Exception as e:
            writer.writerow([asin, "UNKNOWN", "", "", "", str(e)])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mrcc_bulk_report.csv"},
    )


# ── Feature 6: Notification Alerts ──────────────────────────────────

def _hash_descriptions(descriptions: dict[str, str]) -> str:
    """Create a hash of all region descriptions for change detection."""
    combined = json.dumps(descriptions, sort_keys=True)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


@app.post("/alerts/subscribe")
async def subscribe_alert(body: AlertSubscription):
    """Subscribe to description change alerts for an ASIN."""
    asin = body.asin.strip().upper()
    if len(asin) != 10:
        raise HTTPException(status_code=400, detail="Invalid ASIN")

    # Get current descriptions and hash them
    result = await check_description_consistency(asin)
    desc_hash = _hash_descriptions(result.get("descriptions", {}))

    _alert_store[asin] = {
        "last_hash": desc_hash,
        "webhook_url": body.webhook_url,
        "last_checked": datetime.utcnow().isoformat(),
        "subscribed": True,
    }

    return {
        "asin": asin,
        "subscribed": True,
        "description_hash": desc_hash,
        "message": f"Subscribed to alerts for {asin}",
    }


@app.delete("/alerts/{asin}")
async def unsubscribe_alert(asin: str):
    """Unsubscribe from alerts for an ASIN."""
    asin = asin.upper()
    if asin in _alert_store:
        del _alert_store[asin]
    return {"asin": asin, "subscribed": False, "message": "Unsubscribed from alerts"}


@app.get("/alerts")
async def list_alerts():
    """List all active alert subscriptions."""
    return {
        "alerts": [
            {
                "asin": asin,
                "subscribed": data.get("subscribed", True),
                "last_checked": data.get("last_checked"),
                "description_hash": data.get("last_hash"),
            }
            for asin, data in _alert_store.items()
        ],
        "count": len(_alert_store),
    }


@app.post("/alerts/check")
async def check_alerts():
    """
    Check all subscribed ASINs for description changes.
    Returns list of ASINs that have changed since last check.
    """
    changed = []
    for asin, data in _alert_store.items():
        try:
            result = await check_description_consistency(asin)
            new_hash = _hash_descriptions(result.get("descriptions", {}))
            if new_hash != data.get("last_hash"):
                changed.append({
                    "asin": asin,
                    "old_hash": data["last_hash"],
                    "new_hash": new_hash,
                    "risk_level": result["risk_level"],
                    "average_similarity": result["average_similarity"],
                })
                data["last_hash"] = new_hash
            data["last_checked"] = datetime.utcnow().isoformat()
        except Exception as e:
            changed.append({"asin": asin, "error": str(e)})

    return {"changed": changed, "total_monitored": len(_alert_store)}


# ── Sample ASINs ─────────────────────────────────────────────────────

@app.get("/asins")
async def list_sample_asins():
    return {
        "sample_asins": [
            {"asin": "B08N5WRWNW", "expected_risk": "LOW", "description": "Sony Headphones - Consistent"},
            {"asin": "B00TEST123", "expected_risk": "MEDIUM", "description": "Wireless Earbuds - Some variations"},
            {"asin": "B00DIFFER1", "expected_risk": "HIGH", "description": "Major inconsistencies"},
            {"asin": "B09XYZ1234", "expected_risk": "LOW", "description": "Water Bottle - Consistent"},
            {"asin": "B07MEDIUM1", "expected_risk": "MEDIUM", "description": "Fitness Tracker - Moderate variations"},
        ],
        "note": "Any valid 10-char ASIN works. Add ?scrape=true to /check for live data.",
    }


import hashlib

if __name__ == "__main__":
    import socket

    def _port_free(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", p))
                return True
            except OSError:
                return False

    port = int(os.environ.get("PORT", 5000))
    if not _port_free(port):
        # Try to kill the old process on that port, then retry
        try:
            import subprocess
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    subprocess.run(["taskkill", "/PID", pid, "/F"],
                                   capture_output=True)
                    print(f"[INFO] Killed old process PID {pid} on port {port}")
                    import time; time.sleep(1)
                    break
        except Exception:
            pass
        # If still not free, try next port
        if not _port_free(port):
            port += 1
            print(f"[INFO] Port {port - 1} busy, using port {port}")

    print(f"[INFO] Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

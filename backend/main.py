"""
Multi-Region Description Consistency Checker - FastAPI Backend
Provides API endpoint to check product description consistency across Amazon regions.
"""

import os

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import uvicorn

from compare import check_description_consistency

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Region Description Consistency Checker",
    description="API to compare product descriptions across different Amazon regions and detect inconsistencies",
    version="1.0.0"
)

# Enable CORS for Chrome Extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for extension
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response Models
class ComparisonResult(BaseModel):
    region_1: str
    region_2: str
    similarity_score: float
    tfidf_score: float | None = None
    jaccard_score: float | None = None
    sequence_score: float | None = None
    feature_overlap: float | None = None
    confidence: str | None = None


class DiffPart(BaseModel):
    type: Literal["equal", "insert", "delete"]
    text: str


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


class CheckResponse(BaseModel):
    asin: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    average_similarity: float
    min_similarity: float | None = None
    max_similarity: float | None = None
    confidence: str | None = None
    comparisons: list[ComparisonResult]
    regions_analyzed: list[str]
    title_analysis: TitleAnalysis | None = None


class HealthResponse(BaseModel):
    status: str
    message: str


# API Endpoints
@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "Multi-Region Description Consistency Checker API is running"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "API is operational"
    }


@app.get("/check", response_model=CheckResponse)
async def check_consistency(
    asin: str = Query(
        ...,
        description="Amazon Standard Identification Number (ASIN) to check",
        min_length=10,
        max_length=10,
        regex="^[A-Z0-9]{10}$"
    )
):
    """
    Check description consistency for a given ASIN across multiple Amazon regions.
    
    **Parameters:**
    - **asin**: 10-character Amazon ASIN (e.g., B08N5WRWNW)
    
    **Returns:**
    - **asin**: The queried ASIN
    - **risk_level**: LOW, MEDIUM, or HIGH based on description variance
    - **average_similarity**: Average similarity score across all region pairs
    - **comparisons**: Detailed similarity scores for each region pair
    - **regions_analyzed**: List of regions compared (US, IN, DE)
    
    **Risk Level Thresholds:**
    - LOW: Similarity >= 80% (descriptions are consistent)
    - MEDIUM: Similarity 50-79% (some differences exist)
    - HIGH: Similarity < 50% (significant discrepancies detected)
    """
    try:
        result = check_description_consistency(asin.upper())
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


@app.get("/asins")
async def list_sample_asins():
    """
    List sample ASINs available for testing with their expected risk levels.
    Useful for demo and testing purposes.
    """
    return {
        "sample_asins": [
            {
                "asin": "B08N5WRWNW",
                "expected_risk": "LOW",
                "description": "Sony Headphones - Nearly identical descriptions across regions"
            },
            {
                "asin": "B00TEST123",
                "expected_risk": "MEDIUM",
                "description": "Wireless Earbuds - Some variations in descriptions"
            },
            {
                "asin": "B00DIFFER1",
                "expected_risk": "HIGH",
                "description": "Different products described - Major inconsistencies"
            },
            {
                "asin": "B09XYZ1234",
                "expected_risk": "LOW",
                "description": "Water Bottle - Consistent descriptions"
            },
            {
                "asin": "B07MEDIUM1",
                "expected_risk": "MEDIUM",
                "description": "Fitness Tracker - Moderate variations"
            }
        ],
        "note": "Any other valid 10-character ASIN will generate random mock data"
    }


if __name__ == "__main__":
    # Run with: python main.py
    # Or: uvicorn main:app --reload --port 5000
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)

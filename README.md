# Multi-Region Description Consistency Checker

A Chrome Extension + Python FastAPI backend system that detects ASINs on Amazon pages, compares product descriptions across US/IN/DE regions using TF-IDF + cosine similarity, and displays a color-coded risk badge indicating description variance.

## 🏗️ Project Structure

```
multi-region-consistency-checker/
├── backend/
│   ├── main.py              # FastAPI application entry point
│   ├── compare.py           # TF-IDF similarity comparison logic
│   └── requirements.txt     # Python dependencies
├── extension/
│   ├── manifest.json        # Chrome Extension Manifest V3
│   ├── content.js           # Content script for ASIN detection & UI
│   └── icons/               # Extension icons
│       ├── icon16.png
│       ├── icon48.png
│       └── icon128.png
├── test.html                # Test page to simulate Amazon product page
└── README.md
```

## 🚀 Quick Start

### 1. Start the Backend Server

```bash
# Navigate to backend folder
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```

The API will be available at `http://localhost:5000`

### 2. Load the Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `extension` folder from this project
5. The extension is now installed!

### 3. Test the Extension

1. Open `test.html` in Chrome (right-click → Open with Chrome, or use a local server)
2. The extension will detect the ASIN and show a floating badge in the top-right corner
3. Click the badge to see detailed comparison results
4. Use the test buttons to try different ASINs with varying risk levels

## 📡 API Endpoints

### `GET /check?asin={ASIN}`

Check description consistency for a given ASIN.

**Parameters:**
- `asin` (required): 10-character Amazon ASIN (e.g., B08N5WRWNW)

**Response:**
```json
{
  "asin": "B08N5WRWNW",
  "risk_level": "LOW",
  "average_similarity": 0.9234,
  "comparisons": [
    {"region_1": "US", "region_2": "IN", "similarity_score": 0.9456},
    {"region_1": "US", "region_2": "DE", "similarity_score": 0.9123},
    {"region_1": "IN", "region_2": "DE", "similarity_score": 0.9123}
  ],
  "regions_analyzed": ["US", "IN", "DE"]
}
```

### `GET /asins`

List sample ASINs available for testing.

### `GET /health`

Health check endpoint.

## 🎯 Risk Level Thresholds

| Risk Level | Similarity Score | Meaning |
|------------|-----------------|---------|
| 🟢 LOW | ≥ 80% | Descriptions are consistent across regions |
| 🟠 MEDIUM | 50% - 79% | Some differences exist, review recommended |
| 🔴 HIGH | < 50% | Significant discrepancies detected |

## 🧪 Sample ASINs for Testing

| ASIN | Expected Risk | Description |
|------|---------------|-------------|
| B08N5WRWNW | LOW | Sony Headphones - Nearly identical descriptions |
| B00TEST123 | MEDIUM | Wireless Earbuds - Some variations |
| B00DIFFER1 | HIGH | Different products described - Major inconsistencies |
| B09XYZ1234 | LOW | Water Bottle - Consistent descriptions |
| B07MEDIUM1 | MEDIUM | Fitness Tracker - Moderate variations |

## 🔧 How It Works

### Backend (FastAPI + scikit-learn)

1. Receives ASIN from Chrome extension
2. Retrieves mock product descriptions for 3 regions (US, IN, DE)
3. Uses TF-IDF vectorization to convert text to numerical vectors
4. Calculates cosine similarity between all region pairs
5. Determines risk level based on average similarity
6. Returns JSON response with detailed comparisons

### Chrome Extension (Manifest V3)

1. Runs on all URLs (`<all_urls>` permission)
2. Scans page for ASIN patterns:
   - `ASIN: XXXXXXXXXX` in text
   - `/dp/XXXXXXXXXX` in URL
   - `data-asin="XXXXXXXXXX"` attributes
3. Calls backend API with detected ASIN
4. Displays floating badge with color-coded risk level
5. Shows detailed modal on badge click

## 🛠️ Development

### Running in Development Mode

```bash
# Backend with auto-reload
cd backend
uvicorn main:app --reload --port 5000

# For the extension, after making changes:
# Go to chrome://extensions and click the refresh icon on the extension
```

### API Documentation

When the backend is running, visit:
- Swagger UI: `http://localhost:5000/docs`
- ReDoc: `http://localhost:5000/redoc`

## 📝 Notes

- This is a **demo prototype** using mock data
- No actual Amazon API integration - descriptions are simulated
- German (DE) region uses English text for cleaner similarity comparison in the demo
- Unknown ASINs generate random mock data with varying similarity levels

## 🔒 Security Considerations

- CORS is enabled for all origins (development only)
- For production, restrict `allow_origins` to specific domains
- The extension only communicates with `localhost:5000`

## 📦 Dependencies

### Python (Backend)
- FastAPI 0.104.1
- Uvicorn 0.24.0
- scikit-learn 1.3.2
- Pydantic 2.5.2
- NumPy 1.26.2

### Chrome Extension
- Manifest V3
- No external dependencies

## 📄 License

MIT License - Feel free to use and modify for your needs.

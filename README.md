# TruthLens AI: Multimodal Fact Verification Engine

![Version](https://img.shields.io/badge/version-1.6.4-blue)
![Python](https://img.shields.io/badge/python-3.9+-yellow)
![React](https://img.shields.io/badge/react-18-blue)
![License](https://img.shields.io/badge/license-MIT-green)

TruthLens AI is a production-grade investigative tool designed to combat the global epidemic of misinformation. It provides an automated, evidence-based platform for verifying the authenticity of text claims, images, and combined multimodal content using real-time internet cross-referencing and advanced AI reasoning.

## 🎯 Overview

In an era of deepfakes and algorithmic disinformation, TruthLens AI bridges the gap between raw content and verified truth. Unlike traditional search engines, TruthLens AI extracts specific factual claims and performs a deep "Investigative Audit" by retrieving live evidence from credible sources (Wikipedia, Google Search via DuckDuckGo) and synthesizing a human-readable verdict with a clear **"Why"** justification.

## ✨ Key Features

-   **Text Fact Verification**: Extracts individual claims from raw text and verifies them against the latest global events (Context-aware for Jan 2026).
-   **Image Analysis & OCR**: Scans images for synthetic artifacts, composition errors, and extracts text embedded within images to catch "Meme-based" disinformation.
-   **Multimodal Reasoning**: Analyzes text and images **together** to detect cross-modal inconsistencies (e.g., a peaceful text description paired with a violent image).
-   **Live Web Cross-Checking (RAG)**: Uses Retrieval-Augmented Generation to weight real-world evidence higher than static LLM training data.
-   **Explainable AI (XAI)**: Every verdict includes a structured **Expert Reasoning** box explaining exactly *why* information was flagged.
-   **Defensive Error Handling**: Aggressive heuristics catch disinformation even when external APIs or search snippets are sparse.

## 🏗️ System Architecture

TruthLens AI uses a decoupled, modular architecture designed for stability and speed:

1.  **Frontend (React + Vite + TypeScript)**: A high-performance investigative console built with Tailwind CSS for glassmorphism aesthetics.
2.  **Backend (FastAPI)**: A high-concurrency Python server managing the analysis pipeline.
3.  **Analysis Pipeline**:
    -   **Claim Extractor**: Identifies verifiable factual units within user input.
    -   **Search Engine (ddgs)**: Retrieves live snippets from the web.
    -   **Evaluation Model (Gemini)**: Performs deep semantic reasoning on claims vs evidence.
    -   **Verdict Engine**: A deterministic logic layer that aggregates LLM scores, visual risks, and audio artifacts into a final confidence score (0.0–1.0).
    -   **Explanation Tree**: Synthesizes a structured JSON reasoning path for frontend rendering.

## 🚀 How It Works (Step-by-Step)

1.  **Submission**: User uploads text, an image, or both to the **Combined Console**.
2.  **Extraction**: Text is parsed into discrete claims; images are captioned and OCRed.
3.  **Retrieval**: The system searches DuckDuckGo and Wikipedia for contemporary evidence.
4.  **Audit**: The AI evaluates if the evidence *supports*, *contradicts*, or is *silent* regarding the claims.
5.  **Synthesis**: The Verdict Engine checks for "Hoax Patterns" and Cross-Modal mismatches.
6.  **Delivery**: The UI renders a verdict (TRUE/FAKE/MISLEADING) with a highlighted **"Why this verdict?"** reason.

## 🛠️ Technologies Used

### Frontend
-   **React**: For reactive state management of investigative results.
-   **Vite**: For ultra-fast development and build cycles.
-   **TypeScript**: Ensures type safety across complex JSON API responses.
-   **Tailwind CSS**: Modern styling with dark-mode investigative aesthetics.

### Backend
-   **Python & FastAPI**: High-performance asynchronous API handling.
-   **Uvicorn**: Scalable production server for Python.
-   **Groq Llama-3.1-70B**: The core reasoning model for claim verification (60% faster than Gemini).
-   **OpenCV & Tesseract**: For visual feature extraction and OCR.
-   **moviepy & librosa**: (Beta) For video processing and audio artifact detection.

### Data Sources
-   **DuckDuckGo Search**: For real-time news and snippet retrieval.
-   **Wikipedia API**: For established scientific and historical consensus.

## 📦 Installation Guide

### Prerequisites
-   [Node.js](https://nodejs.org/) (v18+)
-   [Python](https://www.python.org/) (v3.9+)
-   [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (Installed and in PATH)

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/TruthLens-AI.git
cd TruthLens-AI
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
*Frontend runs at: http://localhost:8080*

### 3. Backend Setup
```bash
# Create single venv in root directory (if not already created)
python -m venv venv

# Activate venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Start backend
cd backend
python run.py
```
*Backend runs at: http://localhost:9000*

## 🔑 Environment Variables

### Root Directory (`.env`)
```env
# Groq API Configuration
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### Frontend (`frontend/.env` - Optional)
```env
VITE_API_BASE_URL=http://localhost:9000/api
```

**Note:** 
- Store `.env` in the root project directory
- All backend configuration reads from root `.env`
- Never commit `.env` to version control
- Get GROQ_API_KEY from: https://console.groq.com/

## 📂 API Documentation

### `POST /api/verify/multimodal`
The primary endpoint for coordinated verification.

**Request Payload (Multipart/Form-data):**
- `text`: "The Earth is flat."
- `file`: (Optional) Image or short video file.

**Response JSON Example:**
```json
{
  "verdict": "LIKELY FAKE",
  "confidence": 0.95,
  "reasoning": [
    {
      "step": "Text Claim Verification",
      "status": "CONTRADICTED",
      "details": { "explanation": "Scientific consensus and satellite imagery prove Earth is an oblate spheroid." }
    },
    {
      "step": "Final Decision",
      "details": { "summary": "Identified as Fake. Core Reason: Explicitly refuted by credible sources." }
    }
  ]
}
```

## 🧪 Example Outputs

| Input | Verdict | Confidence | Expert Reasoning |
| :--- | :--- | :--- | :--- |
| "The Earth is a sphere" | **LIKELY TRUE** | 0.85+ | Verified as True. Core Reason: Matches established factual consensus. |
| "Drinking bleach cures viruses" | **LIKELY FAKE** | 0.95 | Identified as Fake. Core Reason: Credible sources explicitly refute this claim. |
| Combined: [Riot Image] + "Peaceful" | **MISLEADING** | 0.70 | Caution: Content contains multimodal contradictions. |
| "Future AI will be sentient" | **UNCERTAIN** | 0.35 | Uncertain. Reason: Insufficient external evidence found. |

## 🛡️ Reliability & Error Handling

-   **Zero 500 Errors**: All external API calls (Gemini, Search) are wrapped in failover try/except blocks.
-   **Smart Heuristics**: If the LLM is overloaded or the key expires, a local keyword-risk engine provides fallback analysis.
-   **Confidence Calibration**: Confidence scores are evidence-driven, not arbitrary. High scores require multi-source agreement.

## ⚠️ Limitations

-   **Source Dependency**: Performance is linked to the availability of external search results.
-   **Not a Human Proxy**: TruthLens AI is a tool to *assist* high-stakes decision-making, not a replacement for professional human fact-checkers.
-   **Image Quality**: Extremely low-resolution images may degrade OCR and artifact detection accuracy.

## 🔮 Future Enhancements

-   **Browser Extension**: Rapid verification of news articles directly in Chrome/Edge.
-   **Source Credibility Scoring**: Real-time ranking of the domain's historical accuracy.
-   **Multilingual Support**: Expanding verification to 50+ languages.

## 📄 License & Contribution

Distributed under the **MIT License**. We welcome contributions that improve the accuracy and speed of truth detection! 

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

---
**TruthLens AI** — *See through the noise.*

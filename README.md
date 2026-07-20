# Trvios AI - Trip Chat Platform

A premium python web application built using **Clean Architecture** patterns, leveraging **FastAPI** for real-time Server-Sent Events (SSE) streaming and **ChromaDB** for semantic vector search over travel itineraries.

---

## 🌟 Features

- **Clean Architecture Directory Structure**: Clear boundary separation between Domain, Application, Infrastructure, and Presentation layers.
- **Unified 1-API Engine (`POST /api/unified`)**: Single synchronous endpoint handling AI Chat, FAQ training, PDF training, Website training, MongoDB trips training, and Itinerary Planning all in 1 row.
- **Dynamic API Syncing**: Dynamically loads, maps, and stores travel itineraries from MongoDB or external Trvios API to ChromaDB.
- **Deep Semantic Querying**: Custom indexes including detailed highlights and day-by-day itinerary schedules.
- **SSE Streaming Answers**: Real-time natural language answers streaming token-by-token.
- **Premium User Experience**: Responsive layout with modern Outfit typography, glassmorphism components, and interactive slide-out drawer revealing full timeline itineraries.
- **Graceful Fallbacks**: Local word-by-word streamer fallback if no OpenAI key is configured.

---

## 📬 Postman API Collection & Sharing Guide

All APIs are pre-configured in `postman_collection.json`. You can share or import all APIs using any of the following methods:

### Option 1: Direct GitHub Link (Fastest)
1. Open **Postman** -> Click **Import** (top left).
2. Paste this URL:
   `https://raw.githubusercontent.com/Muskanyadav29/ai-voice-assistant/main/postman_collection.json`
3. Click **Import** — all 9 API endpoints will be imported into your Postman workspace!

### Option 2: Share via OpenAPI / Swagger UI
When the server is running, open the interactive browser documentation:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc UI:** `http://localhost:8000/redoc`
- **OpenAPI JSON Spec:** `http://localhost:8000/openapi.json`

---

## 📁 Folder Structure & Architecture

```text
new project/
|-- pyproject.toml              # Build system & package configurations
|-- requirements.txt            # Production dependencies
|-- postman_collection.json     # Postman API collection v2.1
|-- data/
|   `-- chroma/                 # Local vector database storage
|-- src/
|   `-- clean_app/
|       |-- main.py             # Entry point
|       |-- unified_service.py  # Merged 1-API service wrapper
|       |-- domain/             # Core business entities and repository ports (interfaces)
|       |   |-- entities/
|       |   |   `-- trip.py     # Trip and ItineraryItem domain definitions
|       |   `-- repositories/
|       |       |-- trip_repository.py
|       |       `-- vector_store.py
|       |-- application/        # Application services & Use Cases (orchestration)
|       |   |-- dto/
|       |   |   `-- trip_dto.py # Data Transfer Objects
|       |   `-- use_cases/
|       |       |-- chat_with_trips.py
|       |       |-- index_trips.py
|       |       |-- index_mongo_trips.py
|       |       |-- ingest_faq.py
|       |       |-- plan_itinerary.py
|       |       `-- list_trips.py
|       |-- infrastructure/     # Database adapters, LLM client, configurations
|       |   |-- ai/
|       |   |   `-- chat_service.py      # OpenAI Client & local fallback streamer
|       |   |-- config/
|       |   |   `-- settings.py          # Environment settings
|       |   |-- persistence/
|       |   |   |-- static_trip_repository.py
|       |   |   |-- mongo_trip_repository.py
|       |   |   `-- trvios_trip_repository.py
|       |   `-- vector/
|       |       `-- chroma_vector_store.py # ChromaDB vector store client
|       `-- presentation/       # User interaction layers (Web Assets, REST API endpoints, CLI)
|           |-- api/
|           |   |-- app.py      # FastAPI application factory
|           |   |-- run.py      # Server runner
|           |   |-- schemas.py  # Pydantic request/response validation schemas
|           |   `-- routes/
|           |       |-- unified.py    # POST /api/unified
|           |       |-- train.py      # FAQ, PDF, Website, MongoDB training
|           |       |-- itinerary.py  # Structured Itinerary Planning
|           |       |-- chat.py
|           |       `-- trips.py
|           |-- cli/
|           |   `-- run.py      # Console database diagnostics tool
|           `-- web/            # Premium Frontend assets (HTML, CSS, JS)
|               |-- index.html
|               |-- styles.css
|               `-- app.js
`-- tests/                      # Automated test suite
    |-- unit/                   # Unit tests
    `-- integration/            # API integration tests
```

---

## 🚀 Setup & Execution

### 1. Prerequisites
- Python 3.11 or later.

### 2. Environment Configurations
Create a `.env` file in the project root:
```env
APP_ENV=development
APP_DEBUG=true

# Database locations
CHROMA_PERSIST_DIR=./data/chroma
AUTO_INDEX_TRIPS=true

TRIP_SOURCE=static
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4o-mini

API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Running the Web API Server
```bash
python -m clean_app.main api
```
Access the web UI at `http://localhost:8000` and Swagger docs at `http://localhost:8000/docs`.

### 5. Running Tests
```bash
python -m pytest
```

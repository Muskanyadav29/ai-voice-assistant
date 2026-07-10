# Trvios AI - Trip Chat Platform

A premium python web application built using **Clean Architecture** patterns, leveraging **FastAPI** for real-time Server-Sent Events (SSE) streaming and **ChromaDB** for semantic vector search over travel itineraries.

---

## 🌟 Features

- **Clean Architecture Directory Structure**: Clear boundary separation between Domain, Application, Infrastructure, and Presentation layers.
- **Dynamic API Syncing**: Dynamically loads, maps, and stores travel itineraries from the external Trvios API (`https://api.trvios.com/api/ai/trips`) to ChromaDB.
- **Deep Semantic Querying**: Custom indexes including detailed highlights and day-by-day itinerary schedules.
- **SSE Streaming Answers**: Real-time natural language answers streaming token-by-token.
- **Premium User Experience**: Responsive layout with modern Outfit typography, glassmorphism components, and an interactive slide-out drawer revealing full timeline itineraries when citations are clicked.
- **Graceful Fallbacks**: Simulates high-fidelity conversational answers via a local word-by-word streamer if no OpenAI key is configured.

---

## 📁 Folder Structure & Architecture

The application strictly adheres to Clean Architecture principles:

```text
new project/
|-- pyproject.toml              # Build system & package configurations
|-- requirements.txt            # Production dependencies
|-- data/
|   `-- chroma/                 # Local vector database storage
|-- src/
|   `-- clean_app/
|       |-- main.py             # Entry point
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
|       |       `-- list_trips.py
|       |-- infrastructure/     # Database adapters, LLM client, configurations
|       |   |-- ai/
|       |   |   `-- chat_service.py      # OpenAI Client & local fallback streamer
|       |   |-- config/
|       |   |   `-- settings.py          # Environment settings
|       |   |-- persistence/
|       |   |   |-- static_trip_repository.py
|       |   |   `-- trvios_trip_repository.py  # Fetches live data from Trvios API
|       |   `-- vector/
|       |       `-- chroma_vector_store.py # ChromaDB vector store client
|       `-- presentation/       # User interaction layers (Web Assets, REST API endpoints, CLI)
|           |-- api/
|           |   |-- app.py      # FastAPI application factory
|           |   |-- run.py      # Server runner
|           |   |-- schemas.py  # Pydantic request/response validation schemas
|           |   `-- routes/
|           |       |-- chat.py
|           |       `-- trips.py
|           |-- cli/
|           |   `-- run.py      # Console database diagnostics tool
|           `-- web/            # Premium Frontend assets (HTML, CSS, JS)
|               |-- index.html
|               |-- styles.css
|               `-- app.js
`-- tests/                      # Automated test suite
    |-- unit/                   # Unit tests (Entities, Mappings)
    `-- integration/            # API integration tests (Streaming endpoints)
```

### Layer Responsibilities
1. **Domain**: Contains the core rules of our application (e.g. `Trip` entity) and is completely decoupled from any frameworks, HTTP libraries, or databases.
2. **Application**: Coordinates use cases (e.g. searching and streaming chat). Uses abstract repository interfaces (ports) to retrieve data.
3. **Infrastructure**: Implementations of the repositories. Adapts the database (ChromaDB), web services (httpx fetching the API), and OpenAI completions.
4. **Presentation**: The external entry points, including FastAPI routers, web UI elements, and validation models.

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
AUTO_INDEX_TRIPS=true # Set to true to index trips on server start

# Data Source configuration: "trvios" (live API) or "static" (trips.json)
TRIP_SOURCE=trvios
TRVIOS_TRIPS_API_URL=https://api.trvios.com/api/ai/trips

# Optional: Set OpenAI credentials to enable generative replies (falls back to local simulator without it)
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4o-mini

API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Install Dependencies
Set up your virtual environment and install the required modules:
```bash
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Running the Web API Server
Start the development server using:
```bash
# Run server
python -m clean_app.main api
```
Access the application by opening `http://localhost:8000` in your web browser.

### 5. Running the CLI Diagnostics Tool
To verify the catalog fetching, database counts, and search capabilities from the console, execute:
```bash
python -m clean_app.main
```

### 6. Running Tests
Verify the installation by running the test suite:
```bash
python -m pytest
```

---

## 🔒 Verification & Compliance

This project has been thoroughly customized to support:
1. ** लाइव API Integration**: Fully maps the Trvios endpoints, parsing durations (e.g. `"5 Days / 4 Nights"`), discount prices, and custom lists.
2. ** Detailed Metadata Store**: Stores the itinerary timelines directly in ChromaDB.
3. ** SSE Event-driven Streaming**: Sends custom structure events (`sources`, `token` segments, and `done` finalization) down the stream.

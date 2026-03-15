# NoctIS - OSINT Red Team Toolbox

Professional OSINT search interface powered by ripgrep with real-time results and progress tracking.

## Features

- **Real-time search** with ripgrep integration
- **Regex templates** for common OSINT patterns (names, emails, phones, IPs)
- **Progress tracking** with file count, speed, and ETA
- **Stats dashboard** showing dataset metrics
- **Professional dark UI** designed for red team operations
- **WebSocket streaming** for live results
- **Configurable search paths** and parameters

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: Vue 3 + Vite + TypeScript + Tailwind CSS
- **WebSockets**: Real-time bidirectional communication
- **Tests**: pytest (backend) + vitest (frontend)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- ripgrep (`rg`)

### Installation

```bash
# Install backend dependencies
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend
npm install
```

### Run Development Servers

```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
python -m pytest  # Run tests first
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Access the application at `http://localhost:5173`

### Run with Docker

```bash
docker-compose up --build
```

## Project Structure

```
NoctIS/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app
│   │   ├── models.py         # Pydantic models
│   │   ├── config.py         # Configuration
│   │   ├── websocket.py      # WebSocket handlers
│   │   └── services/
│   │       ├── ripgrep.py    # Ripgrep integration
│   │       └── stats.py      # Stats calculation
│   ├── tests/
│   │   └── test_*.py         # Unit tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # Vue components
│   │   ├── views/            # Pages
│   │   ├── stores/           # Pinia stores
│   │   ├── router/           # Vue Router
│   │   └── types/            # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
└── README.md
```

## Usage

### Search Page

1. Select a regex template or enter custom regex
2. Fill in the search parameters (e.g., first name, last name)
3. Click "Search" to start
4. View real-time results and progress

### Settings Page

Configure:
- Search path (where to run ripgrep)
- Thread count (1-16)
- Max file size
- File types to include/exclude

### Regex Templates

- **Name Search**: `(first.*last|last.*first)` - Find name in any order
- **Email**: Standard email pattern matching
- **Phone (FR)**: French phone number formats
- **IP Address**: IPv4 address matching
- **Custom**: Write your own regex

## Testing

```bash
# Backend tests
cd backend
pytest -v --cov=app

# Frontend tests
cd frontend
npm run test
```

## License

MIT

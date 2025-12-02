# Quickstart: Novus Project Database v1 Core

**Branch**: `001-npd-v1-core` | **Date**: 2025-12-01

This guide provides setup instructions for local development of NPD v1.

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Docker & Docker Compose | 24.0+ | Container orchestration |
| Python | 3.11+ | Backend runtime |
| Node.js | 20 LTS | Frontend build tools |
| pnpm | 8.0+ | Package manager (recommended) |
| Git | 2.40+ | Version control |

### Optional (for development)

| Software | Version | Purpose |
|----------|---------|---------|
| VS Code | Latest | IDE with extensions |
| DBeaver | Latest | Database GUI |
| Ollama | Latest | Local LLM (can run in Docker) |

---

## Quick Start (Docker Compose)

The fastest way to run the full stack locally:

```bash
# Clone the repository
git clone <repo-url>
cd novus-database

# Copy environment template
cp .env.example .env

# Edit .env with your Azure AD credentials (see Azure AD Setup below)

# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Access the application
# Frontend: http://localhost:6700
# Backend API: http://localhost:6701
# API Docs: http://localhost:6701/docs
```

### Services Started

| Service | Port | Description |
|---------|------|-------------|
| `frontend` | 6700 | Vite React development server |
| `backend` | 6701 | FastAPI application |
| `db` | 6702 | PostgreSQL with pgvector |
| `ollama` | 6703 | Local embedding/LLM service |

---

## Manual Setup (Development)

For active development with hot-reload and debugging.

### 1. Database Setup

```bash
# Start only PostgreSQL
docker compose up -d db

# Or use an existing PostgreSQL instance (15+)
# Ensure pgvector extension is available:
# CREATE EXTENSION vector;
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing

# Copy environment config
cp .env.example .env
# Edit .env with database URL and Azure AD credentials

# Run database migrations
alembic upgrade head

# Seed initial data (structured tags)
python -m app.scripts.seed_tags

# Start development server
uvicorn app.main:app --reload --port 6701
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Copy environment config
cp .env.example .env.local
# Edit with API URL (default: http://localhost:6701)

# Start development server
pnpm dev
```

### 4. Ollama Setup (for RAG features)

```bash
# Option A: Docker (recommended)
docker compose up -d ollama

# Option B: Native installation
# Download from https://ollama.com
ollama serve

# Pull required models
ollama pull nomic-embed-text    # Embeddings (~274 MB)
ollama pull llama3.2            # Summarization (~4 GB, optional)
```

---

## Environment Variables

### Backend (.env)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://npd:npd@localhost:6702/npd

# Azure AD Authentication
AZURE_AD_TENANT_ID=your-tenant-id
AZURE_AD_CLIENT_ID=your-client-id
AZURE_AD_CLIENT_SECRET=your-client-secret
AZURE_AD_REDIRECT_URI=http://localhost:6701/api/v1/auth/callback

# Application
SECRET_KEY=your-random-secret-key-min-32-chars
ENVIRONMENT=development
DEBUG=true

# Ollama
OLLAMA_BASE_URL=http://localhost:6703

# File Storage
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=50

# CORS (development only)
CORS_ORIGINS=["http://localhost:6700"]
```

### Frontend (.env.local)

```bash
VITE_API_URL=http://localhost:6701
VITE_AZURE_AD_CLIENT_ID=your-client-id
VITE_AZURE_AD_TENANT_ID=your-tenant-id
```

---

## Azure AD Setup

NPD requires Azure AD (Entra ID) for authentication. Follow these steps:

### 1. Register Application

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. Click "New registration"
3. Name: `Novus Project Database (Dev)` or similar
4. Supported account types: "Single tenant" (your organization only)
5. Redirect URI: `http://localhost:6701/api/v1/auth/callback` (Web)
6. Click "Register"

### 2. Configure Authentication

1. Under "Authentication":
   - Add redirect URI for production if needed
   - Enable "ID tokens" under Implicit grant
   - Set "Supported account types" to single tenant

### 3. Create Client Secret

1. Under "Certificates & secrets" → "Client secrets"
2. Click "New client secret"
3. Add description, set expiration
4. **Copy the secret value immediately** (shown only once)

### 4. Configure App Roles

1. Under "App roles" → "Create app role":
   - Display name: `Admin`
   - Allowed member types: Users/Groups
   - Value: `admin`
   - Description: "NPD administrator"
2. Create another role:
   - Display name: `User`
   - Value: `user`
   - Description: "NPD user"

### 5. Assign Users to Roles

1. Go to "Enterprise applications" → Find your app
2. Under "Users and groups" → "Add user/group"
3. Assign users or groups to Admin/User roles

### 6. Note Required Values

Copy these to your `.env` file:
- **Tenant ID**: Overview → Directory (tenant) ID
- **Client ID**: Overview → Application (client) ID
- **Client Secret**: Created in step 3

---

## Database Migrations

```bash
cd backend

# Create a new migration after model changes
alembic revision --autogenerate -m "description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

---

## Running Tests

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_projects.py

# Run with verbose output
pytest -v
```

### Frontend Tests

```bash
cd frontend

# Run unit tests
pnpm test

# Run with coverage
pnpm test:coverage

# Run E2E tests (requires backend running)
pnpm test:e2e

# Open Playwright UI
pnpm test:e2e:ui
```

---

## Code Quality

### Backend

```bash
cd backend

# Format code
black app tests
isort app tests

# Lint
ruff check app tests

# Type checking
mypy app
```

### Frontend

```bash
cd frontend

# Format code
pnpm format

# Lint
pnpm lint

# Type checking
pnpm type-check
```

---

## Common Tasks

### Reset Database

```bash
# Drop and recreate (development only!)
docker compose down -v
docker compose up -d db
cd backend && alembic upgrade head
python -m app.scripts.seed_tags
```

### View API Documentation

- Swagger UI: http://localhost:6701/docs
- ReDoc: http://localhost:6701/redoc
- OpenAPI JSON: http://localhost:6701/openapi.json

### Test Document Upload

```bash
# Upload a test PDF
curl -X POST http://localhost:6701/api/v1/projects/{project_id}/documents \
  -H "Cookie: session=your-session-cookie" \
  -F "files=@test-document.pdf"
```

### Trigger Document Processing

```bash
# Force re-index all documents (admin)
curl -X POST http://localhost:6701/api/v1/admin/reindex \
  -H "Cookie: session=your-session-cookie"
```

---

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker compose ps db

# Check logs
docker compose logs db

# Verify connection
psql postgresql://npd:npd@localhost:6702/npd -c "SELECT 1;"

# Check pgvector extension
psql postgresql://npd:npd@localhost:6702/npd -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

### Azure AD Login Fails

1. Verify redirect URI matches exactly (including trailing slash)
2. Check client secret hasn't expired
3. Ensure user is assigned to an app role
4. Check browser console for CORS errors

### Ollama Not Responding

```bash
# Check Ollama is running
curl http://localhost:6703/api/tags

# Pull model if missing
ollama pull nomic-embed-text

# Check Ollama logs
docker compose logs ollama
```

### Frontend Can't Connect to API

1. Check CORS_ORIGINS in backend .env includes frontend URL
2. Verify VITE_API_URL in frontend .env.local
3. Check browser network tab for actual errors

---

## IDE Setup (VS Code)

### Recommended Extensions

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "charliermarsh.ruff",
    "bradlc.vscode-tailwindcss",
    "esbenp.prettier-vscode",
    "dbaeumer.vscode-eslint"
  ]
}
```

### Workspace Settings

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/.venv/bin/python",
  "python.formatting.provider": "black",
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

---

## Next Steps

After setup, you can:

1. **Explore the API**: Open http://localhost:6701/docs
2. **Create test data**: Use the API to create organizations, contacts, and projects
3. **Upload documents**: Test document processing and search
4. **Review the spec**: See `specs/001-npd-v1-core/spec.md` for requirements
5. **Check tasks**: Run `/speckit.tasks` to generate implementation tasks

# 🗺️ CodeMap — AI-Based Codebase Analyzer & Documentation Generator

An AI-powered tool that analyzes entire codebases and automatically generates comprehensive documentation, architecture overviews, workflow explanations, use case diagrams
(Mermaid), and user manuals.

**Supports 60+ programming languages** — from modern languages (Python, TypeScript, Rust, Go) to legacy languages (Fortran, COBOL, Pascal) and niche languages (Lua, Nim, Zig, Julia).

---

## ✨ Features

- 📦 **Upload ZIP files** or provide **Git repository URLs**
- 🤖 **AI-powered analysis** using OpenAI (GPT-4o-mini by default)
- 📄 **Project Documentation** — comprehensive overview of the codebase
- 🏗️ **Architecture Overview** — patterns, components, data flow
- 🔄 **Workflow Explanation** — step-by-step system flows
- 📊 **Use Case Diagrams** — auto-generated Mermaid diagrams
- 📖 **User Manual** — feature-wise navigation guide
- ⚡ **Background Processing** — Celery + Redis for async analysis
- 📡 **REST API** — JSON endpoints for programmatic access
- 🎨 **Premium Dark UI** — modern, responsive web interface

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Django 4.2+ |
| Task Queue | Celery + Redis |
| AI Engine | OpenAI API (GPT-4o-mini) |
| Database | SQLite (demo) / PostgreSQL |
| Frontend | Django Templates + Mermaid.js |
| Styling | Custom CSS (dark theme) |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Redis** (for Celery task queue)
- **Git** (for cloning repositories)
- **OpenAI API key**

### 1. Clone & Setup

```bash
# Clone the repository
git clone <repo-url> CodeMap
cd CodeMap

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and set your OpenAI API key:
# OPENAI_API_KEY=sk-your-key-here
```

### 3. Initialize Database

```bash
python manage.py migrate
python manage.py createsuperuser  # Optional: for admin panel
```

### 4. Start Redis

```bash
# Using Docker (recommended):
docker run -d -p 6379:6379 redis

# Or install Redis natively:
# Windows: Use Memurai (https://www.memurai.com/) or WSL
# macOS: brew install redis && redis-server
# Linux: sudo apt install redis-server && sudo service redis start
```

### 5. Start Celery Worker

Open a **separate terminal** (with venv activated):

```bash
celery -A codemap worker -l info --pool=solo
```

> **Note:** On Windows, use `--pool=solo` or `--pool=threads`.

### 6. Start Django Server

```bash
python manage.py runserver
```

### 7. Open the App

Navigate to **http://localhost:8000/** in your browser.

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload/` | POST | Upload a project (ZIP or Git URL) |
| `/api/projects/` | GET | List all analyzed projects |
| `/api/projects/<id>/status/` | GET | Check analysis status |
| `/api/projects/<id>/results/` | GET | Fetch analysis results |

### Example: Upload via Git URL

```bash
curl -X POST http://localhost:8000/api/upload/ \
  -H "Content-Type: application/json" \
  -d '{"git_url": "https://github.com/user/repo.git", "project_name": "My Project"}'
```

### Example: Upload via ZIP

```bash
curl -X POST http://localhost:8000/api/upload/ \
  -F "zip_file=@my-project.zip" \
  -F "project_name=My Project"
```

---

## 📁 Project Structure

```
CodeMap/
├── manage.py                   # Django management script
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── codemap/                    # Django project configuration
│   ├── __init__.py             # Celery app import
│   ├── settings.py             # All settings (DB, Celery, OpenAI, logging)
│   ├── urls.py                 # Root URL config
│   ├── celery.py               # Celery app setup
│   ├── wsgi.py                 # WSGI entry point
│   └── asgi.py                 # ASGI entry point
├── analyzer/                   # Main application
│   ├── models.py               # Data models
│   ├── views.py                # Template + API views
│   ├── urls.py                 # App URL routing
│   ├── forms.py                # Upload form
│   ├── tasks.py                # Celery background tasks
│   ├── admin.py                # Django admin config
│   ├── services/
│   │   ├── ai_service.py       # OpenAI integration
│   │   ├── file_processor.py   # File extraction & traversal
│   │   └── prompt_templates.py # LLM prompt templates
│   └── templates/analyzer/     # HTML templates
│       ├── base.html
│       ├── upload.html
│       ├── status.html
│       ├── results.html
│       └── project_list.html
├── static/css/style.css        # Premium dark theme CSS
├── media/                      # Uploaded projects (gitignored)
└── logs/                       # Application logs (gitignored)
```

---

## ⚙️ Configuration

All configuration is done via environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (insecure default) | Django secret key |
| `DEBUG` | `True` | Debug mode |
| `OPENAI_API_KEY` | (required) | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `OPENAI_MAX_TOKENS` | `4096` | Max response tokens |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `DATABASE_URL` | SQLite | PostgreSQL URL (optional) |
| `MAX_FILE_SIZE_MB` | `500` | Max upload size |
| `MAX_SINGLE_FILE_SIZE_KB` | `512` | Max individual file size for analysis |

---

## 📝 License

MIT License — feel free to use and modify.

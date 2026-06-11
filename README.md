# Student-Well-Being-AI 🚀

📦 GitHub: https://github.com/LieutenantHazzy/Student-Well-Being-AI

An AI-powered planning assistant that helps students organize project work. Describe your project in natural language, and the AI breaks it into structured tasks across 5 phases, schedules them into your calendar, and presents a visual timetable.

Built as a school project for **Data Science Tools and Techniques** (HAN University of Applied Sciences, minor DDDM), following the **CRISP-DM** methodology.

## Features

- **AI Chat Planning** — describe a project in plain language; the AI extracts title, deadline, and tasks
- **5-Phase Breakdown** — tasks are categorized into concept, planning, execution, controlling, and closing
- **Auto-Scheduling** — fits tasks into available calendar slots (Mon-Fri 9-17) around your fixed appointments
- **Diff & Approve** — review proposed changes with a Git-style diff before saving
- **Visual Timetable** — week-by-week color-coded schedule view
- **Appointment Handling** — add fixed events like meetings or dentist appointments via chat

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 8, Tailwind CSS 4 |
| Backend | FastAPI, Uvicorn, SSE-Starlette |
| AI | Ollama (llama3.1) |
| Infrastructure | Docker, Docker Compose |

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Ollama](https://ollama.com/) with llama3.1 pulled: `ollama pull llama3.1`

### Run with Docker

```bash
docker-compose up
```

Open [http://localhost:5173](http://localhost:5173).

### Run manually

**Backend:**
```bash
pip install -r requirements.txt
uvicorn APP.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```bash
cd agenda
npm install
npm run dev
```

## Project Structure

```
Student-Well-Being-AI/
├── agenda/              # React frontend
├── APP/                 # FastAPI backend
│   ├── api/             # API endpoints + chat agent
│   ├── main.py          # CLI planner agent
│   └── scheduler.py     # Scheduling engine
├── JSON/                # Data storage (projects, schedule, tasks)
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── requirements.txt
```

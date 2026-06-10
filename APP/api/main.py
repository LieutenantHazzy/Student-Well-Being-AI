import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from sse_starlette.sse import EventSourceResponse

from APP.api.chat_agent import ConversationAgent

BASE_DIR = Path(__file__).resolve().parent.parent.parent
JSON_DIR = BASE_DIR / 'JSON'
PROJECTS_FILE = JSON_DIR / 'projects.json'
SCHEDULE_FILE = JSON_DIR / 'schedule.json'
SCHEDULED_OUTPUT_FILE = JSON_DIR / 'scheduled_tasks.json'
UNSCHEDULED_FILE = JSON_DIR / 'unscheduled_tasks.json'

agent: ConversationAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = ConversationAgent()
    yield


app = FastAPI(title="Student Well-being AI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str | None = None


class ConfirmRequest(BaseModel):
    approved: bool


@app.get("/api/health")
async def health():
    return {"status": "ok", "agent": agent is not None}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    conv_id = req.conversation_id or uuid.uuid4().hex[:12]

    def event_generator():
        for event in agent.chat_stream(conv_id, req.message):
            yield {
                "event": event["type"],
                "data": json.dumps(event["content"]) if isinstance(event["content"], (dict, list)) else event["content"]
            }

    return EventSourceResponse(event_generator())


@app.post("/api/confirm/{conv_id}")
async def confirm(conv_id: str, req: ConfirmRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    result = agent.confirm_proposal(conv_id, req.approved)
    return result


@app.delete("/api/conversation/{conv_id}")
async def clear_conversation(conv_id: str):
    if agent is not None:
        agent.clear_history(conv_id)
    return {"status": "cleared"}


@app.get("/api/conversation/{conv_id}")
async def get_conversation(conv_id: str):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    history = agent.get_history(conv_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    safe = [m for m in history if m['role'] != 'system']
    return {"messages": safe}


@app.post("/api/schedule/run")
async def run_schedule():
    from scheduler import schedule_tasks_rule_based
    result = schedule_tasks_rule_based()
    return result


@app.get("/api/schedule/data")
async def get_schedule_data():
    if SCHEDULED_OUTPUT_FILE.exists():
        try:
            with open(SCHEDULED_OUTPUT_FILE, 'r') as f:
                data = json.load(f)
            return {"data": data}
        except json.JSONDecodeError:
            return {"data": []}
    return {"data": []}


@app.get("/api/schedule/unscheduled")
async def get_unscheduled():
    if UNSCHEDULED_FILE.exists():
        try:
            with open(UNSCHEDULED_FILE, 'r') as f:
                data = json.load(f)
            return {"data": data}
        except json.JSONDecodeError:
            return {"data": []}
    return {"data": []}


@app.get("/api/projects")
async def get_projects():
    if PROJECTS_FILE.exists():
        try:
            with open(PROJECTS_FILE, 'r') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError:
            return {}
    return {}


class BlockRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    start_time: str = Field(..., pattern=r'^\d{2}:\d{2}$')
    end_time: str = Field(..., pattern=r'^\d{2}:\d{2}$')

    @field_validator('date')
    @classmethod
    def validate_date(cls, v):
        datetime.strptime(v, '%Y-%m-%d')
        return v

    @field_validator('start_time', 'end_time')
    @classmethod
    def validate_time(cls, v):
        datetime.strptime(v, '%H:%M')
        return v

    @model_validator(mode='after')
    def validate_time_range(self):
        start = datetime.strptime(self.start_time, '%H:%M')
        end = datetime.strptime(self.end_time, '%H:%M')
        if end <= start:
            raise ValueError('end_time must be after start_time')
        return self


@app.post("/api/agenda/block")
async def add_block(req: BlockRequest):
    data = {}
    if SCHEDULE_FILE.exists():
        try:
            with open(SCHEDULE_FILE, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    if "blocked_slots" not in data:
        data["blocked_slots"] = []
    data["blocked_slots"].append({
        "title": req.title,
        "date": req.date,
        "start_time": req.start_time,
        "end_time": req.end_time
    })
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    return {"status": "added"}


@app.get("/api/agenda")
async def get_agenda():
    if SCHEDULE_FILE.exists():
        try:
            with open(SCHEDULE_FILE, 'r') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError:
            return {}
    return {}

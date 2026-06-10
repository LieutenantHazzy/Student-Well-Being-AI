import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ollama import chat as ollama_chat

from scheduler import schedule_tasks_rule_based

BASE_DIR = Path(__file__).resolve().parent.parent.parent
JSON_DIR = BASE_DIR / 'JSON'
PROJECTS_FILE = JSON_DIR / 'projects.json'
SCHEDULE_FILE = JSON_DIR / 'schedule.json'
SCHEDULED_OUTPUT_FILE = JSON_DIR / 'scheduled_tasks.json'

SYSTEM_PROMPT = """
You are the Smart AI Planner. Your job is to extract project information from a user and break it down into concrete tasks.
You must categorize tasks into exactly 5 phases: concept, planning, execution, controlling, and closing.

Business Rules for Tasks:
1. Every single task must take a minimum of 0.5 hours. No task can be smaller than 0.5 hours.
2. Tasks can optionally have their own deadline (formatted as YYYY-MM-DD). If the user says a task must be done by a specific date, include a "deadline" field for that task.

The system supports MULTIPLE projects. When the user talks about a new project, create a new project object.
When they refer to an existing project (e.g., "update my AI project"), output the updated project with the SAME title so the system can match it.

Your primary goal is to gather all necessary data before finalizing the layout.
Necessary data includes:
1. A clear project title.
2. A valid project deadline (formatted as YYYY-MM-DD).
3. At least one task estimated in hours for relevant project phases.

APPOINTMENT HANDLING:
If the user asks to add a calendar event (e.g. "doctor at 3pm on Friday", "meeting", "dentist", "appointment"),
you MUST immediately output a JSON block with this schema (wrapped in ```json):

```json
{
  "type": "appointment",
  "title": "Brief event name",
  "date": "YYYY-MM-DD",
  "start_time": "HH:MM",
  "end_time": "HH:MM"
}
```

This is NOT a project — do NOT ask for approval. Save it immediately.
Always include the date. If the user says "next Monday" or "this Friday", calculate the correct date.

CRITICAL INSTRUCTIONS FOR MODE SELECTION:
- If any necessary data is missing, vague, or if you need validation from the user, you must output a conversational message asking the user clarifying questions. Do NOT output a JSON block yet.
- Only when you have ALL necessary information and the user explicitly gives permission, says "approve", "looks good", "lgtm", or asks you to save/update the file, you MUST switch modes and output a JSON object inside a Markdown code block matching this schema exactly:

```json
{
  "project_title": "Name of the project",
  "deadline": "YYYY-MM-DD",
  "phases": {
      "concept": [{"title": "task name", "hours_required": 2.0}],
    "planning": [{"title": "task with its own deadline", "hours_required": 1.0, "deadline": "2026-06-10"}],
    "execution": [],
    "controlling": [],
    "closing": []
  }
}
```

The JSON must be inside a ```json code block. Do not output raw JSON outside a code block.
"""


class ConversationAgent:
    def __init__(self):
        self.conversations = {}

    def get_or_create_history(self, conv_id: str) -> list:
        if conv_id not in self.conversations:
            history = [
                {'role': 'system', 'content': SYSTEM_PROMPT}
            ]
            current = self._load_current_memory()
            projects = current.get("projects", [])
            if projects:
                summary = [
                    {"project_title": p["project_title"], "deadline": p.get("deadline")}
                    for p in projects
                ]
                history.append({
                    'role': 'system',
                    'content': f"The user's existing projects are: {json.dumps(summary)}"
                })
            self.conversations[conv_id] = {"history": history}
        return self.conversations[conv_id]["history"]

    def get_history(self, conv_id: str) -> list | None:
        conv = self.conversations.get(conv_id)
        return conv["history"] if conv else None

    def clear_history(self, conv_id: str):
        self.conversations.pop(conv_id, None)

    def _load_current_memory(self) -> dict:
        if PROJECTS_FILE.exists():
            try:
                with open(PROJECTS_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _extract_json(self, text: str) -> dict | None:
        code_block = re.search(r'```(?:json)?\s*\n?([\s\S]*?)```', text)
        json_str = code_block.group(1).strip() if code_block else None
        if not json_str:
            brace_match = re.search(r'\{.*\}', text, re.DOTALL)
            if brace_match:
                json_str = brace_match.group(0)
        if json_str:
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return None
        return None

    def _save_project(self, data: dict) -> dict:
        current = self._load_current_memory()
        projects = current.get("projects", [])

        title = data.get("project_title", "")
        match = next((i for i, p in enumerate(projects) if p.get("project_title") == title), None)
        if match is not None:
            data["project_id"] = projects[match].get("project_id", uuid.uuid4().hex[:12])
            existing_project = projects[match]
            new_phases = data.get("phases", {})
            merged_phases = existing_project.get("phases", {})
            for phase, tasks in new_phases.items():
                if tasks:
                    incoming_titles = {t["title"] for t in tasks}
                    merged = [t for t in merged_phases.get(phase, []) if t["title"] not in incoming_titles]
                    merged.extend(tasks)
                    merged_phases[phase] = merged
            data["phases"] = merged_phases
            projects[match] = data
        else:
            data["project_id"] = uuid.uuid4().hex[:12]
            projects.append(data)

        JSON_DIR.mkdir(parents=True, exist_ok=True)
        with open(PROJECTS_FILE, 'w') as f:
            json.dump({"projects": projects}, f, indent=2)
        return {"status": "saved", "project": data}

    def _save_appointment(self, data: dict) -> dict:
        schedule = {}
        if SCHEDULE_FILE.exists():
            try:
                with open(SCHEDULE_FILE, 'r') as f:
                    schedule = json.load(f)
            except json.JSONDecodeError:
                schedule = {}
        if "blocked_slots" not in schedule:
            schedule["blocked_slots"] = []
        schedule["blocked_slots"].append({
            "title": data["title"],
            "date": data["date"],
            "start_time": data["start_time"],
            "end_time": data["end_time"]
        })
        JSON_DIR.mkdir(parents=True, exist_ok=True)
        with open(SCHEDULE_FILE, 'w') as f:
            json.dump(schedule, f, indent=2)
        return data

    def _compute_diff(self, old: dict, new: dict) -> list:
        changes = []
        old_title = old.get("project_title", "")
        new_title = new.get("project_title", "")
        if old_title != new_title:
            changes.append(f"Title: {old_title or '(none)'} -> {new_title}")
        old_deadline = old.get("deadline", "")
        new_deadline = new.get("deadline", "")
        if old_deadline != new_deadline:
            changes.append(f"Deadline: {old_deadline or '(none)'} -> {new_deadline}")
        if not old:
            for phase, tasks in new.get("phases", {}).items():
                for t in tasks:
                    changes.append(f"+ [{phase}] {t['title']} ({t['hours_required']}h)")
            return changes
        merged = {k: list(v) for k, v in old.get("phases", {}).items()}
        for phase, tasks in new.get("phases", {}).items():
            if tasks:
                incoming_titles = {t["title"] for t in tasks}
                merged[phase] = [t for t in merged.get(phase, []) if t["title"] not in incoming_titles] + list(tasks)
        old_set = set()
        for phase, tasks in old.get("phases", {}).items():
            for t in tasks:
                old_set.add((phase, t.get("title", ""), t.get("hours_required", 0)))
        merged_set = set()
        for phase, tasks in merged.items():
            for t in tasks:
                merged_set.add((phase, t.get("title", ""), t.get("hours_required", 0)))
        for phase, title, hours in sorted(merged_set - old_set):
            changes.append(f"+ [{phase}] {title} ({hours}h)")
        for phase, title, hours in sorted(old_set - merged_set):
            changes.append(f"- [{phase}] {title} ({hours}h)")
        return changes

    def chat_stream(self, conv_id: str, user_message: str):
        history = self.get_or_create_history(conv_id)
        history.append({'role': 'user', 'content': user_message})

        yield {"type": "status", "content": "Thinking..."}

        response = ollama_chat(model='llama3.1', messages=history)
        ai_reply = response.message.content

        extracted = self._extract_json(ai_reply)
        if extracted:
            history.append({'role': 'assistant', 'content': ai_reply})

            if extracted.get("type") == "appointment":
                self._save_appointment(extracted)
                run = schedule_tasks_rule_based()
                msg = f"📅 Added: {extracted['title']} on {extracted['date']} at {extracted['start_time']}-{extracted['end_time']}"
                unscheduled = run.get("unscheduled_tasks", [])
                if unscheduled:
                    names = ", ".join(t["title"] for t in unscheduled[:3])
                    extra = f" ({len(unscheduled) - 3} more)" if len(unscheduled) > 3 else ""
                    msg += f" ⚠️ Could not place: {names}{extra}"
                yield {"type": "token", "content": msg}
            else:
                current = self._load_current_memory()
                projects = current.get("projects", [])
                title = extracted.get("project_title", "")
                existing = next((p for p in projects if p.get("project_title") == title), {})
                diff = self._compute_diff(existing, extracted)
                is_new = not existing

                yield {"type": "project_proposal", "content": json.dumps({
                    "summary": f"{'New' if is_new else 'Update'}: {extracted.get('project_title')} (deadline: {extracted.get('deadline')})",
                    "diff": diff,
                    "proposed": extracted
                })}

                self.conversations[conv_id]["pending_proposal"] = extracted
        else:
            yield {"type": "token", "content": ai_reply}
            history.append({'role': 'assistant', 'content': ai_reply})

        yield {"type": "done", "content": ""}

    def confirm_proposal(self, conv_id: str, approved: bool) -> dict:
        conv = self.conversations.get(conv_id)
        if not conv or "pending_proposal" not in conv:
            return {"status": "error", "message": "No pending proposal"}
        proposed = conv.pop("pending_proposal")
        if approved:
            result = self._save_project(proposed)
            run = schedule_tasks_rule_based()
            response_data = {
                "status": "approved",
                "project": result,
                "schedule": run
            }
            unscheduled = run.get("unscheduled_tasks", [])
            if unscheduled:
                response_data["warning"] = (f"{len(unscheduled)} task(s) could not be scheduled: "
                                            f"{', '.join(t['title'] for t in unscheduled[:5])}"
                                            f"{'...' if len(unscheduled) > 5 else ''}")
            return response_data
        else:
            return {"status": "rejected", "message": "Changes discarded"}

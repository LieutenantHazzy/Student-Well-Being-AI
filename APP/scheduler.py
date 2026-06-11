import json
import re
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = BASE_DIR / 'JSON'
AGENDA_FILE = JSON_DIR / 'schedule.json'
PROJECTS_FILE = JSON_DIR / 'projects.json'
SCHEDULED_OUTPUT_FILE = JSON_DIR / 'scheduled_tasks.json'
UNSCHEDULED_FILE = JSON_DIR / 'unscheduled_tasks.json'

def load_json(filepath):
    """Safely loads a JSON file, returning an empty dictionary if missing or corrupted."""
    if filepath.exists():
        with open(filepath, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def parse_time(time_str):
    """Converts a string formatted as HH:MM into a datetime time object."""
    return datetime.strptime(time_str, "%H:%M").time()

def determine_week_start(project_data, agenda):
    """Derive the Monday of the scheduling week from the deadline or blocked slots."""
    deadline_str = project_data.get("deadline")
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
            return deadline - timedelta(days=deadline.weekday())
        except ValueError:
            pass

    dates = []
    for slot in agenda.get("blocked_slots", []):
        try:
            dates.append(datetime.strptime(slot["date"], "%Y-%m-%d"))
        except ValueError:
            continue
    if dates:
        min_date = min(dates)
        return min_date - timedelta(days=min_date.weekday())

    today = datetime.now()
    return today - timedelta(days=today.weekday())

def merge_overlapping_blocks(blocks):
    """Merge overlapping blocked time slots for a single day into combined entries."""
    sorted_blocks = sorted(blocks, key=lambda x: (x["start"], x["end"]))
    merged = []
    for block in sorted_blocks:
        if not merged:
            merged.append(dict(block))
        else:
            last = merged[-1]
            if block["start"] < last["end"]:
                last["end"] = max(last["end"], block["end"])
                last["title"] = f"{last['title']}, {block['title']}"
            else:
                merged.append(dict(block))
    return merged

def ai_prioritize_tasks(tasks):
    """Use LLM to reorder tasks optimally based on deadlines, phases, project context, and difficulty."""
    if not tasks:
        return tasks

    from ollama import chat as ollama_chat

    task_summary = []
    for t in tasks:
        summary = {
            "title": t["title"],
            "phase": t["phase"],
            "hours": round(t["hours"], 2),
            "project": t.get("project_title", "Unknown")
        }
        deadline = t.get("deadline") or t.get("project_deadline")
        if deadline:
            summary["deadline"] = deadline
        task_summary.append(summary)

    prompt = f"""You are a smart task prioritizer. Given tasks from multiple projects with their phases, estimated hours, and deadlines, reorder them in the optimal scheduling sequence.

Rules:
1. Tasks with the nearest deadlines must come first.
2. Respect phase order as a secondary guide: concept → planning → execution → controlling → closing
3. Respect project order: try to keep tasks from the same project reasonably grouped to avoid context switching.
4. Consider task difficulty and focus required (inferred from title). Harder/deep-focus tasks should be placed earlier.
5. Return ONLY a JSON array of task objects in the new order, preserving all original fields exactly.

Tasks:
{json.dumps(task_summary, indent=2)}

Return the reordered array inside a ```json code block:"""

    try:
        response = ollama_chat(model='llama3.1', messages=[
            {'role': 'system', 'content': 'You are a task prioritization assistant. Always respond with a JSON code block containing the reordered task array.'},
            {'role': 'user', 'content': prompt}
        ])
        reply = response.message.content

        code_block = re.search(r'```(?:json)?\s*\n?([\s\S]*?)```', reply)
        json_str = code_block.group(1).strip() if code_block else None
        if not json_str:
            brace_match = re.search(r'\[.*\]', reply, re.DOTALL)
            if brace_match:
                json_str = brace_match.group(0)

        if json_str:
            reordered = json.loads(json_str)
            if isinstance(reordered, list) and len(reordered) == len(tasks):
                title_map = {t["title"]: t for t in tasks}
                result = [title_map[t["title"]] for t in reordered if t.get("title") in title_map]
                if len(result) == len(tasks):
                    return result
    except Exception:
        pass

    return tasks


def schedule_tasks_rule_based():
    """Deterministic rule-based scheduling logic to fit project tasks into available calendar gaps."""
    agenda = load_json(AGENDA_FILE)
    project_data = load_json(PROJECTS_FILE)
    
    if not agenda:
        return {"status": "error", "message": "schedule.json not found or empty."}
    if not project_data:
        return {"status": "error", "message": "projects.json not found or empty."}

    projects = project_data.get("projects", [])
    if not projects:
        return {"status": "error", "message": "No projects found in projects.json."}

    working_hours = agenda.get("working_hours")
    if not working_hours:
        return {"status": "error", "message": "schedule.json missing working_hours."}
    work_start_str = working_hours.get("start")
    work_end_str = working_hours.get("end")
    work_days = working_hours.get("work_days")
    if not all([work_start_str, work_end_str, work_days]):
        return {"status": "error", "message": "schedule.json working_hours is incomplete."}

    work_start = parse_time(work_start_str)
    work_end = parse_time(work_end_str)
    work_days_set = set(work_days)

    # Collect tasks from ALL projects, tagging with project identifiers
    tasks_to_schedule = []
    all_deadlines = []
    for proj in projects:
        proj_deadline = proj.get("deadline", "not set")
        all_deadlines.append(proj_deadline)
        for phase_name, phase_tasks in proj.get("phases", {}).items():
            for task in phase_tasks:
                entry = {
                    "title": task["title"],
                    "hours": task["hours_required"],
                    "phase": phase_name,
                    "project_id": proj["project_id"],
                    "project_title": proj["project_title"],
                    "project_deadline": proj_deadline
                }
                if task.get("deadline"):
                    entry["deadline"] = task["deadline"]
                tasks_to_schedule.append(entry)

    # Use earliest project deadline for scheduling window
    valid_deadlines = [d for d in all_deadlines if d != "not set"]
    overall_deadline = min(valid_deadlines) if valid_deadlines else "not set"

    # AI-enhanced: reorder tasks intelligently across all projects
    tasks_to_schedule = ai_prioritize_tasks(tasks_to_schedule)

    start_date = determine_week_start({"deadline": overall_deadline}, agenda)

    # Organize pre-existing blocked calendar entries by their respective dates
    blocked_by_date = {}
    for slot in agenda.get("blocked_slots", []):
        d = slot["date"]
        if d not in blocked_by_date:
            blocked_by_date[d] = []
        blocked_by_date[d].append({
            "start": parse_time(slot["start_time"]),
            "end": parse_time(slot["end_time"]),
            "title": slot["title"]
        })

    for d in blocked_by_date:
        blocked_by_date[d] = merge_overlapping_blocks(blocked_by_date[d])

    final_schedule = []
    unscheduled_tasks = []
    task_index = 0
    max_weeks = 12

    for week_num in range(max_weeks):
        if task_index >= len(tasks_to_schedule):
            break

        week_start = start_date + timedelta(weeks=week_num)
        current_day = week_start
        days_processed = 0
        total_work_days = len(work_days_set)

        while days_processed < total_work_days and task_index < len(tasks_to_schedule):
            date_str = current_day.strftime("%Y-%m-%d")
            day_name = current_day.strftime("%A")

            if day_name in work_days_set:
                days_processed += 1
                current_time = datetime.combine(current_day.date(), work_start)
                day_end_time = datetime.combine(current_day.date(), work_end)

                day_blocks = blocked_by_date.get(date_str, [])

                while current_time < day_end_time and task_index < len(tasks_to_schedule):
                    overlap = False
                    for block in day_blocks:
                        block_start = datetime.combine(current_day.date(), block["start"])
                        block_end = datetime.combine(current_day.date(), block["end"])

                        if current_time >= block_start and current_time < block_end:
                            current_time = block_end
                            overlap = True
                            break

                    if overlap:
                        continue

                    # Check if current task exceeds its deadline
                    task = tasks_to_schedule[task_index]
                    task_deadline = task.get("deadline") or task.get("project_deadline")
                    if task_deadline and task_deadline != "not set" and date_str > task_deadline:
                        unscheduled_tasks.append({
                            "title": task["title"],
                            "project_title": task.get("project_title", ""),
                            "phase": task["phase"],
                            "hours": task["hours"],
                            "reason": "deadline_exceeded"
                        })
                        task_index += 1
                        continue

                    task_duration = timedelta(hours=task["hours"])
                    potential_end = current_time + task_duration

                    next_block_start = day_end_time
                    for block in day_blocks:
                        b_start = datetime.combine(current_day.date(), block["start"])
                        if b_start > current_time:
                            next_block_start = b_start
                            break

                    if potential_end <= next_block_start:
                        final_schedule.append({
                            "title": task["title"],
                            "phase": task["phase"],
                            "project_id": task.get("project_id", ""),
                            "project_title": task.get("project_title", ""),
                            "date": date_str,
                            "start_time": current_time.strftime("%H:%M"),
                            "end_time": potential_end.strftime("%H:%M"),
                            "type": "task"
                        })
                        current_time = potential_end
                        task_index += 1
                    else:
                        if next_block_start < day_end_time and next_block_start > current_time:
                            available = (next_block_start - current_time).total_seconds() / 3600
                            if available >= 0.5:
                                final_schedule.append({
                                    "title": task["title"],
                                    "phase": task["phase"],
                                    "project_id": task.get("project_id", ""),
                                    "project_title": task.get("project_title", ""),
                                    "date": date_str,
                                    "start_time": current_time.strftime("%H:%M"),
                                    "end_time": next_block_start.strftime("%H:%M"),
                                    "type": "task"
                                })
                                task["hours"] = round(task["hours"] - available, 2)
                                current_time = next_block_start
                            else:
                                current_time = next_block_start
                        else:
                            break

            current_day += timedelta(days=1)

    # Append merged fixed appointments to the output
    for date_str, blocks in blocked_by_date.items():
        for block in blocks:
            final_schedule.append({
                "title": block["title"],
                "phase": "fixed_appointment",
                "date": date_str,
                "start_time": block["start"].strftime("%H:%M"),
                "end_time": block["end"].strftime("%H:%M"),
                "type": "block"
            })

    # Flush any remaining tasks as unscheduled (no slot found)
    while task_index < len(tasks_to_schedule):
        task = tasks_to_schedule[task_index]
        unscheduled_tasks.append({
            "title": task["title"],
            "project_title": task.get("project_title", ""),
            "phase": task["phase"],
            "hours": task["hours"],
            "reason": "no_available_slot"
        })
        task_index += 1

    # Ensure the storage directory exists, then export the calendar data payload
    JSON_DIR.mkdir(parents=True, exist_ok=True)
        
    with open(SCHEDULED_OUTPUT_FILE, 'w') as f:
        json.dump(final_schedule, f, indent=2)

    with open(UNSCHEDULED_FILE, 'w') as f:
        json.dump(unscheduled_tasks, f, indent=2)
        
    return {
        "status": "success" if not unscheduled_tasks else "partial",
        "remaining_tasks_count": len(unscheduled_tasks),
        "unscheduled_tasks": unscheduled_tasks,
        "schedule_data": final_schedule,
        "deadline": overall_deadline,
        "week_start": start_date.strftime("%Y-%m-%d")
    }


import json
import os
from datetime import datetime, timedelta
from ollama import chat, ChatResponse

# File path and file name configurations
JSON_DIR = os.path.join(os.path.dirname(__file__), '..', 'JSON')
AGENDA_FILE = os.path.join(JSON_DIR, 'schedule.json')        
PROJECTS_FILE = os.path.join(JSON_DIR, 'projects.json')      
SCHEDULED_OUTPUT_FILE = os.path.join(JSON_DIR, 'scheduled_tasks.json') 

def load_json(filepath):
    """Safely loads a JSON file, returning an empty dictionary if missing or corrupted."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def parse_time(time_str):
    """Converts a string formatted as HH:MM into a datetime time object."""
    return datetime.strptime(time_str, "%H:%M").time()

def schedule_tasks_rule_based():
    """Deterministic rule-based scheduling logic to fit project tasks into available calendar gaps."""
    agenda = load_json(AGENDA_FILE)
    project_data = load_json(PROJECTS_FILE)
    
    if not agenda:
        return {"status": "error", "message": "schedule.json not found or empty."}
    if not project_data:
        return {"status": "error", "message": "projects.json not found or empty."}

    # Gather all outstanding project tasks across the 5 project phases
    tasks_to_schedule = []
    phases = project_data.get("phases", {})
    for phase_name, tasks in phases.items():
        for task in tasks:
            tasks_to_schedule.append({
                "title": task["title"],
                "hours": task["hours_required"],
                "phase": phase_name
            })

    # Scheduling starts on Monday of the designated project execution week
    start_date = datetime(2026, 5, 25)
    working_hours = agenda["working_hours"]
    work_start = parse_time(working_hours["start"])
    work_end = parse_time(working_hours["end"])
    
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

    final_schedule = []
    current_day = start_date

    # Iterate through the 5 consecutive business working days (Mon to Fri)
    for _ in range(5):
        date_str = current_day.strftime("%Y-%m-%d")
        day_name = current_day.strftime("%A") 
        
        if day_name in working_hours["work_days"]:
            current_time = datetime.combine(current_day.date(), work_start)
            day_end_time = datetime.combine(current_day.date(), work_end)
            
            day_blocks = blocked_by_date.get(date_str, [])
            day_blocks.sort(key=lambda x: x["start"])

            while current_time < day_end_time and tasks_to_schedule:
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
                
                # Fetch the next task awaiting assignment
                task = tasks_to_schedule[0]
                task_duration = timedelta(hours=task["hours"])
                potential_end = current_time + task_duration
                
                # Identify the boundary point of the next upcoming appointment constraint
                next_block_start = day_end_time
                for block in day_blocks:
                    b_start = datetime.combine(current_day.date(), block["start"])
                    if b_start > current_time:
                        next_block_start = b_start
                        break
                
                # Validate if the task fits comfortably into the current open time window
                if potential_end <= next_block_start and potential_end <= day_end_time:
                    final_schedule.append({
                        "title": task["title"],
                        "phase": task["phase"],
                        "date": date_str,
                        "start_time": current_time.strftime("%H:%M"),
                        "end_time": potential_end.strftime("%H:%M"),
                        "type": "task"
                    })
                    current_time = potential_end
                    tasks_to_schedule.pop(0) 
                else:
                    if next_block_start != day_end_time:
                        current_time = next_block_start
                    else:
                        break # Remaining day time is entirely utilized
                        
        current_day += timedelta(days=1)

    # Append original fixed appointments so they show up inside the React interface layout
    for slot in agenda.get("blocked_slots", []):
        final_schedule.append({
            "title": slot["title"],
            "phase": "fixed_appointment",
            "date": slot["date"],
            "start_time": slot["start_time"],
            "end_time": slot["end_time"],
            "type": "block"
        })

    # Ensure the storage directory exists, then export the calendar data payload
    if not os.path.exists(JSON_DIR):
        os.makedirs(JSON_DIR)
        
    with open(SCHEDULED_OUTPUT_FILE, 'w') as f:
        json.dump(final_schedule, f, indent=2)
        
    return {
        "status": "success", 
        "remaining_tasks_count": len(tasks_to_schedule),
        "schedule_data": final_schedule  
    }

def run_scheduler_agent():
    print("🤖 [AI Scheduler Agent] Initializing...")
    
    system_prompt = """
    You are the Student Well-being Assistant. Your role is to motivate the student and present their REAL optimized schedule calculated by the system execution engine.
    
    STRICT RUNTIME RULES:
    - NEVER make up fake appointments, classes, or time slots.
    - ALWAYS use the exact data provided in the system message to tell the student which task is scheduled and when.
    - Present the weekly schedule organized clearly by day (Monday through Friday) using plain, friendly language.
    - Remind the student that rest periods and fixed educational activities have been explicitly protected to prevent cognitive fatigue and support well-being.
    - ALWAYS reply and communicate in English.
    """

    messages = [{'role': 'system', 'content': system_prompt}]
    print("Assistant is online. Type a command like: 'Distribute my tasks across my free slots this week'")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
            
        if user_input.lower() in ['exit', 'quit']:
            break
            
        if not user_input:
            continue
            
        messages.append({'role': 'user', 'content': user_input})
        
        # Trigger condition check for executing the calculations
        if any(keyword in user_input.lower() for keyword in ["divide", "distribute", "plan", "schedule", "done", "worked"]):
            print("\n[AI Module] Scanning schedule.json for open slots and allocating project tasks...")
            result = schedule_tasks_rule_based()
            
            if result["status"] == "success":
                # Feed the real structural calculation back to the LLM context path
                formatted_data = json.dumps(result["schedule_data"], indent=2)
                messages.append({
                    'role': 'system', 
                    'content': f"The calculation engine has run SUCCESSFUL. Here is the REAL schedule data you MUST use for your response:\n{formatted_data}\n\nUnscheduled tasks due to constraints: {result['remaining_tasks_count']}. Report this layout neatly and encouragingly to the student."
                })
            else:
                messages.append({
                    'role': 'system',
                    'content': f"Calculation pipeline failure: {result.get('message', 'Unknown system error')}"
                })

        print("\n[AI] Processing response...")
        response: ChatResponse = chat(model='llama3.1', messages=messages)
        ai_reply = response.message.content
        print(f"\nAI: {ai_reply}")
        messages.append({'role': 'assistant', 'content': ai_reply})

if __name__ == "__main__":
    run_scheduler_agent()

    # uv run c:/Users/40jul/Documents/minor_DDDM/Student-Well-Being-AI/APP/main.py
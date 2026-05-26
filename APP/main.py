import json
import os
import re
from ollama import chat, ChatResponse

# Importeer de rekenmodule uit je scheduler script
from scheduler import schedule_tasks_rule_based

# Define strict folder paths based on your architecture requirements
JSON_DIR = os.path.join(os.path.dirname(__file__), '..', 'JSON')
PROJECTS_FILE = os.path.join(JSON_DIR, 'projects.json')

# The comprehensive system prompt mapping out validation gates and structural business rules
SYSTEM_PROMPT = """
You are the Smart AI Planner. Your job is to extract project information from a user and break it down into concrete tasks.
You must categorize tasks into exactly 5 phases: concept, planning, execution, controlling, and closing.

Business Rules for Tasks:
1. Every single task must take a minimum of 0.5 hours. No task can be smaller than 0.5 hours.

Your primary goal is to gather all necessary data before finalizing the layout.
Necessary data includes:
1. A clear project title.
2. A valid deadline (formatted as YYYY-MM-DD).
3. At least one task estimated in hours for relevant project phases.

CRITICAL INSTRUCTIONS FOR MODE SELECTION:
- If any necessary data is missing, vague, or if you need validation from the user, you must output a conversational message asking the user clarifying questions. Do NOT output a JSON block yet.
- Only when you have ALL necessary information and the user explicitly gives permission, says "approve", "looks good", "lgtm", or asks you to save/update the file, you MUST switch modes and output a strict raw JSON object configuration matching this schema exactly:

{
  "project_title": "Name of the project",
  "deadline": "YYYY-MM-DD",
  "phases": {
    "concept": [{"title": "task name", "hours_required": 2.0}],
    "planning": [],
    "execution": [],
    "controlling": [],
    "closing": []
  }
}

Ensure the JSON structure is intact. You are allowed to include a polite confirmation sentence before or after the JSON block, as long as the JSON block itself is properly formatted.
"""

def ensure_json_directory():
    """Validates local file system paths and initializes the JSON folder if missing."""
    if not os.path.exists(JSON_DIR):
        os.makedirs(JSON_DIR)

def load_local_memory() -> dict:
    """Loads current state from local file memory to establish state change tracking."""
    ensure_json_directory()
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def show_merge_request(old_data: dict, new_data: dict) -> bool:
    """Prints a clean, human-readable Git-style comparison between old and new project states."""
    print("\n" + "=" * 25 + " 🚀 MERGE REQUEST DIALOGUE " + "=" * 25)
    
    # Extract project names safely from potential wrapping variants
    def get_project_title(data):
        if "project_title" in data:
            return data["project_title"]
        if "projects" in data and len(data["projects"]) > 0:
            return data["projects"][-1].get("title", "Unknown Project")
        return "New Project Setup"

    def get_deadline(data):
        if "deadline" in data:
            return data["deadline"]
        if "projects" in data and len(data["projects"]) > 0:
            return data["projects"][-1].get("deadline", "None")
        return "None"

    old_title = get_project_title(old_data)
    new_title = get_project_title(new_data)
    old_deadline = get_deadline(old_data)
    new_deadline = get_deadline(new_data)

    # 1. Show high-level metadata changes
    print("\n📋 PROJECT METADATA:")
    if old_title != new_title:
        print(f"  Title:    🔴 {old_title} \n            ➡️ 🟢 {new_title}")
    else:
        print(f"  Title:    ✨ {new_title}")

    if old_deadline != new_deadline:
        print(f"  Deadline: 🔴 {old_deadline} ➡️ 🟢 {new_deadline}")
    else:
        print(f"  Deadline: 📅 {new_deadline}")

    # Helper to flatten tasks by phase for easy side-by-side comparison
    def get_tasks_dict(data):
        phases_data = {}
        if "phases" in data:
            phases_data = data["phases"]
        elif "projects" in data and len(data["projects"]) > 0:
            phases_data = data["projects"][-1].get("phases", {})
        
        flattened = {}
        for phase, tasks in phases_data.items():
            if isinstance(tasks, list):
                for t in tasks:
                    if isinstance(t, dict) and "title" in t:
                        # Normalize hours field variants
                        flattened[t["title"]] = {
                            "phase": phase,
                            "hours": t.get("hours_required", t.get("hours", 0.5))
                        }
        return flattened

    old_tasks = get_tasks_dict(old_data)
    new_tasks = get_tasks_dict(new_data)

    print("\n⚡ PHASE & TASK ADJUSTMENTS:")
    all_task_titles = set(old_tasks.keys()).union(set(new_tasks.keys()))
    has_changes = False

    for title in sorted(all_task_titles):
        # Case A: Task was completely removed
        if title in old_tasks and title not in new_tasks:
            info = old_tasks[title]
            print(f"  🚨 [REMOVED]  ({info['phase'].upper()}) - {title} ({info['hours']} hrs)")
            has_changes = True
            
        # Case B: Task is completely new
        elif title in new_tasks and title not in old_tasks:
            info = new_tasks[title]
            print(f"  ➕ [ADDED]    ({info['phase'].upper()}) - {title} ({info['hours']} hrs)")
            has_changes = True
            
        # Case C: Task exists in both, check if hours were modified
        elif title in old_tasks and title in new_tasks:
            old_hrs = old_tasks[title]["hours"]
            new_hrs = new_tasks[title]["hours"]
            phase = new_tasks[title]["phase"]
            if old_hrs != new_hrs:
                print(f"  🔄 [MODIFIED] ({phase.upper()}) - {title}: 🔴 {old_hrs} hrs ➡️ 🟢 {new_hrs} hrs")
                has_changes = True

    if not has_changes and old_title == new_title and old_deadline == new_deadline:
        print("  No changes detected. Your schedule is perfectly synchronized.")

    print("\n" + "=" * 79)
    user_choice = input("Do you approve merging these changes to your schedule memory? (y/n): ").strip().lower()
    return user_choice == 'y'

def run_planner_agent():
    """Runs the conversational loop, tracking session updates and handling validations."""
    current_memory = load_local_memory()
    
    # Initialize short-term conversation logs with global system guidelines
    conversation_history = [
        {'role': 'system', 'content': SYSTEM_PROMPT}
    ]
    
    # Inject current local file state as an operational system baseline
    if current_memory:
        conversation_history.append({
            'role': 'system', 
            'content': f"The current stored project memory state on the user's computer is: {json.dumps(current_memory)}"
        })

    print("🤖 [Smart AI Planner Initialization] State active. Say hello or type your project details!")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat session.")
            break
            
        if user_input.lower() in ['exit', 'quit']:
            print("Exiting chat session.")
            break
        
        if not user_input:
            continue
            
        # Append latest user response to message tracking array
        conversation_history.append({'role': 'user', 'content': user_input})
        
        print("\n[AI] Processing state...")
        
        # Request dynamic conversational or structural response from local Ollama runtime
        response: ChatResponse = chat(
            model='llama3.1',
            messages=conversation_history
        )
        
        ai_reply = response.message.content
        
        # Robust Regex Engine: Safely find and isolate JSON blocks even if hidden inside conversation paragraphs
        json_match = re.search(r'(\{.*\}).*', ai_reply, re.DOTALL)
        
        if json_match:
            try:
                json_string = json_match.group(1)
                proposed_memory = json.loads(json_string)
                
                # Execution of clean human-oriented PR interface diff comparison
                is_approved = show_merge_request(current_memory, proposed_memory)
                
                if is_approved:
                    with open(PROJECTS_FILE, 'w') as f:
                        json.dump(proposed_memory, f, indent=2)
                    print("✅ Data locked and written successfully to 'JSON/projects.json'.")
                    
                    # 🎯 HIER GEBEURT DE AUTOMATISCHE MAGIE:
                    print("🚀 Smart AI Planner triggert automatisch de Scheduler Agent...")
                    schedule_result = schedule_tasks_rule_based()
                    
                    if schedule_result["status"] == "success":
                        print("📅 Systeem-update: Vrije gaten zijn berekend en 'scheduled_tasks.json' is up-to-date!")
                    else:
                        print(f"⚠️ Scheduler waarschuwing: {schedule_result.get('message')}")
                        
                    current_memory = proposed_memory
                else:
                    print("❌ Changes discarded. Session remaining open for further instruction.")
                
                # Sync conversation history block to track operational state progression
                conversation_history.append({'role': 'assistant', 'content': ai_reply})
                
            except json.JSONDecodeError:
                # If regex caught mismatched braces that don't match JSON syntax, fallback to chat lines
                print(f"\nAI: {ai_reply}")
                conversation_history.append({'role': 'assistant', 'content': ai_reply})
        else:
            # Standard output configuration: missing variables found, asking questions
            print(f"\nAI: {ai_reply}")
            conversation_history.append({'role': 'assistant', 'content': ai_reply})

if __name__ == "__main__":
    run_planner_agent()

    # uv run c:/Users/40jul/Documents/minor_DDDM/Student-Well-Being-AI/APP/main.py
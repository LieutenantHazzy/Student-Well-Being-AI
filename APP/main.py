import json
import os
from ollama import chat, ChatResponse
from deepdiff import DeepDiff

# Path definitions
JSON_DIR = os.path.join(os.path.dirname(__file__), '..', 'JSON')
PROJECTS_FILE = os.path.join(JSON_DIR, 'projects.json')

SYSTEM_PROMPT = """
You are the Smart AI Planner. Your job is to extract project information and break it down into concrete tasks.
You must categorize tasks into exactly 5 phases: concept, planning, execution, controlling, and closing.
Rule: Every single task must take at least 0.5 hours.

Your primary goal is to gather all necessary data before finalizing the layout. 
Necessary data includes:
1. A clear project title.
2. A valid deadline (YYYY-MM-DD).
3. At least one task estimated in hours for relevant project phases.

CRITICAL INSTRUCTIONS FOR MODE SELECTION:
If any necessary data is missing, vague, or if you need validation from the user, you must output a conversational message asking the user clarifying questions. Do NOT output a JSON block yet.

Only when you have ALL necessary information and the user has confirmed details, you must switch modes and output a strict raw JSON object matching this schema exactly (with no conversational text around it):
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
"""

def ensure_json_directory():
    if not os.path.exists(JSON_DIR):
        os.makedirs(JSON_DIR)

def load_local_memory() -> dict:
    ensure_json_directory()
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def run_planner_agent():
    current_memory = load_local_memory()
    
    # Initialize the chat log array to maintain short-term memory over multiple questions
    conversation_history = [
        {'role': 'system', 'content': SYSTEM_PROMPT}
    ]
    
    # If we already have a project saved, let the AI know what the current state is
    if current_memory:
        conversation_history.append({
            'role': 'system', 
            'content': f"The current stored project memory state is: {json.dumps(current_memory)}"
        })

    print("🤖 [Smart AI Planner Initialization] State active. Say hello or type a project name!")
    
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ['exit', 'quit']:
            print("Exiting chat session.")
            break
            
        # Append what the user just typed to the chat matrix
        conversation_history.append({'role': 'user', 'content': user_input})
        
        print("\n[AI] Processing state...")
        
        # NOTE: We removed format='json' here so the model is allowed to reply in natural language!
        response: ChatResponse = chat(
            model='llama3.1',
            messages=conversation_history
        )
        
        ai_reply = response.message.content
        
        # Determine if the AI decided it's ready to output the completed JSON
        if ai_reply.strip().startswith('{') and ai_reply.strip().endswith('}'):
            try:
                proposed_memory = json.loads(ai_reply)
                
                # Show Git-style Pull Request comparison
                print("\n" + "="*20 + " MERGE REQUEST DIALOGUE " + "="*20)
                diff = DeepDiff(current_memory, proposed_memory, ignore_order=True)
                
                if not diff:
                    print("No adjustments found. Local state perfectly syncs.")
                else:
                    print(json.dumps(json.loads(diff.to_json()), indent=2))
                print("="*64)
                
                approve = input("Do you approve merging this data structure to local storage? (y/n): ").strip().lower()
                if approve == 'y':
                    with open(PROJECTS_FILE, 'w') as f:
                        json.dump(proposed_memory, f, indent=2)
                    print("✅ Data locked and written successfully to 'JSON/projects.json'.")
                    current_memory = proposed_memory # Sync runtime loop memory state
                else:
                    print("❌ Changes discarded. Session remaining open for further instruction.")
                
                # Keep history updated so it remembers its final proposal state
                conversation_history.append({'role': 'assistant', 'content': ai_reply})
                
            except json.JSONDecodeError:
                print("🚨 Format Error: AI tried to generate a structure but it broke JSON standard compilation rules.")
                print(f"Raw Output: {ai_reply}")
        else:
            # AI asked a conversational tracking question or gave descriptive advice
            print(f"\nAI: {ai_reply}")
            # Save the question into chat memory so it remembers what it asked you!
            conversation_history.append({'role': 'assistant', 'content': ai_reply})

if __name__ == "__main__":
    run_planner_agent()
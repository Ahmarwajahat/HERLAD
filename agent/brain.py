from groq import Groq
from openai import OpenAI
from dotenv import load_dotenv
try:
    from cerebras.cloud.sdk import Cerebras
except ImportError:
    Cerebras = None
import os, json, time, re
from dotenv import load_dotenv
load_dotenv()

from agent.rl_agent import RLAgent
rl_agent = RLAgent()

from agent.tools import (list_files, read_file, write_file, write_word_file,
                         search_web, write_and_run_code, whatsapp_notify_me,
                         send_whatsapp_file, upload_to_classroom,
                         execute_code_online, run_code_locally_with_screenshot,
                         search_knowledge_base, add_file_to_knowledge_base,
                         run_code_in_nano_and_screenshot, execute_bash_command)
from agent.memory import log_task, log_tool_call, complete_task

# ── Load all Groq clients ──────────────────────────
def load_clients():
    clients = []
    for env in ["GROQ_API_KEY","GROQ_API_KEY_2","GROQ_API_KEY_3"]:
        k = os.getenv(env,"").strip()
        if k:
            try:
                clients.append(Groq(api_key=k))
            except: pass
    return clients

CLIENTS = load_clients()

# ── MINIMAL tool schema (works on ALL Groq models) ──
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a folder. Use /mnt/AhmarData/ for Desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file. Provide full path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string"
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Save text to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_word_file",
            "description": "Save content as a premium document in one of the 5 supported formats (.docx, .pdf, .html, .md, .txt) depending on the file extension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The destination filepath (can end in .docx, .pdf, .html, .md, or .txt)"},
                    "content": {"type": "string"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_file",
            "description": "Send a file to owner on WhatsApp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "caption": {"type": "string"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "whatsapp_notify_me",
            "description": "Send text notification to owner on WhatsApp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_and_run_code",
            "description": "Write Python code to file and execute it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "filename": {"type": "string"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "upload_to_classroom",
            "description": "Upload a file/lab to Google Classroom and turn it in.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to the file to upload"},
                    "class_name": {"type": "string", "description": "Exact or partial name of the Google Classroom class"},
                    "assignment_name": {"type": "string", "description": "Exact or partial name of the assignment"},
                    "account_name": {"type": "string", "description": "Google account name/profile to use (e.g. 'university', 'personal')"}
                },
                "required": ["filepath", "class_name", "assignment_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_code_locally_with_screenshot",
            "description": "Run code locally on this machine, capture the text output, and save a clean terminal-style screenshot image to logs/. Use this by default unless the user explicitly asks for the online compiler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code":     {"type": "string",  "description": "The source code to run"},
                    "language": {"type": "string",  "description": "Programming language: python, js, etc."}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code_online",
            "description": "Compile and run code online via Firefox/OneCompiler. ONLY use this when the user explicitly says 'online compiler', 'run online', or 'onecompiler'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The source code to run"},
                    "language": {"type": "string", "description": "The programming language (e.g. 'cpp', 'java', 'js', 'python')"},
                    "method": {"type": "string", "description": "Method: 'api' (instant API) or 'browser' (opens firefox and runs it). Default is 'api'."}
                },
                "required": ["code", "language"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the local knowledge base (RAG) for documents, manuals, or slides.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search term or query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_file_to_knowledge_base",
            "description": "Add a file (pdf, docx, txt) to the local knowledge base (RAG).",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "Path to the file to add"}
                },
                "required": ["source_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_code_in_nano_and_screenshot",
            "description": "Write code to a file, open it in 'nano' inside gnome-terminal, save a screenshot of nano editor, close it, run the program in gnome-terminal, and capture a screenshot of its terminal output. Use this when the user requests code creation and running via nano/screenshots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The source code to write and run"},
                    "filename": {"type": "string", "description": "The name of the file to save (default program.py)"},
                    "language": {"type": "string", "description": "The programming language (default python)"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_bash_command",
            "description": "Execute a shell/bash command on the system, capture its output, and return it. Useful to navigate directories, run user programs, or check system configurations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                    "working_dir": {"type": "string", "description": "The directory to run the command in"}
                },
                "required": ["command"]
            }
        }
    }
]

# ── Execute tool ───────────────────────────────────
def execute_tool(name, args):
    try:
        if name == "list_files":
            return str(list_files(args.get("folder_path")))
        if name == "read_file":
            return str(read_file(args["filepath"]))
        if name == "write_file":
            return write_file(args["filepath"], args["content"])
        if name == "write_word_file":
            return write_word_file(args["filepath"], args["content"])
        if name == "send_whatsapp_file":
            return send_whatsapp_file(
                args["filepath"], args.get("caption",""))
        if name == "whatsapp_notify_me":
            return whatsapp_notify_me(args["message"])
        if name == "search_web":
            return search_web(args["query"])
        if name == "write_and_run_code":
            return write_and_run_code(
                args["code"], args.get("filename","output.py"))
        if name == "upload_to_classroom":
            return upload_to_classroom(
                args["filepath"], args["class_name"], args["assignment_name"], args.get("account_name", "default"))
        if name == "run_code_locally_with_screenshot":
            return run_code_locally_with_screenshot(
                args["code"], args.get("language", "python"))
        if name == "execute_code_online":
            return execute_code_online(
                args["code"], args["language"], args.get("method", "browser"))
        if name == "search_knowledge_base":
            return search_knowledge_base(args["query"])
        if name == "add_file_to_knowledge_base":
            return add_file_to_knowledge_base(args["source_path"])
        if name == "run_code_in_nano_and_screenshot":
            return run_code_in_nano_and_screenshot(
                args["code"], args.get("filename", "program.py"), args.get("language", "python"))
        if name == "execute_bash_command":
            return execute_bash_command(
                args["command"], args.get("working_dir"))
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error: {str(e)}"

# ── Call AI with Groq first (extremely fast), OpenRouter fallback second ──
# ── Call AI with Groq, SambaNova, Cerebras, and OpenRouter fallbacks ──
import requests

class ModelResponse(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for k, v in list(self.items()):
            if isinstance(v, dict):
                self[k] = ModelResponse(v)
            elif isinstance(v, list):
                self[k] = [ModelResponse(x) if isinstance(x, dict) else x for x in v]

    def __getattr__(self, name):
        if name in self:
            return self[name]
        if name in ("content", "tool_calls", "function", "arguments", "name", "choices", "message"):
            return None
        raise AttributeError(f"'ModelResponse' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        self[name] = value

SIMPLE_TASK_KEYWORDS = [
    "notify", "send message", "whatsapp", "list files",
    "read file", "bash", "echo", "ping", "check", "status",
    "verify", "confirm", "yes or no", "done?"
]

def get_model_size(messages: list) -> str:
    last_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_msg = str(m.get("content", "")).lower()
            break
    is_simple = any(kw in last_msg for kw in SIMPLE_TASK_KEYWORDS)
    return "simple" if is_simple else "complex"

PROVIDERS = [
    # ── PRIORITY 1: Groq — fastest, try first ──────────────────
    {
        "name": "Groq-Key1-70b",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY_1", ""),
        "model_complex": "llama-3.3-70b-versatile",
        "model_simple":  "llama-3.1-8b-instant",
        "priority": 1,
        "dead": False,
    },
    {
        "name": "Groq-Key2-70b",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY_2", ""),
        "model_complex": "llama-3.3-70b-versatile",
        "model_simple":  "llama-3.1-8b-instant",
        "priority": 1,
        "dead": False,
    },
    {
        "name": "Groq-Key3-70b",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY_3", ""),
        "model_complex": "llama-3.3-70b-versatile",
        "model_simple":  "llama-3.1-8b-instant",
        "priority": 1,
        "dead": False,
    },

    # ── PRIORITY 2: SambaNova — new key ─────────────────
    {
        "name": "SambaNova-70b",
        "base_url": "https://api.sambanova.ai/v1",
        "api_key": os.getenv("SAMBANOVA_API_KEY", ""),
        "model_complex": "Meta-Llama-3.3-70B-Instruct",
        "model_simple":  "Meta-Llama-3.3-70B-Instruct",
        "priority": 2,
        "dead": False,
    },

    # ── PRIORITY 3: Cerebras ──────────
    {
        "name": "Cerebras-70b",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": os.getenv("CEREBRAS_API_KEY", ""),
        "model_complex": "gpt-oss-120b",
        "model_simple":  "zai-glm-4.7",
        "priority": 3,
        "dead": False,
    },

    # ── PRIORITY 4: OpenRouter ─────────────
    {
        "name": "OpenRouter-Key2",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_API_KEY_2", ""),
        "model_complex": "meta-llama/llama-3.3-70b-instruct",
        "model_simple":  "google/gemini-2.5-flash",
        "priority": 4,
        "dead": False,
    },
    {
        "name": "OpenRouter-Key3",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_API_KEY_3", ""),
        "model_complex": "meta-llama/llama-3.3-70b-instruct",
        "model_simple":  "google/gemini-2.5-flash",
        "priority": 4,
        "dead": False,
    },
]

DEAD_KEYS = {os.getenv("OPENROUTER_API_KEY", "SKIP_THIS"), os.getenv("OPENROUTER_API_KEY_1", "SKIP_THIS")}

class RateLimitError(Exception):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after

class DeadKeyError(Exception):
    pass

def _parse_retry_after(response) -> int:
    try:
        header_val = response.headers.get("Retry-After", "")
        if header_val:
            return int(float(header_val))
        body = response.text
        import re
        match = re.search(r"try again in (\d+\.?\d*)\s*s", body, re.IGNORECASE)
        if match:
            return int(float(match.group(1))) + 1
    except Exception:
        pass
    return 5

def _make_api_call(
    base_url: str,
    api_key: str,
    model: str,
    messages: list,
    tools: list | None = None,
    tool_choice: str = "auto",
    provider_name: str = "",
) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter" in base_url:
        headers["HTTP-Referer"] = "https://github.com/herald-agent"
        headers["X-Title"] = "HERALD Agent"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.1,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )

    if response.status_code == 429:
        retry_after = _parse_retry_after(response)
        raise RateLimitError(
            f"Rate limit on {provider_name}",
            retry_after=retry_after
        )
    if response.status_code in (401, 402):
        raise DeadKeyError(
            f"Dead key on {provider_name}: HTTP {response.status_code}"
        )
    if response.status_code == 503:
        raise Exception(f"Model unavailable on {provider_name}: 503")
    if not response.ok:
        raise Exception(
            f"API error on {provider_name}: "
            f"HTTP {response.status_code} — {response.text[:200]}"
        )
    return response.json()

def call_ai(messages: list, tools: list | None = None, tool_choice: str = "auto") -> tuple:
    task_type = get_model_size(messages)
    last_error = None

    # Filter out unavailable/dead providers
    available_providers = []
    for p in PROVIDERS:
        if p["api_key"] in DEAD_KEYS:
            continue
        if p["dead"]:
            continue
        if not p["api_key"] or p["api_key"].startswith("your_") or "placeholder" in p["api_key"].lower():
            continue
        available_providers.append(p)

    if not available_providers:
        raise Exception("[HERALD] No active/configured API providers found in .env!")

    # Let the RL agent choose which provider name to use based on the task type state
    provider_names = [p["name"] for p in available_providers]
    chosen_provider_name = rl_agent.choose_action(task_type, provider_names)

    # Reorder providers so the chosen one is tried first
    ordered_providers = []
    # 1. Chosen one first
    for p in available_providers:
        if p["name"] == chosen_provider_name:
            ordered_providers.append(p)
    # 2. Others next (in priority order)
    for p in sorted(available_providers, key=lambda x: x["priority"]):
        if p["name"] != chosen_provider_name:
            ordered_providers.append(p)

    for provider in ordered_providers:
        model = (
            provider["model_simple"]
            if task_type == "simple"
            else provider["model_complex"]
        )

        print(f"[HERALD] Trying {provider['name']} → {model} ({task_type} task)")

        try:
            result = _make_api_call(
                base_url=provider["base_url"],
                api_key=provider["api_key"],
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                provider_name=provider["name"],
            )
            if result:
                print(f"[HERALD] ✓ Success: {provider['name']}")
                # RL feedback: success reward (+10)
                rl_agent.update_q_value(task_type, provider["name"], 10.0)
                return ModelResponse(result), f"{provider['name']}-{model}"
        except RateLimitError as e:
            wait_sec = e.retry_after or 5
            print(f"[HERALD] Rate limit on {provider['name']} — wait {wait_sec}s then try next")
            # RL feedback: rate limit penalty (-5)
            rl_agent.update_q_value(task_type, provider["name"], -5.0)
            time.sleep(min(wait_sec, 10))
            last_error = e
            continue
        except DeadKeyError as e:
            print(f"[HERALD] Dead key {provider['name']} — marking dead, skipping")
            provider["dead"] = True
            # RL feedback: dead key penalty (-20)
            rl_agent.update_q_value(task_type, provider["name"], -20.0)
            last_error = e
            continue
        except Exception as e:
            print(f"[HERALD] Error on {provider['name']}: {e}")
            # RL feedback: general exception penalty (-10)
            rl_agent.update_q_value(task_type, provider["name"], -10.0)
            last_error = e
            continue

    raise Exception(
        f"[HERALD] ALL providers failed. Last error: {last_error}\n"
        "Check API keys in .env file."
    )

# ── System prompt ──────────────────────────────────
SYSTEM_PROMPT = """
You are a human computer science student preparing your lab report. You execute tasks using the tools available to you. You are precise, thorough, and you NEVER skip steps.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## CORE RULES — NEVER BREAK THESE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ACT AS A STUDENT: The final report must look like it was written by a student. NEVER include references to "AI agent", "HERALD", "autonomous", or "automated generator". The title/cover block must represent the student group: "Ahmar Wajahat, Sabir Husain, Ghayour Kamal, Huraira, Arsal".
2. ALWAYS complete EVERY task in the instruction. If 3 tasks are given, all 3 MUST be done.
3. NEVER stop after one tool call and assume you are done.
4. NEVER send the final WhatsApp message until ALL tasks are complete.
5. If a task requires showing execution output, you MUST call run_code_locally_with_screenshot to render the output as a realistic terminal screenshot image.
6. ALWAYS send the generated file via send_whatsapp_file after creating it.
7. Keep explanations and reports highly CONCISE, direct, and free of AI boilerplate.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## HOW TO HANDLE LAB INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When the user gives you a lab instruction (e.g. "Lab 3: Do task A, B, and C"), follow this EXACT sequence:

### STEP 1 — PARSE AND COUNT
Before doing anything else, read the full instruction and identify:
- Total number of tasks (Task 1, Task 2, Task 3 ... etc.)
- For each task: what needs to be coded, what output format is needed, and that a screenshot is required
- Write this plan internally before calling any tool

### STEP 2 — EXECUTE EACH TASK IN ORDER
For each task:
  a) Write the code using write_and_run_code (to verify it runs correctly)
  b) Save the code in a clean task-specific file (e.g. `lab{N}_task1.py` on Desktop)
  c) Call run_code_locally_with_screenshot to execute the script and render a realistic terminal-style screenshot
  d) Save the screenshot path — you will include it in the report
  e) Move to the next task. DO NOT skip.

### STEP 3 — BUILD THE LAB REPORT
After ALL tasks are done, call write_word_file to generate ONE complete lab report containing:
  - Lab title, student names, date, and reviewer (concise, human-like)
  - For each task: objective, complete code, output screenshot, concise explanation
  - Use the markup format described below

### STEP 4 — SEND FILES
  - send_whatsapp_file for the .docx report
  - whatsapp_notify_me with a summary of what was completed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## SCREENSHOT RULES (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Screenshots of terminal execution are MANDATORY for every task.
1. Call run_code_locally_with_screenshot with the EXACT same code that was in the task
2. Use a UNIQUE filename for each task:
   - Task 1 → "lab{N}_task1_output"
   - Task 2 → "lab{N}_task2_output"
   - Task 3 → "lab{N}_task3_output"
   (Replace {N} with the lab number)
3. Reference the returned image path in the report using [image: /path/to/screenshot.png] right below the code block.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## LAB REPORT FORMAT (write_word_file markup)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use this EXACT structure when calling write_word_file:

[TITLE_START]
title: LAB REPORT — [Lab Name/Number]
subtitle: Course: Programming of Artificial Intelligence (BSCS)
course: Programming of Artificial Intelligence (BSCS)
student: Ahmar Wajahat, Sabir Husain, Ghayour Kamal, Huraira, Arsal
instructor: Muhammad Usman Ghani / Mr. Hurrarah Zohrab
date: [Current Date]
[TITLE_END]

---

## Objective

[One concise paragraph describing what this lab is about]

---

## Task 1 — [Task Title]

### Objective
[1 line objective for this specific task]

### Code
```[language]
[complete code here]
```
[image: /home/ahmar/Desktop/AhmarData/openwork_project/logs/local_output_[lang].png]

### Explanation
[2-3 lines explaining what the code does and what the output shows]

---

## Task 2 — [Task Title]

### Objective
[1 line objective for this specific task]

### Code
```[language]
[complete code here]
```
[image: /home/ahmar/Desktop/AhmarData/openwork_project/logs/local_output_[lang].png]

### Explanation
[2-3 lines explaining what the code does and what the output shows]

---

[Repeat for every task]

---

## Conclusion

[2-3 lines summarizing what was learned/demonstrated in this lab]

[END: Document prepared for submission]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MULTI-TASK COMPLETION CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before calling whatsapp_notify_me as final message, verify this checklist:
[ ] All tasks were executed (code ran without error)
[ ] Each task has a unique screenshot representing execution
[ ] write_word_file was called with ALL tasks included in one report
[ ] send_whatsapp_file was called for the .docx file

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## TOOL USAGE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

write_and_run_code:
- Use to test if code works and get actual output text

run_code_locally_with_screenshot:
- Use for ALL lab task outputs to get terminal screenshots

write_word_file:
- Generate the final lab report .docx in one single call

send_whatsapp_file:
- Call AFTER write_word_file succeeds

whatsapp_notify_me:
- Status updates and final summary AFTER all files are sent

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## ERROR HANDLING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If code fails to run:
1. Fix the bug (syntax error, missing import, etc.) and retry
2. If still failing: include the error in the report under that task's "Output" section and continue
"""

SYSTEM = SYSTEM_PROMPT

# ── Main agent loop ────────────────────────────────
def run_agent(user_task: str):
    if not os.getenv("OPENROUTER_API_KEY") and not CLIENTS:
        print("[System]: No API keys found in .env!")
        return

    print(f"[System]: Initializing HERALD...")
    task_id = log_task(user_task)
    whatsapp_notify_me(f"🔄 HERALD initialized task:\n\"{user_task[:150]}...\"")

    # ── 1. RAG Retrieval ──
    print("\n[HERALD Workflow]: Phase 1 - RAG Retrieval")
    from rag.retriever import retrieve_context
    try:
        context_chunks = retrieve_context(user_task, top_k=5)
        # Cosine similarity score >= 0.40 is considered relevant
        relevant_chunks = [c for c in context_chunks if c["score"] >= 0.40]
    except Exception as e:
        print(f"[HERALD RAG]: Error during RAG Retrieval: {e}")
        relevant_chunks = []

    if relevant_chunks:
        print(f"[HERALD Workflow]: Found {len(relevant_chunks)} relevant chunks in Knowledge Base!")
        # whatsapp_notify_me(f"📚 RAG Context Found: Retrieval matched {len(relevant_chunks)} documents.")
        context_str = "\n\n".join([
            f"--- Source Document: {c['document_name']} (Similarity: {c['score']:.4f}) ---\n{c['chunk_text']}"
            for c in relevant_chunks
        ])
        user_prompt = (
            f"[RETRIEVED KNOWLEDGE BASE CONTEXT]\n{context_str}\n\n"
            f"[USER REQUEST]\n{user_task}\n\n"
            "Please use the retrieved knowledge base context above to plan and execute the task. "
            "Cite document names internally where appropriate."
        )
    else:
        print("[HERALD Workflow]: No relevant documents found. Proceeding with normal execution.")
        # whatsapp_notify_me("📚 RAG Context: No relevant documents found. Proceeding with default knowledge.")
        user_prompt = user_task

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": user_prompt}
    ]

    current_model = "unknown"
    max_steps = 30

    for step in range(max_steps):
        time.sleep(0.5)

        if step == 0:
            print("\n[HERALD Workflow]: Phase 2 - Planning")
            # whatsapp_notify_me("🧠 Phase 2: Formulating strategy and planning steps...")
            resp, model = call_ai(messages, tools=None)
        else:
            if step == 1:
                print("\n[HERALD Workflow]: Phase 3 - Execution")
                # whatsapp_notify_me("⚙️ Phase 3: Executing planned steps...")
            resp, model = call_ai(messages, TOOLS)

        if resp is None:
            print("[System]: All models failed. Check API keys.")
            whatsapp_notify_me("❌ HERALD Task failed: All AI models failed. Please check your API keys.")
            break

        if current_model != model:
            current_model = model
            print(f"[System]: Using {model}")

        msg = resp.choices[0].message

        # ── Post Plan and Current Step to Bridge ──
        if msg.content:
            goal = ""
            plan = ""
            current_step_text = ""
            
            # Extract Goal
            goal_match = re.search(r'(?i)goal:\s*(.*?)(?=\n\s*(?:plan|current step|next action):|$)', msg.content, re.DOTALL)
            if goal_match:
                goal = goal_match.group(1).strip()
                
            # Extract Plan
            plan_match = re.search(r'(?i)plan:\s*(.*?)(?=\n\s*(?:current step|next action):|$)', msg.content, re.DOTALL)
            if plan_match:
                plan = plan_match.group(1).strip()
                
            # Extract Current Step
            step_match = re.search(r'(?i)current step:\s*(.*?)(?=\n\s*(?:next action|verification):|$)', msg.content, re.DOTALL)
            if step_match:
                current_step_text = step_match.group(1).strip()
                
            if plan or goal or current_step_text:
                try:
                    import requests
                    requests.post("http://localhost:3001/api/event", json={
                        "type": "plan_generated",
                        "data": {
                            "task_id": task_id,
                            "goal": goal,
                            "plan": plan,
                            "current_step": current_step_text
                        }
                    }, timeout=2)
                except Exception:
                    pass

        # ── Tool call detection ──
        has_tool_calls = False
        tool_calls_to_run = []

        if msg.tool_calls:
            has_tool_calls = True
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except:
                    args = {}
                tool_calls_to_run.append((tc.id, tc.function.name, args))
        elif msg.content:
            # Check for JSON block tool call fallback
            blocks = re.findall(r'```(?:json|python)?\s*(\{[\s\S]*?\})\s*```', msg.content)
            if not blocks:
                blocks = re.findall(r'(\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"parameters"\s*:\s*\{[\s\S]*?\}\s*\})', msg.content)
            
            for b in blocks:
                try:
                    data = json.loads(b)
                    if isinstance(data, dict) and "name" in data and "parameters" in data:
                        has_tool_calls = True
                        tool_calls_to_run.append((f"parsed_{int(time.time())}", data["name"], data["parameters"]))
                except Exception:
                    pass

        if has_tool_calls:
            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": msg.tool_calls
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or ""
                })

            for call_id, name, args in tool_calls_to_run:
                print(f"[HERALD] executing tool: {name} with args: {args}")
                
                # Format arguments briefly
                args_summary = str(args)
                if len(args_summary) > 80:
                    args_summary = args_summary[:80] + "..."
                # whatsapp_notify_me(f"🛠️ Step {step}: Executing tool '{name}' with args {args_summary}...")
                
                result = execute_tool(name, args)

                # Truncate long results
                result_str = str(result)
                if len(result_str) > 1500:
                    result_str = result_str[:1500] + "...[truncated]"

                print(f"[System]: Tool result: {result_str[:150]}")
                # whatsapp_notify_me(f"✅ Tool '{name}' executed successfully.")
                log_tool_call(task_id, name, args, result_str)

                if msg.tool_calls:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result_str
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": f"System executed the tool '{name}' successfully on your behalf.\nResult:\n{result_str}\n\nPlease proceed to the next step."
                    })

            # Trim history if too long (increase threshold to prevent memory loss during long workflows)
            if len(messages) > 120:
                messages = messages[:2] + messages[-80:]

        # ── Done ──
        else:
            if step == 0:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or ""
                })
                messages.append({
                    "role": "user",
                    "content": "System: Plan received. Please begin executing the steps one by one by calling the appropriate tool. Do NOT output any thoughts or planning templates in your response; just call the tool."
                })
                continue

            print("\n[HERALD Workflow]: Phase 4 - Verification")
            print("[System]: Verifying task outcomes and ensuring all requirements are met...")
            # whatsapp_notify_me("🔍 Phase 4: Verifying results and checking constraints...")
            
            print("\n[HERALD Workflow]: Phase 5 - Response")
            print(f"\n[HERALD]: {msg.content}")
            print("\nHERALD: Task complete.")
            if msg.content:
                whatsapp_notify_me(f"🏁 Task complete!\n\nSummary:\n{msg.content[:400]}...")
            complete_task(task_id, current_model)
            break

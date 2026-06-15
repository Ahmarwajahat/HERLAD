# ORION Configuration & Missing Requirements Checklist

This checklist helps you track the state of your development environment, API key rotations, backend services, and permission settings.

---

## 🔑 API Keys Configuration Status

| Key Name | Configured? | Action Required |
|---|---|---|
| `OPENROUTER_API_KEY` | **Yes** (Active) | None. |
| `OPENROUTER_API_KEY_2` | **No** (Placeholder) | Replace `sk-or-v1-key2_here` in `.env` with a valid OpenRouter key. |
| `OPENROUTER_API_KEY_3` | **No** (Placeholder) | Replace `sk-or-v1-key3_here` in `.env` with a valid OpenRouter key. |
| `GROQ_API_KEY` | **Yes** (Active) | None. |
| `GROQ_API_KEY_2` | **Yes** (Active) | None. |
| `GROQ_API_KEY_3` | **No** (Placeholder) | Replace `gsk_key3_here` in `.env` with a valid Groq key. |
| `GEMINI_API_KEY` | **No** (Invalid format) | Key starts with `AQ.` (intended for Advanced/OAuth) rather than `AIzaSy` (developer key). Standard developer models will return a 404 error. |

---

## ⚙️ Backend Services Status

- [x] **WhatsApp Node.js Bridge**: Online (Running on port 3001).
- [x] **React Dashboard**: Online (Running on port 5173).
- [x] **ORION Daemon**: Online (Running on port 5000).
- [ ] **MongoDB**: **Offline**
  - *Current Behavior*: Falls back to local JSON logging at `logs/pending_tasks.json`.
  - *Action Required*: Start the MongoDB service if you want persistent database storage.
    ```bash
    sudo systemctl start mongod
    ```

---

## 🛡️ Antigravity Auto-Run Permissions

Antigravity prompts you for permission before executing commands or modifying files on your system. 

### How to Auto-Run / Bypass Dialogs:
1. **Safe Command Auto-Approval**: Antigravity is configured to mark all read-only, check-only, and compilation testing commands with `SafeToAutoRun: true` where safe. This allows them to execute instantly without prompting you.
2. **Interactive/Destructive Security Boundaries**: For safety and security, state-changing commands (like starting background servers, killing processes, or deleting core code) will always prompt you for confirmation. 

# Taskflow — AI Task Management Agent

Taskflow is a local-first task manager with a responsive Flask web dashboard,
an Ollama-powered natural-language agent, and the original Tkinter desktop app.
Both interfaces share `task_manager.py` and the existing `tasks.json` data.

## Run the web application on macOS

1. Install [Ollama](https://ollama.com/download), open it, then fetch the model:

   ```sh
   ollama pull llama3.2:3b
   ```

2. From the project folder, install dependencies and start Flask:

   ```sh
   cd /Users/chosiga/Desktop/AI-Task-Agent
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   python -m backend.app
   ```

3. Open <http://127.0.0.1:5000>.

Flask binds only to `127.0.0.1`; do not change it to a public interface. Ollama
is used through its local service and is not exposed by this application. To
use a different Python installation, create/activate a virtual environment
first and run the same install/start commands.

## Web app features

- Overview with total, pending, completed and completion-rate summaries.
- Search and status/priority filters, with task priorities and due dates.
- Add, edit, complete/reopen and delete tasks. Deletion requires explicit
  confirmation in the interface.
- Natural-language chat backed by Ollama tool calls. The model can only select
  the predefined task functions; the backend executes them and never runs
  arbitrary generated Python or shell commands.
- `POST /api/chat` accepts conversation messages and returns the local model
  reply as JSON. `GET /api/health` checks Ollama availability and the configured
  model installation.
- Task data persists in `tasks.json`. Existing tasks without a priority are
  displayed as medium priority and remain compatible.

## Existing desktop and CLI interfaces

The original desktop app is still available:

```sh
python assistant.py
```

For the terminal interface:

```sh
python assistant.py --cli
```

## Project files

- `index.html`, `tasks.html`, and `assistant.html` provide the dashboard, task
  form, and assistant chat.
- `style.css` contains the responsive SaaS-style visual design.
- `dashboard.js`, `tasks.js`, and `assistant.js` render task data, call the
  Flask API, and handle explicit deletion confirmation.
- `backend/app.py` serves the frontend and validates JSON API requests.
- `backend/assistant.py` and `backend/task_manager.py` are web-facing adapters
  to the existing agent and shared task logic.
- `assistant.py` connects Llama 3.2 tool calls to a strict allowlist of task
  functions; the same agent is used by web, desktop and CLI.
- `task_manager.py` validates and performs task operations against the JSON
  file, including update and priority operations.
- `gui.py` remains the original Tkinter desktop interface.
- `tests/` contains offline tests for task storage, tool routing, API behavior
  and deletion confirmation.

## Run tests

```sh
python -m unittest discover -s tests -v
```
//thank you 
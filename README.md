# Taskflow

Taskflow is a local-first task manager that combines a responsive web interface,
an Ollama-powered AI assistant, and a Tkinter desktop application. Tasks are
stored in `tasks.json`, so the web, desktop, and CLI interfaces share the same
task data.

## Features

- View task totals, pending work, completed work, and completion rate
- Search tasks and filter by status or priority
- Add, edit, complete, reopen, and delete tasks
- Schedule tasks with due dates and optional start/end times
- Manage tasks through natural-language chat
- Run AI locally through Ollama
- Require explicit confirmation before deleting tasks

## Requirements

- macOS
- Python 3
- [Ollama](https://ollama.com/download)
- The `llama3.2:3b` model

## Installation

Clone the repository and open the project directory:

```sh
cd AI-TASK-MANAGER
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install the local Ollama model:

```sh
ollama pull llama3.2:3b
```

Make sure Ollama is running, then start the web application:

```sh
python -m backend.app
```

Open <http://127.0.0.1:5000>.

## Interfaces

### Web application

The web interface includes an overview dashboard, task management workspace,
and AI assistant chat.

```text
index.html       Overview dashboard
tasks.html       Task list and task editor
assistant.html   AI assistant chat
style.css        Shared responsive styles
```

### Desktop application

Launch the original Tkinter desktop interface:

```sh
python assistant.py
```

### Command-line assistant

Launch the interactive assistant in the terminal:

```sh
python assistant.py --cli
```

## AI behavior

Taskflow uses Ollama only for natural-language understanding and tool selection.
The application exposes a fixed set of task functions, so generated requests
cannot execute arbitrary Python or shell commands.

The web API exposes:

- `GET /api/tasks` - list tasks
- `POST /api/tasks` - create a task
- `PUT /api/tasks/<id>` - update a task
- `PATCH /api/tasks/<id>/complete` - complete a task
- `PATCH /api/tasks/<id>/reopen` - reopen a task
- `DELETE /api/tasks/<id>` - delete a confirmed task
- `POST /api/chat` - send messages to the local assistant
- `GET /api/health` - check Ollama and model availability

## Data

Tasks are persisted in `tasks.json`. Existing tasks without a priority are
treated as medium priority for display and remain backward-compatible.

The Flask server binds only to `127.0.0.1`. Keep Ollama and the application
local unless you intentionally apply and review additional network security.

## Project structure

```text
backend/
  app.py              Flask application and API routes
  assistant.py        Web-facing assistant adapter
  task_manager.py     Web-facing task operations

assistant.py          Ollama tool-routing agent
task_manager.py       Shared task validation and storage
gui.py                Tkinter desktop interface
tests/                Task, assistant, and web API tests
```

## Run tests

Activate the virtual environment and run:

```sh
python -m unittest discover -s tests -v
```

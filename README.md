# Taskflow

Taskflow is a local-first task manager that combines a responsive web interface,
an Ollama-powered AI assistant, and a Tkinter desktop application. The goal is
to give users one shared task data store across all supported interfaces.

## Project status

This repository is organized around feature branches for a student team
project. Each branch contains the work assigned to one role, and the final
application is assembled by merging those contributions.

The branch currently checked out here is `ATM-6-Database-Engineer`. At present,
this branch contains documentation only; application source code is maintained
on the role-specific branches and is not runnable directly from this checkout.

## Planned features

- A dashboard with task totals, completion progress, and status summaries
- Task search and filtering by status and priority
- Task creation, editing, completion, reopening, and deletion
- Due dates and optional start and end times
- Natural-language task management through a local AI assistant
- Confirmation before destructive actions
- Shared task data between web, desktop, and command-line interfaces

## Interfaces

### Web application

The assembled web application will provide an overview dashboard, a task
workspace, and an AI assistant chat.

### Desktop application

The Tkinter desktop interface provides access to the same task data outside the
browser.

### Command-line assistant

The CLI assistant provides an interactive terminal interface for managing tasks
through natural language.

## Development

Use the branch that matches the work you are responsible for:

```sh
git switch ATM-6-Database-Engineer
```

For a complete application assembled from the role branches, use the relevant
integration branch and keep shared data formats compatible with the rest of the
team.

## Expected setup

Once the application source is merged into the active branch, setup is intended
to use Python virtual environments and a local Ollama installation:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Taskflow's AI assistant uses the `llama3.2:3b` Ollama model:

```sh
ollama pull llama3.2:3b
ollama serve
```

The web application is expected to be available locally at
<http://127.0.0.1:5000>.

## AI behavior

The Ollama model is used for natural-language understanding and tool selection.
Task operations should be exposed through a fixed, validated set of functions;
the model must not receive unrestricted shell or Python execution capabilities.

Destructive operations, especially task deletion, should require explicit
confirmation.

## Data

The project is planned to persist tasks in a shared local data store so web,
desktop, and CLI users observe the same tasks.

The exact database implementation and schema should be documented on the branch
that introduces that integration. Until source code is available, the format of
the shared task records is intentionally not specified in this README.

## Security and privacy

Keep Ollama and local application services bound to loopback addresses unless
remote access is deliberately required and protected.

Do not commit API keys, credentials, personal task data, or generated database
files. The AI assistant should be able to manage tasks only through approved
application operations.

## Contributing

1. Switch to the appropriate role branch.
2. Make focused changes for that role.
3. Test the relevant application behavior.
4. Open a pull request for review and integration.

Keep changes limited to the assigned role to avoid conflicting edits in shared
files.

# Bibliometric Data Collection Project

Welcome to the team. Follow this guide to set up the project and contribute safely.

---

## Phase 1: Initial Setup

1. Open Terminal (`Command Prompt`/`PowerShell` on Windows).
2. Move to your Desktop:

```bash
cd Desktop
```

3. Clone the repository:

```bash
git clone <YOUR_REPO_URL_HERE>
```

4. Enter the project folder:

```bash
cd Software-Group-Project-Bibliometric-Data-Collection
```

---

## Phase 2: Daily Workflow (Safe Branching)

Never code directly on `main`. Always create a feature branch.

1. Get the latest code:

```bash
git checkout main
git pull origin main
```

2. Create your work branch:

Replace `task-name` with your task (example: `api-fix`).

```bash
git checkout -b feature/task-name
```

3. Save your work:

```bash
git add .
git commit -m "Brief description of what you changed"
```

---

## Phase 3: Share Your Work

1. Push your branch:

```bash
git push -u origin feature/task-name
```

2. Create a Pull Request (PR):
- Go to the repository on GitHub.
- Click **Compare & pull request**.
- Add a clear title/description.
- Click **Create pull request**.

---

## Important Rules

- Do not push `node_modules/`, `.venv/`, or `venv/`.
- Do not push `.env` files (API keys/secrets).
- Always pull latest `main` before creating a new branch.
 changed for check

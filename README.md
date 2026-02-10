

📚 Bibliometric Data Collection Project

Welcome to the team! Follow this guide to set up the project on your computer and start contributing.



================================================================================================
 🏁 Phase 1: Initial Download

1. Open your Terminal(Command Prompt or PowerShell on Windows).
2. Move to your Desktop:

# cd Desktop

3. Clone the project:

# git clone <YOUR_REPO_URL_HERE>


4. Enter the folder:

# cd Software-Group-Project-Bibliometric-Data-Collection

======================================================================================================

🛠️ Phase 2: Daily Workflow (The "Safe" Way)

To avoid overwriting each other's work, we use **Branches**. Never code directly on the `main` branch!

1. Get the latest code

Before starting any new task, make sure your local code is up to date:

# git checkout main
# git pull origin main


 2. Create a Work Branch

Create a new "playground" for your specific task:
    Replace 'task-name' with what you are doing (e.g., feature/api-fix)
# git checkout -b feature/task-name


3. Save your work

As you write code, save your progress locally:


# git add .
# git commit -m "Brief description of what you changed"


================================================================================================


📤 Phase 3: Sharing your work

When your task is finished and tested:

1. Push to GitHub

# git push origin feature/task-name




2. Create a Pull Request (PR):
 Go to the project page on GitHub.
 Click the green **"Compare & pull request"** button.
 Add a title and click **"Create pull request"**.


=======================================================================


## ⚠️ Important Rules

* 🚫 **Do not push** `node_modules/` or `venv/` folders.
* 🔑 **Do not push** `.env` files (API keys).
* ✅ **Always pull** before you start a new branch.


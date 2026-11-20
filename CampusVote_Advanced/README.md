# CampusVote – Advanced Online Voting System

A student-level Software Engineering and System Design project built with **Python, Flask, HTML, CSS, and SQLite**. This version expands the original application with election scheduling, multiple elections, candidate management, voter participation history, vote receipts, result charts, CSV export, and an administrative audit log.

> **Important:** This is an academic demonstration application, not a secure or certified platform for public elections. It is intended for local classroom demonstrations only. Do not use it for real elections or sensitive voting.

## Features

### Voter features
1. Voter registration with full name, username, email, and password.
2. Password hashing using Werkzeug security utilities.
3. Login and logout with role-based access.
4. Voter dashboard showing elections and participation status.
5. Multiple elections, each with its own candidates and voting period.
6. Candidate profiles with position and short manifesto/statement.
7. One vote per registered account per election, enforced by a database unique constraint.
8. Confirmation receipt code after successful vote submission.
9. Profile editing and participation history.
10. Public results page with candidate-wise vote totals and proportional bars.

### Administrator features
11. Admin dashboard with voter, election, candidate, and ballot counts.
12. Create elections with start and end date/time.
13. Change election status (Draft, Open, Closed).
14. Add candidates to a selected election.
15. Delete candidates only when they have no recorded ballots.
16. Export election results to CSV.
17. Audit log showing recent account and administration actions.

### Application features
18. Responsive layout for desktop and mobile screens.
19. Server-side validation for important form fields.
20. Basic CSRF form-token checking.
21. SQLite foreign keys and database constraints.
22. Friendly error pages for common HTTP errors.

## Requirements
- Windows 10/11, macOS, or Linux
- Python 3.10 or later
- Visual Studio Code (recommended)
- A modern web browser

## Run in VS Code (Windows)

1. Extract the ZIP file.
2. Open the extracted `CampusVote_Advanced` folder in VS Code.
3. Open **Terminal → New Terminal**.
4. Create a virtual environment:

   ```bash
   python -m venv venv
   ```

5. Activate it in PowerShell:

   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use Command Prompt instead:

   ```cmd
   venv\Scripts\activate.bat
   ```

6. Install Flask:

   ```bash
   python -m pip install -r requirements.txt
   ```

7. Start the application:

   ```bash
   python app.py
   ```

8. Open this address in Chrome:

   `http://127.0.0.1:5000`

Keep the terminal open while using the website. Press `Ctrl + C` in the terminal to stop the server.

## Demo administrator login

- Username: `admin`
- Password: `admin123`

Change this demo password before any deployment. The secret key should also be replaced with a strong environment variable named `CAMPUSVOTE_SECRET`.

## First-time demonstration flow

1. Open the website and register a new voter account.
2. Log in as the voter.
3. Open the sample **Student Council Election 2026**.
4. Review candidate names, positions, and statements.
5. Cast one vote and save the receipt code.
6. Try to vote again in the same election to see duplicate-vote prevention.
7. Open Results to view the candidate-wise totals.
8. Log out and log in using the demo administrator account.
9. Create another election, then add candidates to it.
10. Use the admin dashboard to change election status, export results as CSV, and review the audit log.

## Project structure

```text
CampusVote_Advanced/
├── app.py
├── requirements.txt
├── README.md
├── FEATURES_AND_TESTING.md
├── run_windows.bat
├── .gitignore
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── register.html
│   ├── login.html
│   ├── dashboard.html
│   ├── election.html
│   ├── results.html
│   ├── profile.html
│   ├── receipt.html
│   ├── admin.html
│   ├── new_election.html
│   ├── manage_candidates.html
│   ├── audit.html
│   └── error.html
└── static/
    └── style.css
```

The SQLite database `campusvote.db` is created automatically the first time the application starts. A sample election and three sample candidates are also created automatically for demonstration.

## Notes and limitations

- The application runs locally using Flask's development server.
- Election date/time fields use the computer's local time.
- The receipt confirms that a vote was submitted; it does not show which candidate was selected.
- The demo stores voter participation separately from anonymous ballot records, but this architecture has not been independently audited for election-grade anonymity or security.
- For production use, the system would need independent security review, secure deployment, stronger identity verification, election-specific legal compliance, robust backup and recovery, and formal privacy protections.

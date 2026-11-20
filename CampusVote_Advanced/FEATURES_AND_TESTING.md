# CampusVote – Feature Details and Testing Guide

## Functional modules

| Module | Description |
|---|---|
| Registration | Creates a voter account and checks duplicate username/email values. |
| Authentication | Verifies password hashes and establishes a login session. |
| Voter dashboard | Lists elections and shows whether the logged-in voter has participated. |
| Election management | Admin creates elections and sets start/end times and status. |
| Candidate management | Admin adds candidate names, positions, and statements to an election. |
| Voting | Checks election availability, validates candidate selection, and records participation and ballot in one database transaction. |
| Duplicate prevention | A unique database constraint allows one participation record per user per election. |
| Receipt | Generates a random receipt code confirming successful submission. |
| Results | Counts ballots by candidate and displays totals with proportional bars. |
| Profile | Allows voters to update their name/email and review participation receipts. |
| CSV export | Allows an administrator to download candidate-wise election totals. |
| Audit log | Records registration, login, logout, voting, election, candidate, and export actions. |

## Suggested manual test cases

| Test ID | Test | Expected result |
|---|---|---|
| TC-01 | Register with valid details | Account is created successfully. |
| TC-02 | Register using an existing username or email | Duplicate account is rejected with a message. |
| TC-03 | Register with a password shorter than 8 characters | Validation message is displayed. |
| TC-04 | Log in with correct voter credentials | Voter dashboard opens. |
| TC-05 | Log in with an incorrect password | Access is denied with an error message. |
| TC-06 | Open an election as a logged-in voter | Candidate list is displayed. |
| TC-07 | Submit a vote during an open election | Vote is recorded and receipt code is shown. |
| TC-08 | Attempt a second vote in the same election | Duplicate vote is prevented. |
| TC-09 | Vote in a different open election | A separate vote is allowed for that election. |
| TC-10 | Open results | Candidate-wise vote totals are displayed. |
| TC-11 | Log in as admin and create an election | New election is added. |
| TC-12 | Add candidates to an election | Candidate appears in that election. |
| TC-13 | Delete a candidate with no votes | Candidate is deleted. |
| TC-14 | Try deleting a candidate with recorded votes | Deletion is blocked. |
| TC-15 | Export results | CSV file is downloaded. |
| TC-16 | Open audit log as admin | Recent system actions are listed. |
| TC-17 | Open admin route as a voter | Access is denied. |

## Database overview

- `users`: account profile, username, email, password hash, and role.
- `elections`: election title, description, start/end time, and status.
- `candidates`: candidate details associated with an election.
- `participation`: records that a user has participated in an election and stores a receipt code. A unique `(user_id, election_id)` constraint prevents a second participation record.
- `ballots`: candidate selection and election ID, stored separately from the voter identity table.
- `audit_logs`: records key user and administrator actions.

## Suggested screenshots for the report

1. Home page showing available elections.
2. Voter registration page.
3. Login page.
4. Voter dashboard showing election participation status.
5. Election page showing candidate cards and manifestos.
6. Vote receipt page after successful submission.
7. Duplicate-vote prevention message.
8. Results page with vote totals.
9. Admin dashboard with summary statistics.
10. Create election page.
11. Candidate management page.
12. Audit log page.
13. CSV results opened in a spreadsheet application.
14. VS Code project folder and terminal showing the Flask server running.

Only insert screenshots captured from your own running application.

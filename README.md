# Discord Payment Auditor Bot

This is a simple Discord bot designed for tracking and auditing payments submitted in a Discord server.

## Features

- `/pay` — Interactive payment submission form.
    - Submit creator name, payment amount, payment details, and optional note.
    - Automatically tags the user who submitted the payment.
    - Optionally attach a PDF bill (sent after filling out the form).

- `!scan <username> <month/year>` — Monthly audit report.
    - Search for all payments submitted by a specific user for a given month/year.
    - Example: `!scan jacobm6039 4/2025`
    - Displays a summary of:
        - Creator paid
        - Amount
        - Submission date
    - Results are printed in Discord for visibility and to the console for logging.

---

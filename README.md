# Discord Payment & Audit Bot Information

This document provides a concise overview of how the Discord Payment & Audit Bot works. The bot enables payment submissions via interactive dropdowns and modals, audits payment records by filtering database entries, and lists all server members.

## Core Features

### Interactive Payment Submission
- **Slash Command `/pay`**  
  1. **Select Creator:** Pick from a dropdown of creators (or add a new one).  
  2. **Select App:** Pick from a dropdown of supported apps.  
  3. **Fill Modal:** Enter payment details:
     - **Amount** (no dollar sign)  
     - **Payment Info** (method/details or `pdf`)  
     - **Note** (optional; defaults if you plan to attach a PDF later)  
- **Data Logging**  
  On submit, the bot captures:
  - Creator name  
  - App name  
  - Discord username  
  - Amount  
  - Timestamp  
  …and inserts a record into the `queued_payments` table, then sends a confirmation.

### Payment Audit
- **Slash Command `/audit <username|all> <app|all> <M/YY>`**  
  Filters the `queued_payments` table by:
  1. **Username** (specific or `all`)  
  2. **App** (specific or `all`)  
  3. **Month/Year** (M/YY format, e.g., `4/2025`)  
- **Output**  
  Returns an ephemeral summary showing:
  - Number of payments  
  - Total amount  
  - Per‑payment lines with Creator, App, Amount, and Date

### User Listing
- **Slash Command `/users`**  
  Ephemerally lists all guild member names.  
  _Note: Requires `intents.members = True` in code and in the Developer Portal._

### Utility Commands
- **Prefix Command `!ping`**  
  Replies “Pong!” to confirm the bot is online.  
- **Slash Command `/commands`**  
  Ephemerally displays this help overview.

## Workflow Overview

1. **Payment Submission**  
   - User runs `/pay` → selects creator → selects app → fills out modal → bot logs to DB → bot confirms.  
2. **Auditing Payments**  
   - User runs `/audit <username|all> <app|all> <M/YY>` → bot queries DB → bot returns ephemeral summary.  
3. **User Listing**  
   - User runs `/users` → bot returns ephemeral list of server members.  
4. **Help & Ping**  
   - `/commands` for help; `!ping` to check connectivity.
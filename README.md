# Discord Payment & Audit Bot Information

This document provides a concise overview of how the Discord Payment & Audit Bot works. The bot enables payment submissions via interactive modals, audits payment records by filtering messages, and lists all server members.

## Core Features

### Interactive Payment Submission
- **Slash Command `/pay`**:  
  Launches a modal for users to submit payment data, including:
  - **Creator Name** (the name of the creator)
  - **Amount** (entered without a dollar sign)
  - **Payment Info** (payment method/details or the keyword `pdf`)
  - **Note** (optional; defaults to a preset message if a PDF bill is to be sent later)
- **Data Logging**:  
  Upon submission, the bot retrieves the user's Discord name, logs the current timestamp, and sends a confirmation with the payment details.

### Payment Audit
- **Command `!audit <username> <mo/year>`**:  
  Scans logged payment messages by filtering with the provided username and month/year (M/YY format).  
  **Update**: Use `all` as the username to retrieve payments for every user in the specified month.
  - The command extracts fields (creator name, amount, submission date) from messages and returns a summary along with the total summed amount.

### User Listing
- **Command `!users`**:  
  Lists all usernames in the server using the full guild member list.
  - **Note**: Ensure the `members` intent is enabled in both the code (`intents.members = True`) and the Discord Developer Portal.

### Utility Commands
- **Ping (`!ping`)**:  
  Responds with "Pong!" to confirm the bot is online.
- **Commands Info (`!commands`)**:  
  Displays a summary of all available commands.

## Workflow Overview

1. **Payment Submission:**  
   Users trigger `/pay`, fill out the modal, and submit payment details. The bot logs the data and sends a confirmation message.

2. **Auditing Payments:**  
   An admin runs `!audit <username> <mo/year>`.  
   - If a specific username is provided, only payments from that user are shown.
   - If `all` is used, payments for all users during the specified month are returned.
   - The summary includes a count of payments and the total amount.

3. **User Listing:**  
   Running `!users` returns all server member names (make sure the members intent is enabled).
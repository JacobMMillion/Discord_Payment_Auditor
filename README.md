# Discord Payment & Audit Bot Information

This document provides an overview of how the Discord Payment & Audit Bot works. The bot facilitates payment submissions via interactive modals and enables auditing of those submissions via commands. It also allows server administrators to list all members in the server.

## Core Features

### Interactive Payment Submission
- **Slash Command `/pay`:**  
  Launches an interactive modal where users submit payment data.  
  The modal collects:
  - **Creator Name:** The name of the creator.
  - **Amount:** The payment amount (entered without a dollar sign).
  - **Payment Info:** Information on the payment method/details, or the keyword `pdf` if applicable.
  - **Note:** An optional field that defaults to a message if a PDF bill is to be sent later.
  
- **Automatic Data Logging:**  
  When the modal is submitted:
  - The bot automatically retrieves the user's Discord name.
  - It records the current timestamp.
  - A confirmation message is sent that includes the submitted payment details, the submitting user’s name, and the timestamp.

### Payment Audit
- **Command `!audit <username> <mo/year>`:**  
  This command scans through previously logged payment messages in the channel.  
  It works by:
  - Iterating over the bot’s message history (filtered by a specific header).
  - Extracting relevant fields (creator name, amount, submission date) from each message.
  - Matching submissions based on the provided username and month/year (in M/YY format).
  - Returning a summary of all matching payment records.

### User Listing
- **Command `!users`:**  
  Lists all usernames in the server.  
  - This command uses the server's member list from the guild.
  - **Note:** Ensure the `members` intent is enabled both in the code (`intents.members = True`) and in the Discord Developer Portal, so the full member list is accessible.

### Utility Commands
- **Ping Command (`!ping`):**  
  Responds with "Pong!" to verify that the bot is online.
- **Commands Info (`!commands`):**  
  Displays a summary of all available commands and their usage.

## Command Workflow Details

1. **/pay Modal Interaction:**
   - User enters `/pay` to initiate payment submission.
   - An interactive modal form appears for the user to fill in their payment data.
   - On submission, the bot logs the data and sends a confirmation message in the channel.

2. **Auditing Payments:**
   - An admin or authorized user runs `!audit <username> <mo/year>`.
   - The bot fetches recent messages in the channel looking for messages beginning with "**Payment Data Submitted**".
   - It parses each message to extract fields like creator name, amount, submission date, and the submitter's username.
   - Only the messages matching the provided criteria are summarized and sent back as a report.

3. **User Listing:**
   - A user runs `!users`.
   - The bot accesses the full member list via `ctx.guild.members` (requires proper intents) and displays all usernames in the server.

4. **Command Reference:**
   - The `!commands` command provides a consolidated view of all bot commands, ensuring that users know how to interact with the bot effectively.

## Code Structure Overview

- **Bot Initialization:**
  - The bot is configured with necessary intents: `message_content` for reading messages and `members` for accessing the server member list.
  
- **Event Handlers and Commands:**
  - The `on_ready()` event ensures the bot is synced with Discord’s slash commands.
  - Commands such as `!ping`, `!users`, and `!audit` are implemented as standard bot commands.
  - The payment submission process is handled by a custom `PaymentModal` class that extends `discord.ui.Modal`.

- **Extensibility:**
  - The code is structured to allow easy modifications or additions, such as expanding the payment modal or adding new audit features.
  - Commented sections exist for potential future PDF handling and advanced data processing.

## Example Workflow

1. **Payment Submission:**  
   A user uses `/pay` to open the modal and fill in details about a payment.
   
2. **Confirmation & Logging:**  
   Once submitted, the bot sends a confirmation message that includes the creator name, amount, payment info, and submission timestamp. This message is stored for auditing.

3. **Auditing Entries:**  
   An administrator runs `!audit username 4/2025` to retrieve all payments submitted by that user in April 2025.
   
4. **User Verification:**  
   Running `!users` returns a full list of all server members, verifying the bot’s member-caching capability.

This README summarizes the workflow, commands, and core functionality of the bot. It’s intended to help users and developers understand how the bot processes payments and audits submissions.
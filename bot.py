import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from datetime import datetime
import re

# NO LONGER NEED THESE, but leaving in case we ever want to do PDF things
# import aiohttp
# import fitz
# import tempfile
# from dataclasses import dataclass

load_dotenv()

TOKEN = os.getenv('TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    # Sync the slash commands with Discord so the new command is registered.
    await bot.tree.sync()  
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='ping', help='Responds with a greeting')
async def hello(ctx):
    await ctx.send('Pong!')


# COMMANDS INFO
@bot.command(name='commands', help='Displays available commands and how to use them.')
async def commands_info(ctx):
    response = (
        "**Available Commands:**\n\n"
        "➡️ `!users` — Lists all usernames in the current channel.\n\n"
        "➡️ `/pay` — Submit a payment via an interactive form.\n"
        "_Fill out Creator Name, Amount, and Payment Info_\n"
        "_If you have a PDF bill, fill this out and then send the PDF afterwards._\n\n"
        "➡️ `!scan <username> <mo/year>` — Audit a user's payments for a specific month/year.\n"
        "_Example:_ `!scan jacobm6039 4/2025`\n"
        "_Returns all payments submitted by that user for April 2025._"
    )
    await ctx.send(response)

@bot.command(name='users', help='Lists all usernames in the current channel.')
async def users(ctx):
    members = ctx.channel.members
    usernames = [member.name for member in members]
    response = "**Users in this channel:**\n" + "\n".join(usernames)
    await ctx.send(response)

# ----------------- START OF PAYMENT MODAL CODE (UPDATED) -----------------
# In this version, we remove the "Your Name" field so that the user's Discord name
# is auto‑populated from the interaction and cannot be changed.
# The modal will now include only 4 fields:
#   1. Name of Creator
#   2. Amount
#   3. Payment Info (combines method and details)

class PaymentModal(discord.ui.Modal, title="Submit a Payment"):
    creator_name = discord.ui.TextInput(
        label="Name of Creator",
        placeholder="Enter the creator's first and last name (capitalized)",
        style=discord.TextStyle.short
    )
    amount = discord.ui.TextInput(
        label="Amount",
        placeholder="Enter the payment amount (no dollar sign)",
        style=discord.TextStyle.short
    )
    payment_info = discord.ui.TextInput(
        label="Payment Info",
        # Updated placeholder is 66 characters (under 100)
        placeholder="Enter payment method (e.g., PayPal, ACH) and details or type 'pdf'.",
        style=discord.TextStyle.long
    )
    # Note field added with a default value.
    note = discord.ui.TextInput(
        label="Note",
        placeholder="If you have a PDF bill, fill this out and then send the PDF.",
        style=discord.TextStyle.long,
        default="If you have a PDF bill, fill this out and then send the PDF.",
        required=False
    )
        
    async def on_submit(self, interaction: discord.Interaction):
        # Automatically retrieve the user's Discord display name.
        user_name = interaction.user.name

        # Get the current date and time for the submission.
        submission_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Process the form data when the modal is submitted
        response = (
            f"**Payment Data Submitted**\n\n"
            f"__*Creator Name:*__ {self.creator_name.value}\n"
            f"__*Amount:*__ ${self.amount.value}\n"
            f"__*Payment Info:*__ {self.payment_info.value}\n\n"
            f"*Submitted by:* {user_name}\n"
            f"*Submitted on:* {submission_timestamp}"
        )
        # Send a confirmation message
        await interaction.response.send_message(response, ephemeral=False)

# Slash command version of pay (no changes here)
@bot.tree.command(name="pay", description="Submit a Payment Message via an Interactive Modal Form")
async def pay(interaction: discord.Interaction):
    modal = PaymentModal()
    await interaction.response.send_modal(modal)
# ----------------- END OF PAYMENT MODAL CODE (UPDATED) -----------------





# SCAN OVER BOT MESSAGES FILTERED BY USERNAME AND DATE (M/YY format)
@bot.command(name='scan', help='Scans payments by username and date (e.g., !scan Jacob 2/25 for Feb 2025)')
async def scan(ctx, discord_username: str, date_str: str):
    results = []   # Complete messages matching criteria
    summaries = [] # Summary lines: Creator, Amount, and Date

    # Parse the date string (expects M/YY, e.g., "2/25" for Feb 2025)
    try:
        parts = date_str.split('/')
        if len(parts) != 2:
            await ctx.send("Please provide the date in M/YY format, e.g., 2/25 for February 2025.")
            return
        month = int(parts[0])
        year_suffix = int(parts[1])
        year = 2000 + year_suffix if year_suffix < 100 else year_suffix
    except Exception:
        await ctx.send("Invalid date format. Please provide the date in M/YY format, e.g., 2/25 for February 2025.")
        return

    # Helper function to remove markdown formatting (asterisks, underscores, etc.)
    def remove_markdown(text: str) -> str:
        return re.sub(r'(\*\*\*|\*\*|\*|__)', '', text)

    async for msg in ctx.channel.history(limit=10000):  # Increase limit if needed
        if msg.author != ctx.bot.user:
            continue  # Only look at messages sent by the bot

        # Only process messages with the expected header.
        if not msg.content.startswith("**Payment Data Submitted**"):
            continue

        # Remove markdown formatting (so we have plain text)
        message_text = remove_markdown(msg.content.strip())

        # Initialize field values.
        creator = None
        amount = None
        submitted_on = None
        submitted_by = None

        # Split the message into lines to locate each field.
        lines = message_text.splitlines()
        for line in lines:
            line_lower = line.lower()
            if line_lower.startswith("creator name:"):
                creator = line[len("creator name:"):].strip()
            elif line_lower.startswith("amount:"):
                amount = line[len("amount:"):].strip()
            elif line_lower.startswith("submitted on:"):
                submitted_on_str = line[len("submitted on:"):].strip()
                try:
                    submitted_on = datetime.strptime(submitted_on_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    submitted_on = None
            elif line_lower.startswith("submitted by:"):
                submitted_by = line[len("submitted by:"):].strip()

        # Check that the message was submitted by the specified discord_username.
        if submitted_by is None or discord_username.lower() not in submitted_by.lower():
            continue

        # Check that the submission date matches the requested month and year.
        if submitted_on is None or (submitted_on.month != month or submitted_on.year != year):
            continue

        # Build a summary line from the extracted fields.
        # For each matching message in your scan command:
        summary_line = f"**Creator:** {creator or 'N/A'} | **Amount:** {amount or 'N/A'} | **Date:** {submitted_on.strftime('%Y-%m-%d')}"
        summaries.append(summary_line)
        results.append(message_text)

    # Send a final summary message in chat.
    if summaries:
        summary_text = f"✅ There are {len(summaries)} payment(s) from '{discord_username}' for {month}/{year}:\n" + "\n".join(summaries)
        await ctx.send(summary_text)
        # For verification, also print each complete message to the console.
        for m in results:
            print("—" * 50)
            print(m)
            print("—" * 50 + "\n")
    else:
        await ctx.send("📭 No payment messages found with the specified filters.")






# MAIN
bot.run(TOKEN)


# # NOTE: since we just iterate over bot messages, we do not need this

# DATA STRUCTURE
# Represents a single message with all the info we need to process it later.
# @dataclass
# class ScannedMessage:
#     author: str
#     message: str
#     attachment: str
#     message_id: int
#     timestamp: datetime

# # HELPER function to download and extract text from a PDF
# async def download_and_extract_pdf(url: str) -> str:
#     async with aiohttp.ClientSession() as session:
#         async with session.get(url) as resp:
#             if resp.status == 200:
#                 with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
#                     tmp_file.write(await resp.read())
#                     tmp_path = tmp_file.name

#     text = ""
#     try:
#         doc = fitz.open(tmp_path)
#         for page in doc:
#             text += page.get_text()
#         doc.close()
#     except Exception as e:
#         print(f"[ERROR] Failed to parse PDF: {e}")
#         return ""

#     return text
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from datetime import datetime
import re
import psycopg2 # we want to use an actual database instead of using json

# NO LONGER NEED THESE, but leaving in case we ever want to do PDF things
# import aiohttp
# import fitz
# import tempfile
# from dataclasses import dataclass

load_dotenv()
TOKEN = os.getenv('TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Enables member caching
bot = commands.Bot(command_prefix='!', intents=intents)

CONN_STR = os.getenv('DATABASE_URL')

# Load creator names from the DB
def load_creators():
    """
    Loads creator names from the 'creator_names' table.
    """
    conn = psycopg2.connect(CONN_STR)
    cursor = conn.cursor()
    
    query = "SELECT creator_name FROM creator_names;"
    cursor.execute(query)
    rows = cursor.fetchall()
    creators = [row[0] for row in rows]
    
    cursor.close()
    conn.close()
    return creators

# Save new creator names to the DB
def save_creators(creators):
    """
    Inserts a list of creator names into the 'creator_names' table.
    Uses ON CONFLICT DO NOTHING to avoid duplicate inserts.
    """
    conn = psycopg2.connect(CONN_STR)
    cursor = conn.cursor()
    
    query = """
    INSERT INTO creator_names (creator_name)
    VALUES (%s)
    ON CONFLICT (creator_name) DO NOTHING;
    """
    for creator in creators:
        cursor.execute(query, (creator,))
    
    conn.commit()
    cursor.close()
    conn.close()


# Global list for creator names, loaded from file.
global_creators = load_creators()

@bot.event
async def on_ready():
    # Sync slash commands with Discord so the new command is registered.
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
        "➡️ `!users` — Lists all usernames in the server.\n\n"
        "➡️ `/pay` — Submit a payment via an interactive form.\n"
        "_After selecting a creator (or adding one), fill out Amount and Payment Info._\n\n"
        "➡️ `!audit <username> <mo/year>` — Audit a user's payments for a specific month/year. Use `all` as the username to retrieve payments for every user.\n"
        "_Example:_ `!audit jacobm6039 4/2025` returns payments for that user in April 2025.\n"
        "_Example:_ `!audit all 4/2025` returns payments for everyone in April 2025."
    )
    await ctx.send(response)

@bot.command(name='users', help='Lists all usernames in the server.')
async def users(ctx):
    members = ctx.guild.members
    usernames = [member.name for member in members]
    response = "**Users in this server:**\n" + "\n".join(usernames)
    await ctx.send(response)

# ----------------- PAYMENT SUBMISSION WITH DROPDOWN -----------------

# This view shows a dropdown to select a creator and a button to add a new creator.
class CreatorSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CreatorSelect())
    
    @discord.ui.button(label="Add New Creator", style=discord.ButtonStyle.primary, custom_id="add_creator")
    async def add_new_creator(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddCreatorModal())

# The dropdown select for creators.
class CreatorSelect(discord.ui.Select):
    def __init__(self):
        # Build options from the global creator list.
        options = [discord.SelectOption(label=name) for name in global_creators]
        # Always include an option to add a new creator.
        options.append(discord.SelectOption(label="Other", description="Add a new creator"))
        super().__init__(placeholder="Select a creator", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        chosen = self.values[0]
        if chosen == "Other":
            await interaction.response.send_modal(AddCreatorModal())
        else:
            # Launch the Payment Modal with the selected creator name.
            await interaction.response.send_modal(PaymentModal(creator_name=chosen))

# Modal to add a new creator.
class AddCreatorModal(discord.ui.Modal, title="Add New Creator"):
    new_creator = discord.ui.TextInput(
        label="New Creator Name",
        placeholder="Enter the new creator's name",
        style=discord.TextStyle.short
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        global global_creators
        new_name = self.new_creator.value
        if new_name not in global_creators:
            global_creators.append(new_name)
            save_creators(global_creators)  # Persist the updated list to file.
            await interaction.response.send_message(f"Creator '{new_name}' added!", ephemeral=True)
        else:
            await interaction.response.send_message(f"Creator '{new_name}' already exists.", ephemeral=True)
        # Send back the creator selection view so the user can continue.
        await interaction.followup.send("Please select a creator:", view=CreatorSelectView(), ephemeral=True)

# The Payment Modal now no longer includes a text field for the creator.
class PaymentModal(discord.ui.Modal, title="Submit a Payment"):
    def __init__(self, creator_name: str):
        super().__init__()
        self.creator_name = creator_name  # Set the selected creator name

    amount = discord.ui.TextInput(
        label="Amount",
        placeholder="Enter the payment amount (no dollar sign)",
        style=discord.TextStyle.short
    )
    payment_info = discord.ui.TextInput(
        label="Payment Info",
        placeholder="Enter payment method (e.g., PayPal, ACH) and details or type 'pdf'.",
        style=discord.TextStyle.long
    )
    note = discord.ui.TextInput(
        label="Note",
        placeholder="If you have a PDF bill, fill this out and then send the PDF.",
        style=discord.TextStyle.long,
        default="If you have a PDF bill, fill this out and then send the PDF.",
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        user_name = interaction.user.name
        submission_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response_text = (
            f"**Payment Data Submitted**\n\n"
            f"__*Creator Name:*__ {self.creator_name}\n"
            f"__*Amount:*__ ${self.amount.value}\n"
            f"__*Payment Info:*__ {self.payment_info.value}\n\n"
            f"*Submitted by:* {user_name}\n"
            f"*Submitted on:* {submission_timestamp}"
        )
        await interaction.response.send_message(response_text, ephemeral=False)

# Slash command version of pay: first, select a creator then fill in the rest.
@bot.tree.command(name="pay", description="Submit a Payment via an Interactive Form")
async def pay(interaction: discord.Interaction):
    # Show the creator selection view first.
    await interaction.response.send_message("Please select a creator:", view=CreatorSelectView(), ephemeral=True)

# ----------------- END OF PAYMENT SUBMISSION WITH DROPDOWN -----------------




# SCAN OVER BOT MESSAGES FILTERED BY USERNAME AND DATE (M/YY format)
@bot.command(name='audit', help='Scans payments by username and date (e.g., !scan Jacob 2/25 for Feb 2025)')
async def audit(ctx, discord_username: str, date_str: str):
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
    
    # Sum
    total_amount = 0.0

    async for msg in ctx.channel.history(limit=100000):  # NOTE: Increase limit if needed
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

        # Check that the message was submitted by the specified discord_username or do not continue if "all".
        if discord_username.lower() != "all" and (submitted_by is None or discord_username.lower() not in submitted_by.lower()):
            continue

        # Check that the submission date matches the requested month and year.
        if submitted_on is None or (submitted_on.month != month or submitted_on.year != year):
            continue

        # Update sum
        try:
            clean_amount = amount.replace("$", "").replace(",", "").strip()
            total_amount += float(clean_amount)
        except (TypeError, ValueError):
            pass


        # Build a summary line from the extracted fields.
        # For each matching message in your scan command:
        summary_line = f"**Creator:** {creator or 'N/A'} | **Amount:** {amount or 'N/A'} | **Date:** {submitted_on.strftime('%Y-%m-%d')}"
        summaries.append(summary_line)
        results.append(message_text)

    # Send a final summary message in chat.
    if summaries:
        if discord_username.lower() == "all":
            summary_text = f"✅ There are {len(summaries)} payment(s) for {month}/{year} | Total Amount: ${total_amount:.2f}:\n" + "\n".join(summaries)
        else:
            summary_text = f"✅ There are {len(summaries)} payment(s) from '{discord_username}' for {month}/{year} | Total Amount: ${total_amount:.2f}:\n" + "\n".join(summaries)

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
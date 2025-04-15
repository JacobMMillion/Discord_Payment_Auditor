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

# Load creator names from the creator_names table
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

    creators.sort()
    return creators

# Load app names from the app_names table
def load_apps():
    """
    Loads app names from the 'app_names' table.
    """
    conn = psycopg2.connect(CONN_STR)
    cursor = conn.cursor()

    query = "SELECT app_name FROM app_names;"
    cursor.execute(query)
    rows = cursor.fetchall()
    apps = [row[0] for row in rows]

    cursor.close()
    conn.close()
    return apps

# Save new creator names to the creator_names table
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

# Save a queued payment to the queued_payments table
def save_queued_payment(creator_name, app_name, discord_user, amount, payment_date):
    """
    Inserts a new queued payment record into the 'queued_payments' table.
    """
    conn = psycopg2.connect(CONN_STR)
    cursor = conn.cursor()
    query = """
    INSERT INTO queued_payments (creator_name, app_name, discord_user, amount, date)
    VALUES (%s, %s, %s, %s, %s);
    """
    cursor.execute(query, (creator_name, app_name, discord_user, amount, payment_date))
    conn.commit()
    cursor.close()
    conn.close()

# Global list for creator names, loaded from creator_names.
# Keep separate from simply getting usernames from queued_payments, as we may want to store payment info here
global_creators = load_creators()
global_apps = load_apps()

@bot.event
async def on_ready():
    # Sync slash commands with Discord so the new command is registered.
    await bot.tree.sync()
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='ping', help='Responds with a greeting')
async def hello(ctx):
    await ctx.send('Pong!')

# COMMANDS INFO
@bot.tree.command(name='commands', description='Displays available commands and how to use them.')
async def commands_info(interaction: discord.Interaction):
    response = (
        "**Available Commands:**\n\n"
        "➡️ `/users` — Lists all usernames in the server.\n\n"
        "➡️ `/pay` — Submit a payment via an interactive form.\n"
        "   _After selecting a creator (or adding one), select an app, then fill out Amount and Payment Info._\n\n"
        "➡️ `/audit` — Audit payments by username, app, and month/year.\n"
        "   _When you run `/audit`, you will be prompted to enter three pieces of information:_\n"
        "   • **Username:** Enter a Discord username or `all` for every user.\n"
        "   • **App:** Enter an app name or `all` for every app.\n"
        "   • **Date (M/YY):** Provide month and year in M/YY format (e.g., `4/2025`).\n\n"
        "   _Example:_ `/audit jacobm6039 Astra 4/2025` retrieves payments for user `jacobm6039` on `Astra` in April 2025.\n"
        "   _Example:_ `/audit all all 4/2025` retrieves all payments across every user and app in April 2025."
    )
    await interaction.response.send_message(response, ephemeral=True)

@bot.tree.command(name='users', description='Lists all usernames in the server.')
async def users(interaction: discord.Interaction):
    members = interaction.guild.members
    usernames = sorted(member.name for member in members)
    response = "**Users in this server:**\n" + "\n".join(usernames)
    await interaction.response.send_message(response, ephemeral=True)

# ----------------- PAYMENT SUBMISSION WITH DROPDOWN -----------------

# This view shows a dropdown to select a creator and a button to add a new creator.
class CreatorSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CreatorSelect())
    
    @discord.ui.button(label="Add New Creator", style=discord.ButtonStyle.primary, custom_id="add_creator")
    async def add_new_creator(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddCreatorModal())

# The dropdown select for creators, which leads to the app select, which should then lead to the payment view.
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
            # TODO: ? Launch the Payment Modal with the selected creator name.
            # first pick an app
            await interaction.response.send_message(
                "Now select an app for this payment:", 
                view=AppSelectView(chosen), 
                ephemeral=True
            )

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
            global_creators.append(new_name) # Append to local list
            global_creators.sort() # Sort new local list
            save_creators(global_creators)  # Persist the updated list to file.
            await interaction.response.send_message(f"Creator '{new_name}' added!", ephemeral=True)
        else:
            await interaction.response.send_message(f"Creator '{new_name}' already exists.", ephemeral=True)
        # Send back the creator selection view so the user can continue.
        await interaction.followup.send("Please select a creator:", view=CreatorSelectView(), ephemeral=True)

class AppSelect(discord.ui.Select):
    def __init__(self, creator_name):
        self.creator_name = creator_name
        options = [discord.SelectOption(label=a) for a in global_apps]
        super().__init__(placeholder="Select an app", min_values=1, max_values=1, options=options)

    async def callback(self, interaction, /):
        app = self.values[0]
        # now launch the payment modal with both creator & app
        await interaction.response.send_modal(PaymentModal(
            creator_name=self.creator_name,
            app_name=app
        ))

class AppSelectView(discord.ui.View):
    def __init__(self, creator_name):
        super().__init__(timeout=None)
        self.add_item(AppSelect(creator_name))

# The Payment Modal submits to the queued_payments table
class PaymentModal(discord.ui.Modal):
    def __init__(self, creator_name, app_name):
        super().__init__(title="Submit a Payment")
        self.creator_name = creator_name
        self.app_name = app_name

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
        submission_date = datetime.now().date()
        
        # Attempt to cast the amount to float (you might include additional validation here)
        try:
            payment_amount = float(self.amount.value)
        except ValueError:
            await interaction.response.send_message("Invalid payment amount.", ephemeral=True)
            return

        # Save the payment to the queued_payments table
        try:
            save_queued_payment(
            self.creator_name,   # creator_name
            self.app_name,       # app_name
            user_name,           # discord_user
            payment_amount,      # amount
            submission_date      # date
            )
        except Exception as e:
            await interaction.response.send_message(f"Failed to save payment: {e}", ephemeral=True)
            return

        response_text = (
            f"**Payment Request Submitted:**\n\n"
            f"__*Creator Name:*__ {self.creator_name}\n"
            f"__*Amount:*__ ${self.amount.value}\n"
            f"__*Payment Info:*__ {self.payment_info.value}\n\n"
            f"*App:* {self.app_name}\n"
            f"*Submitted by:* {user_name}\n"
            f"*Submitted on:* {submission_date}"
        )
        await interaction.response.send_message(response_text, ephemeral=False)

# Slash command version of pay: first, select a creator then fill in the rest.
@bot.tree.command(name="pay", description="Submit a Payment via an Interactive Form")
async def pay(interaction: discord.Interaction):
    # Show the creator selection view first.
    await interaction.response.send_message("Please select a creator:", view=CreatorSelectView(), ephemeral=True)

# ----------------- END OF PAYMENT SUBMISSION WITH DROPDOWN -----------------




# AUDIT queued_payments FILTERED BY USERNAME AND DATE (M/YY format)
@bot.tree.command(
    name='audit',
    description='Scans payments by username, app, and date (e.g., /audit <username|all> <app|all> <M/YY>)'
)
async def audit(
    interaction: discord.Interaction,
    discord_username: str,
    app_name: str,
    date_str: str
):
    # 1) Parse the date string in M/YY format
    try:
        parts = date_str.split('/')
        if len(parts) != 2:
            raise ValueError
        month = int(parts[0])
        year_suffix = int(parts[1])
        year = 2000 + year_suffix if year_suffix < 100 else year_suffix
    except Exception:
        await interaction.response.send_message(
            "❗ Usage: `/audit <username|all> <app|all> <M/YY>`\n"
            "Example: `/audit jacobm6039 Astra 4/2025` or `/audit all all 4/2025`",
            ephemeral=True
        )
        return

    # 2) Build the time window for that month
    from datetime import date
    try:
        start_date = date(year, month, 1)
        next_month = month % 12 + 1
        next_year = year + (1 if month == 12 else 0)
        next_month_date = date(next_year, next_month, 1)
    except ValueError as e:
        await interaction.response.send_message(f"Invalid date: {e}", ephemeral=True)
        return

    total_amount = 0.0
    summaries = []

    # 3) Query the DB with optional filters for user/app
    try:
        conn = psycopg2.connect(CONN_STR)
        cursor = conn.cursor()

        base_query = """
        SELECT creator_name, app_name, discord_user, amount, date
        FROM queued_payments
        WHERE date >= %s AND date < %s
        """
        params = [start_date, next_month_date]

        if discord_username.lower() != "all":
            base_query += " AND LOWER(discord_user) LIKE %s"
            params.append(f"%{discord_username.lower()}%")
        if app_name.lower() != "all":
            base_query += " AND LOWER(app_name) LIKE %s"
            params.append(f"%{app_name.lower()}%")

        cursor.execute(base_query + ";", tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        await interaction.response.send_message(f"Database error: {e}", ephemeral=True)
        return

    # 4) Build summaries
    for creator, app, user_found, amt, rec_date in rows:
        try:
            total_amount += float(amt)
        except:
            pass
        summaries.append(
            f"**Creator:** {creator} | **App:** {app} | "
            f"**Amount:** ${float(amt):.2f} | **Date:** {rec_date:%Y-%m-%d}"
        )

    # 5) Send back a single ephemeral message
    if summaries:
        header = f"✅ {len(summaries)} payment(s) for {month}/{year}"
        if discord_username.lower() != "all":
            header += f" from `{discord_username}`"
        if app_name.lower() != "all":
            header += f" on `{app_name}`"
        header += f" | Total: ${total_amount:.2f}\n"

        await interaction.response.send_message(header + "\n".join(summaries), ephemeral=True)
    else:
        await interaction.response.send_message(
            "📭 No payments found matching those filters.",
            ephemeral=True
        )






# MAIN
bot.run(TOKEN)
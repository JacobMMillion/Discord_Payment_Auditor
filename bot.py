import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
from dotenv import load_dotenv
from datetime import datetime, time
from zoneinfo import ZoneInfo
import psycopg2

load_dotenv()
TOKEN = os.getenv('TOKEN')
CONN_STR = os.getenv('DATABASE_URL')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Enables member caching
bot = commands.Bot(command_prefix='!', intents=intents)

# ----------------- PAYMENTS AND AUDITS -----------------

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

# Autocomplete for creator names
async def creator_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    # return up to 25 creators containing the current substring
    matches = [
        app_commands.Choice(name=name, value=name)
        for name in global_creators
        if current.lower() in name.lower()
    ][:25]
    return matches

# Autocomplete for app names
async def app_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    matches = [
        app_commands.Choice(name=a, value=a)
        for a in global_apps
        if current.lower() in a.lower()
    ][:25]
    return matches

@bot.event
async def on_ready():
    # Sync slash commands with Discord so the new command is registered.
    await bot.tree.sync()
    print(f'{bot.user} has connected to Discord!')

    # Added for budget messaging, should message at 6AM EST daily
    if not daily_balances.is_running():
        daily_balances.start()

@bot.command(name='ping', help='Responds with a greeting')
async def hello(ctx):
    await ctx.send('Pong!')

# COMMANDS INFO
@bot.tree.command(name='commands', description='Displays available commands and how to use them.')
async def commands_info(interaction: discord.Interaction):
    response = (
        "**Available Commands:**\n\n"
        "➡️ `/users` — Lists all usernames in the server.\n\n"
        "➡️ `/pay` — Submit a payment with autocomplete and auto‑add creators.\n"
        "   _Type to find or add a creator, select an app, then enter amount & payment info in the popup._\n\n"
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

# ----------------- PAYMENT SUBMISSION -----------------

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
        est = ZoneInfo("America/New_York")
        submission_dt = datetime.now(est)
        submission_date = submission_dt.date()
        
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

# Slash command version of pay: first, select a creator an app, using autocomplete and the ability to add new creators
# Then show the payment modal
@bot.tree.command(
    name="pay",
    description="Submit a payment"
)
@app_commands.describe(
    creator="Start typing a creator name…",
    app="Start typing an app name…"
)
@app_commands.autocomplete(
    creator=creator_autocomplete,
    app=app_autocomplete
)
async def pay(
    interaction: discord.Interaction,
    creator: str,
    app: str
):
    """Slash‑command: picks creator & app via autocomplete."""
    # auto‑add unknown creators only
    if creator not in global_creators:
        save_creators([creator])
        global_creators.append(creator)
        global_creators.sort()
        prefix = f"✅ Creator `{creator}` added!"
    else:
        prefix = None

    if prefix:
        # 1) Let the user know we added them
        await interaction.response.send_message(prefix, ephemeral=True)
        # 2) Then open the modal as a follow‑up
        await interaction.followup.send_modal(
            PaymentModal(creator_name=creator, app_name=app)
        )
    else:
        # No prefix → skip straight to the modal
        await interaction.response.send_modal(
            PaymentModal(creator_name=creator, app_name=app)
        )
# ----------------- END OF PAYMENT SUBMISSION -----------------




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
# ----------------- END PAYMENTS AND AUDITS -----------------




# ----------------- BUDGET MESSAGING (ip) -----------------
import json
import aiohttp

EASTERN = ZoneInfo("America/New_York")

# Pull in your TOKEN and CHANNEL_ID from env
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

def format_balances(data: dict) -> str:
    """Turn the JSON into a markdown string, including the account name."""
    lines = ["**Account Balances:**"]
    for acct in data["accounts"]:
        name  = acct.get("name", "Unknown")
        num   = acct["accountNumber"]
        avail = acct["availableBalance"]
        curr  = acct["currentBalance"]
        lines.append(f"- **{name}** (`{num}`): Available ${avail:,.2f}, Current ${curr:,.2f}")
    return "\n".join(lines)

async def fetch_accounts():
    # TODO: swap this stub for your real Mercury API call
    """
    # This will look something like this:

    # Pull your Mercury API token from env
    MERCURY_TOKEN = os.getenv("MERCURY_API_TOKEN")
    url = "https://api.mercury.com/api/v1/accounts"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {MERCURY_TOKEN}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()
    """

    # TESTING: stubbed Mercury API response
    response_json = """
    {
      "accounts": [
        {
          "accountNumber": "1984429715",
          "name": "Astra",
          "availableBalance": 93000,
          "currentBalance": 100000
        },
        {
          "accountNumber": "99265598157",
          "name": "Haven",
          "availableBalance": 78000,
          "currentBalance": 80000
        },
        {
          "accountNumber": "6429081385",
          "name": "Berry",
          "availableBalance": 70000,
          "currentBalance": 75000
        },
        {
          "accountNumber": "2263409985",
          "name": "Saga",
          "availableBalance": 25000,
          "currentBalance": 30000
        }
      ]
    }
    """
    return json.loads(response_json)

@bot.tree.command(name="budget", description="Show current account balances")
async def budget(interaction: discord.Interaction):
    data = await fetch_accounts()
    msg  = format_balances(data)
    await interaction.response.send_message(msg, ephemeral=True)

@tasks.loop(time=time(hour=6, minute=0, tzinfo=EASTERN))
async def daily_balances():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"❌ Could not find channel {CHANNEL_ID}")
        return

    data = await fetch_accounts()
    await channel.send(format_balances(data))

# ----------------- END BUDGET MESSAGING (ip) -----------------

# MAIN
bot.run(TOKEN)
import os
import json
import discord
from discord.ext import commands
from myserver import server_on

# ------------------------------
# Setup bot intents
# ------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------------
# File paths
# ------------------------------
USERS_FILE = "users.json"
WINNERS_FILE = "winners.json"
COUNTDOWNS_FILE = "countdowns.json"

DATA_FILES = [USERS_FILE, WINNERS_FILE, COUNTDOWNS_FILE]

# ------------------------------
# Create JSON files if missing
# ------------------------------
for file in DATA_FILES:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f, indent=4)
        print(f"Created {file}")

# ------------------------------
# Auto add role "Not Registered" to new members
# ------------------------------
@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name="Not Registered")
    if role:
        try:
            await member.add_roles(role)
            print(f"Assigned 'Not Registered' to {member}")
        except Exception as e:
            print(f"Failed to assign role: {e}")
    else:
        print("Role 'Not Registered' not found")

# ------------------------------
# Command: !reg [username]
# ------------------------------
@bot.command()
async def reg(ctx, username: str = None):

    # Delete the command message
    try:
        await ctx.message.delete()
    except:
        pass

    # If no username provided, stop
    if username is None:
        return

    # Load user data from JSON
    with open(USERS_FILE, "r") as f:
        data = json.load(f)

    user_id = str(ctx.author.id)
    old_name = data.get(user_id)  # Existing username (if any)

    lower_username = username.lower()  # Force lowercase
    existing_usernames_lower = {u.lower() for u in data.values()}  # All registered usernames

    # --------------------------------------------------------
    # Case 1: User has NO username yet AND chosen username is taken
    # --------------------------------------------------------
    if old_name is None and lower_username in existing_usernames_lower:
        await ctx.send(
            f":yellow_square: Username `{lower_username}` that {ctx.author.mention} "
            f"tried to register is already taken!"
        )
        return

    # --------------------------------------------------------
    # Case 2: User has NO username yet AND chosen username is available
    # This is a fresh registration
    # --------------------------------------------------------
    if old_name is None and lower_username not in existing_usernames_lower:
        data[user_id] = lower_username

        # Save updated data
        with open(USERS_FILE, "w") as f:
            json.dump(
                dict(sorted(data.items(), key=lambda x: x[1])),
                f,
                indent=4
            )

        # Role management: give 'Registered', remove 'Not Registered'
        reg_role = discord.utils.get(ctx.guild.roles, name="Registered")
        not_reg_role = discord.utils.get(ctx.guild.roles, name="Not Registered")

        try:
            if reg_role:
                await ctx.author.add_roles(reg_role)
            if not_reg_role and not_reg_role in ctx.author.roles:
                await ctx.author.remove_roles(not_reg_role)
        except:
            pass

        # Update nickname to the registered username
        try:
            await ctx.author.edit(nick=lower_username)
        except:
            pass

        # Success message
        await ctx.send(
            f":green_square: {ctx.author.mention} has registered with username: `{lower_username}`"
        )
        return

    # --------------------------------------------------------
    # Case 3: User ALREADY has a username AND chosen username is taken
    # Prevent username collision
    # --------------------------------------------------------
    if old_name is not None and lower_username in existing_usernames_lower and lower_username != old_name.lower():
        await ctx.send(
            f":yellow_square: Username `{lower_username}` that {ctx.author.mention} "
            f"tried to update to is already taken!"
        )
        return

    # --------------------------------------------------------
    # Case 4: User ALREADY has a username AND chosen username is available
    # This is a username update
    # --------------------------------------------------------
    if old_name is not None and lower_username not in existing_usernames_lower:
        data[user_id] = lower_username

        # Save updated data
        with open(USERS_FILE, "w") as f:
            json.dump(
                dict(sorted(data.items(), key=lambda x: x[1])),
                f,
                indent=4
            )

        # Ensure user has 'Registered' role
        reg_role = discord.utils.get(ctx.guild.roles, name="Registered")
        not_reg_role = discord.utils.get(ctx.guild.roles, name="Not Registered")

        try:
            if reg_role and reg_role not in ctx.author.roles:
                await ctx.author.add_roles(reg_role)
            if not_reg_role and not_reg_role in ctx.author.roles:
                await ctx.author.remove_roles(not_reg_role)
        except:
            pass

        # Update nickname to new username
        try:
            await ctx.author.edit(nick=lower_username)
        except:
            pass

        # Success message for update
        await ctx.send(
            f":green_square: {ctx.author.mention} updated their username "
            f"from `{old_name.lower()}` → `{lower_username}`"
        )

# --------------------------------------------------------
# Auto-register missing usernames + Auto-fix nickname
# --------------------------------------------------------
@bot.event
async def on_member_update(before, after):
    # Load users.json
    with open(USERS_FILE, "r") as f:
        data = json.load(f)

    user_id = str(after.id)

    # --------------------------------------------------------
    # Case A: User has the role "Registered" but NO username stored in users.json
    # Automatically register them using their current nickname (or username)
    # --------------------------------------------------------
    reg_role = discord.utils.get(after.guild.roles, name="Registered")

    if reg_role and reg_role in after.roles and user_id not in data:

        # Use nickname if available, otherwise fallback to discord username
        raw_name = after.nick if after.nick else after.name
        lower_name = raw_name.lower()

        # Save the new username to users.json
        data[user_id] = lower_name

        # Save sorted JSON (alphabetical ASCII order)
        with open(USERS_FILE, "w") as f:
            json.dump(
                dict(sorted(data.items(), key=lambda x: x[1])),
                f,
                indent=4
            )

        print(f"[AUTO-REGISTER] Added missing username for {after}: {lower_name}")

        # Update the member's nickname to match the stored username
        try:
            await after.edit(nick=lower_name)
        except Exception as e:
            print(f"[AUTO-REGISTER ERROR] Could not update nickname for {after}: {e}")

        return  # Stop here since we already handled this case

    # --------------------------------------------------------
    # If user is not registered in JSON → ignore any further checks
    # --------------------------------------------------------
    if user_id not in data:
        return

    username = data[user_id]  # stored lowercase username

    # Check if user has "Registered" role
    reg_role = discord.utils.get(after.guild.roles, name="Registered")
    if not reg_role:
        return  # role doesn't exist

    if reg_role not in after.roles:
        return  # user is not registered → ignore

    # If nickname is already correct → nothing to do
    if after.nick == username:
        return

    # --------------------------------------------------------
    # Auto-fix nickname if someone (mod or user) changes it
    # --------------------------------------------------------
    try:
        await after.edit(nick=username)
        print(f"[AUTO-NICK] Fixed nickname for {after} → {username}")
    except Exception as e:
        print(f"[AUTO-NICK ERROR] Could not update nickname for {after}: {e}")

# ------------------------------
# Bot Ready Event
# ------------------------------
@bot.event
async def on_ready():
    print(f"Bot is ready: {bot.user}")

# ------------------------------
# Run bot
# ------------------------------
server_on()

bot.run(os.getenv('TOKEN'))

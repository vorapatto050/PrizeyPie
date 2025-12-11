import os
import json
import discord
from discord.ext import commands
from datetime import datetime
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
# Send JSON files to #data-files
# ------------------------------
async def send_json_file(ctx, file_path, display_name):
    if not os.path.exists(file_path):
        return

    date_str = datetime.utcnow().strftime("%d-%m-%y")
    filename = f"{display_name}({date_str}).txt"

    channel = discord.utils.get(ctx.guild.text_channels, name="data-files")
    if not channel:
        return

    await channel.send(file=discord.File(file_path, filename=filename))

# ------------------------------
# Commands to send JSON files
# ------------------------------
@bot.command()
async def users(ctx):
    if ctx.author.id != ctx.guild.owner_id:
        return
    try:
        await ctx.message.delete()
    except:
        pass
    await send_json_file(ctx, USERS_FILE, "users")

@bot.command()
async def winners(ctx):
    if ctx.author.id != ctx.guild.owner_id:
        return
    try:
        await ctx.message.delete()
    except:
        pass
    await send_json_file(ctx, WINNERS_FILE, "winners")

@bot.command()
async def countdowns(ctx):
    if ctx.author.id != ctx.guild.owner_id:
        return
    try:
        await ctx.message.delete()
    except:
        pass
    await send_json_file(ctx, COUNTDOWNS_FILE, "countdowns")

# ------------------------------
# Auto add role "Not Registered"
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
# Remove user data on leave
# ------------------------------
@bot.event
async def on_member_remove(member):
    user_id = str(member.id)

    # Remove from users.json
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            data = json.load(f)

        if user_id in data:
            del data[user_id]
            with open(USERS_FILE, "w") as f:
                json.dump(data, f, indent=4)
            print(f"[REMOVE] Deleted {member} from users.json")

    # Remove from winners.json
    if os.path.exists(WINNERS_FILE):
        with open(WINNERS_FILE, "r") as f:
            winners_data = json.load(f)

        if user_id in winners_data:
            del winners_data[user_id]
            with open(WINNERS_FILE, "w") as f:
                json.dump(winners_data, f, indent=4)
            print(f"[REMOVE] Deleted {member} from winners.json")

# ------------------------------
# Command: !reg [username]
# ------------------------------
@bot.command()
async def reg(ctx, username: str = None):
    try:
        await ctx.message.delete()
    except:
        pass
    if username is None:
        return

    with open(USERS_FILE, "r") as f:
        data = json.load(f)

    user_id = str(ctx.author.id)
    old_name = data.get(user_id)
    lower_username = username.lower()
    existing_usernames_lower = {u.lower() for u in data.values()}

    # Case 1: New user, username taken
    if old_name is None and lower_username in existing_usernames_lower:
        await ctx.send(f":yellow_square: Username `{lower_username}` is already taken!")
        return

    # Case 2: New user, username available
    if old_name is None and lower_username not in existing_usernames_lower:
        data[user_id] = lower_username
        with open(USERS_FILE, "w") as f:
            json.dump(dict(sorted(data.items(), key=lambda x: x[1])), f, indent=4)

        reg_role = discord.utils.get(ctx.guild.roles, name="Registered")
        not_reg_role = discord.utils.get(ctx.guild.roles, name="Not Registered")
        try:
            if reg_role:
                await ctx.author.add_roles(reg_role)
            if not_reg_role and not_reg_role in ctx.author.roles:
                await ctx.author.remove_roles(not_reg_role)
        except:
            pass
        try:
            await ctx.author.edit(nick=lower_username)
        except:
            pass
        await ctx.send(f":green_square: {ctx.author.mention} has registered as `{lower_username}`")
        return

    # Case 3: Existing user, username taken by someone else
    if old_name is not None and lower_username in existing_usernames_lower and lower_username != old_name.lower():
        await ctx.send(f":yellow_square: Username `{lower_username}` is already taken!")
        return

    # Case 4: Existing user, username available → update
    if old_name is not None and lower_username not in existing_usernames_lower:
        data[user_id] = lower_username
        with open(USERS_FILE, "w") as f:
            json.dump(dict(sorted(data.items(), key=lambda x: x[1])), f, indent=4)

        reg_role = discord.utils.get(ctx.guild.roles, name="Registered")
        not_reg_role = discord.utils.get(ctx.guild.roles, name="Not Registered")
        try:
            if reg_role and reg_role not in ctx.author.roles:
                await ctx.author.add_roles(reg_role)
            if not_reg_role and not_reg_role in ctx.author.roles:
                await ctx.author.remove_roles(not_reg_role)
        except:
            pass
        try:
            await ctx.author.edit(nick=lower_username)
        except:
            pass
        await ctx.send(f":green_square: {ctx.author.mention} updated username `{old_name.lower()}` → `{lower_username}`")

# --------------------------------------------------------
# Bot Ready + Auto-register missing usernames
# --------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Bot is ready: {bot.user}")

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users_data = json.load(f)
    else:
        users_data = {}

    for guild in bot.guilds:
        reg_role = discord.utils.get(guild.roles, name="Registered")
        if not reg_role:
            continue

        for member in guild.members:
            if reg_role in member.roles:
                user_id = str(member.id)
                if user_id not in users_data:
                    raw_name = member.nick if member.nick else member.name
                    lower_name = raw_name.lower()
                    users_data[user_id] = lower_name
                    try:
                        await member.edit(nick=lower_name)
                    except Exception as e:
                        print(f"[AUTO-REGISTER ERROR] Could not update nickname for {member}: {e}")
                    print(f"[AUTO-REGISTER STARTUP] Added missing username for {member}: {lower_name}")

    with open(USERS_FILE, "w") as f:
        json.dump(dict(sorted(users_data.items(), key=lambda x: x[1])), f, indent=4)

# --------------------------------------------------------
# Auto-fix nickname
# --------------------------------------------------------
@bot.event
async def on_member_update(before, after):
    with open(USERS_FILE, "r") as f:
        data = json.load(f)

    user_id = str(after.id)
    if user_id not in data:
        return

    username = data[user_id]
    reg_role = discord.utils.get(after.guild.roles, name="Registered")
    if not reg_role or reg_role not in after.roles:
        return

    if after.nick != username:
        try:
            await after.edit(nick=username)
            print(f"[AUTO-NICK] Fixed nickname for {after} → {username}")
        except Exception as e:
            print(f"[AUTO-NICK ERROR] Could not update nickname for {after}: {e}")

# ------------------------------
# Run bot
# ------------------------------
server_on()
bot.run(os.getenv('TOKEN'))

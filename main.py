import os
import json
import random
import asyncio
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

DATA_FILES = [USERS_FILE, WINNERS_FILE]

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

# -------------------------
# Utility: load users
# -------------------------
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

# -------------------------
# Utility: save winners
# -------------------------
def save_winners(winner_data):
    if os.path.exists(WINNERS_FILE):
        with open(WINNERS_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}
    data.update(winner_data)
    with open(WINNERS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# -------------------------
# Countdown task
# -------------------------
async def countdown_task(title, amount, key, timestamp, channel_id, save_message_id):
    channel = bot.get_channel(channel_id)
    if not channel:
        return

    while True:
        now = datetime.utcnow().timestamp()
        remaining = int(timestamp - now)
        if remaining <= 0:
            break
        # Sleep logic
        if remaining <= 5:
            await asyncio.sleep(0.1)
        else:
            await asyncio.sleep(5)

    # Time's up → pick winners
    users_data = load_users()
    registered_ids = list(users_data.keys())
    if len(registered_ids) < amount:
        winners = registered_ids
    else:
        winners = random.sample(registered_ids, amount)

    winner_mentions = [f"<@{uid}>" for uid in winners]
    # Send winner message
    msg = f"**{title}**\n\nRandomly selected users 🎉\n\n" + "\n".join(winner_mentions)
    await channel.send(msg)

    # Save to winners.json
    winner_dict = {uid: title for uid in winners}
    save_winners(winner_dict)

    # Delete countdown save message
    save_channel = discord.utils.get(channel.guild.text_channels, name="countdown-saves")
    if save_channel:
        try:
            msg = await save_channel.fetch_message(save_message_id)
            await msg.delete()
        except:
            pass

# -------------------------
# Command: !random
# -------------------------
@bot.command()
async def random(ctx, title: str, amount: int, date: str, time: str):
    # Convert title (- to space)
    title_clean = title.replace("-", " ")

    # Parse datetime DD/MM/YY HH:MM
    dt_str = f"{date} {time}"
    dt = datetime.strptime(dt_str, "%d/%m/%y %H:%M")
    timestamp = dt.timestamp()  # UTC 0 assumed

    # Generate random key
    key = "".join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=6))

    # Send countdown message
    countdown_msg = await ctx.send(f"@everyone\n\n**{title_clean}**\n\nCountdown: <t:{int(timestamp)}:R>\n\n{key}")

    # Save countdown info in #countdown-saves
    save_channel = discord.utils.get(ctx.guild.text_channels, name="countdown-saves")
    if save_channel:
        save_content = f"TITLE:{title_clean}\nAMOUNT:{amount}\nKEY:{key}\nTIMESTAMP:{int(timestamp)}\nORIGINAL_CHANNEL:{ctx.channel.id}\nMSG_ID:{countdown_msg.id}"
        save_msg = await save_channel.send(save_content)
        save_message_id = save_msg.id
    else:
        save_message_id = None

    # Start countdown task
    asyncio.create_task(countdown_task(title_clean, amount, key, timestamp, ctx.channel.id, save_message_id))

# -------------------------
# Recovery on bot start
# -------------------------
@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user}")
    await asyncio.sleep(2)  # Wait for guilds to load

    for guild in bot.guilds:
        save_channel = discord.utils.get(guild.text_channels, name="countdown-saves")
        if not save_channel:
            continue
        async for msg in save_channel.history(limit=100):
            try:
                lines = msg.content.split("\n")
                data = {line.split(":", 1)[0]: line.split(":", 1)[1] for line in lines}
                title = data["TITLE"]
                amount = int(data["AMOUNT"])
                key = data["KEY"]
                timestamp = int(data["TIMESTAMP"])
                channel_id = int(data["ORIGINAL_CHANNEL"])
                save_message_id = int(data["MSG_ID"])

                now = datetime.utcnow().timestamp()
                if timestamp <= now:
                    # Time passed → execute immediately
                    asyncio.create_task(countdown_task(title, amount, key, timestamp, channel_id, save_message_id))
                else:
                    # Time remaining → continue countdown
                    asyncio.create_task(countdown_task(title, amount, key, timestamp, channel_id, save_message_id))
            except Exception as e:
                print(f"[RECOVERY ERROR] {e}")

# ------------------------------
# Run bot
# ------------------------------
server_on()
bot.run(os.getenv('TOKEN'))

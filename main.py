import os
import json
import discord
from discord.ext import commands
from datetime import datetime, timezone
from myserver import server_on
import asyncio
import random


active_countdowns = {} 

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
# Countdown system (random)
# ------------------------------
# Helper: log winners
def log_winners(winners, title, data):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    if os.path.exists(WINNERS_FILE):
        with open(WINNERS_FILE, "r") as f:
            winners_data = json.load(f)
    else:
        winners_data = {}

    for w in winners:
        user_id = str(w.id)
        if user_id not in winners_data:
            winners_data[user_id] = []

        winners_data[user_id].append({
            "username": data[user_id],
            "title": title,
            "timestamp": timestamp
        })

    with open(WINNERS_FILE, "w") as f:
        json.dump(winners_data, f, indent=4)

# Generate random 6-letter key
def generate_key():
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=6))

# Countdown task
async def countdown_task(guild, channel_id, countdown_message_id, key, title, amount, timestamp):
    # Loop sleep ย่อย
    while True:
        remaining = timestamp - datetime.utcnow().timestamp()
        if remaining <= 0:
            break
        elif remaining < 5:  # เหลือไม่กี่วิ → sleep สั้น ๆ
            await asyncio.sleep(0.1)
        else:                # เหลือหลายวิ → sleep 1 วินาที
            await asyncio.sleep(1)

    # ทำงานต่อหลัง countdown หมด
    channel = bot.get_channel(channel_id)
    if not channel:
        return

    # Delete countdown message
    try:
        msg = await channel.fetch_message(countdown_message_id)
        await msg.delete()
    except:
        pass

    # Get registered members
    role = discord.utils.get(guild.roles, name="Registered")
    if not role:
        return

    with open(USERS_FILE, "r") as f:
        data = json.load(f)

    eligible_members = [m for m in guild.members if role in m.roles and str(m.id) in data]
    if not eligible_members:
        return

    amount = min(amount, len(eligible_members))
    winners = random.sample(eligible_members, amount)

    # Send winners message
    winner_msg = f"**{title}**\n\nRandomly selected users🎉\n\n"
    for w in winners:
        winner_msg += f"{w.mention}\n"
    await channel.send(winner_msg)

    # Log winners
    log_winners(winners, title, data)

    # Delete key message in #key-saves
    key_saves_channel = discord.utils.get(guild.text_channels, name="key-saves")
    if key_saves_channel:
        async for m in key_saves_channel.history(limit=200):
            if key in m.content:
                try:
                    await m.delete()
                except:
                    pass

    # Remove from active tasks
    if key in active_countdowns:
        del active_countdowns[key]

# Command: !random
@bot.command()
async def random(ctx, *, args: str = None):
    if ctx.author.id != ctx.guild.owner_id:
        return
    try:
        await ctx.message.delete()
    except:
        pass
    if not args:
        return

    parts = args.split()
    # Determine if date/time is provided
    if len(parts) >= 4 and "/" in parts[-2] and ":" in parts[-1]:
        # Scheduled random
        try:
            day, month, year = map(int, parts[-2].split("/"))
            hour, minute = map(int, parts[-1].split(":"))
            target_time = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
            amount = int(parts[-3])
            title_raw = " ".join(parts[:-3])
        except:
            return
    else:
        # Immediate random
        try:
            amount = int(parts[-1])
            title_raw = " ".join(parts[:-1])
            target_time = datetime.utcnow()
        except:
            return

    title = title_raw.replace("-", " ")
    role = discord.utils.get(ctx.guild.roles, name="Registered")
    if not role:
        return

    with open(USERS_FILE, "r") as f:
        data = json.load(f)

    eligible_members = [m for m in ctx.guild.members if role in m.roles and str(m.id) in data]
    if not eligible_members:
        return

    amount = min(amount, len(eligible_members))
    key = generate_key()

    countdown_channel = ctx.channel
    key_saves_channel = discord.utils.get(ctx.guild.text_channels, name="key-saves")
    if not key_saves_channel:
        return

    # Send countdown message
    countdown_msg = await countdown_channel.send(
        f"@everyone\n\n**{title}**\n\nCountdown: <t:{int(target_time.timestamp())}:R>\n\n{key}\n."
    )

    # Save key info in #key-saves
    await key_saves_channel.send(
        f"{key}\nTitle: {title}\nAmount: {amount}\nTimestamp: {int(target_time.timestamp())}\nCountdown Msg ID: {countdown_msg.id}\n."
    )

    # Start countdown task
    task = asyncio.create_task(
        countdown_task(ctx.guild, countdown_channel.id, countdown_msg.id, key, title, amount, target_time.timestamp())
    )
    active_countdowns[key] = task

# Restore countdowns on bot start
async def restore_countdowns():
    for guild in bot.guilds:
        key_saves_channel = discord.utils.get(guild.text_channels, name="key-saves")
        if not key_saves_channel:
            continue
        async for m in key_saves_channel.history(limit=200):
            lines = m.content.splitlines()
            if len(lines) < 5:
                continue
            key = lines[0]
            try:
                title_line = lines[1]
                amount_line = lines[2]
                timestamp_line = lines[3]
                countdown_msg_id_line = lines[4]
                title = title_line.split("Title: ")[1]
                amount = int(amount_line.split("Amount: ")[1])
                timestamp = int(timestamp_line.split("Timestamp: ")[1])
                countdown_msg_id = int(countdown_msg_id_line.split("Countdown Msg ID: ")[1])
            except:
                continue
            # Restore task
            task = asyncio.create_task(
                countdown_task(guild, m.channel.id, countdown_msg_id, key, title, amount, timestamp)
            )
            active_countdowns[key] = task

# ------------------------------
# Run bot
# ------------------------------
server_on()
bot.run(os.getenv('TOKEN'))

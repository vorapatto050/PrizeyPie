import os
import json
import discord
import asyncio
import random
from discord.ext import commands
from datetime import datetime, timezone
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
# File paths & constants
# ------------------------------
USERS_FILE = "users.json"
COUNTDOWN_CHANNEL_NAME = "countdown-saves"
ACTIVE_COUNTDOWNS = {}

# ------------------------------
# Helper functions
# ------------------------------
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(dict(sorted(data.items(), key=lambda x: x[1])), f, indent=4)

def parse_datetime_to_timestamp(date_str, time_str):
    dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

async def delete_message_silently(msg):
    try:
        await msg.delete()
    except:
        pass

async def assign_roles(member, add_roles=[], remove_roles=[]):
    try:
        for role in add_roles:
            if role and role not in member.roles:
                await member.add_roles(role)
        for role in remove_roles:
            if role and role in member.roles:
                await member.remove_roles(role)
    except:
        pass

async def edit_nick_silently(member, nick):
    try:
        await member.edit(nick=nick)
    except:
        pass

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
# File init
# ------------------------------
if not os.path.exists(USERS_FILE):
    save_users({})
    print(f"Created {USERS_FILE}")

# ------------------------------
# Role management & auto-nick
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

@bot.event
async def on_member_update(before, after):
    users_data = load_users()
    user_id = str(after.id)
    if user_id in users_data:
        username = users_data[user_id]
        reg_role = discord.utils.get(after.guild.roles, name="Registered")
        if reg_role and reg_role in after.roles and after.nick != username:
            await edit_nick_silently(after, username)
            print(f"[AUTO-NICK] Fixed nickname for {after} → {username}")

@bot.event
async def on_member_remove(member):
    user_id = str(member.id)
    users_data = load_users()
    if user_id in users_data:
        users_data.pop(user_id)
        save_users(users_data)
        print(f"[REMOVE] Deleted {member} from users.json")

# ------------------------------
# Commands: users, clear
# ------------------------------
@bot.command()
async def users(ctx):
    if ctx.author.id != ctx.guild.owner_id:
        return
    await delete_message_silently(ctx.message)
    await send_json_file(ctx, USERS_FILE, "users")

@bot.command()
async def clear(ctx):
    if ctx.author.id != ctx.guild.owner_id:
        return
    try:
        await ctx.channel.purge(limit=None)
    except:
        pass

# ------------------------------
# Registration command
# ------------------------------
@bot.command()
async def reg(ctx, username: str = None):
    await delete_message_silently(ctx.message)
    if not username:
        return

    users_data = load_users()
    user_id = str(ctx.author.id)
    old_name = users_data.get(user_id)
    lower_username = username.lower()
    existing_usernames_lower = {u.lower() for u in users_data.values()}

    # Case logic
    if old_name is None and lower_username in existing_usernames_lower:
        await ctx.send(f":yellow_square: Username `{lower_username}` is already taken!")
        return

    if old_name is None or (old_name and lower_username not in existing_usernames_lower):
        users_data[user_id] = lower_username
        save_users(users_data)
        reg_role = discord.utils.get(ctx.guild.roles, name="Registered")
        not_reg_role = discord.utils.get(ctx.guild.roles, name="Not Registered")
        await assign_roles(ctx.author, add_roles=[reg_role], remove_roles=[not_reg_role])
        await edit_nick_silently(ctx.author, lower_username)
        if old_name:
            await ctx.send(f":green_square: {ctx.author.mention} updated username `{old_name.lower()}` → `{lower_username}`")
        else:
            await ctx.send(f":green_square: {ctx.author.mention} has registered as `{lower_username}`")
        return

    if old_name and lower_username in existing_usernames_lower and lower_username != old_name.lower():
        await ctx.send(f":yellow_square: Username `{lower_username}` is already taken!")

# ------------------------------
# Countdown logic
# ------------------------------
async def countdown_task(message, title, amount, timestamp):
    while True:
        remaining = timestamp - int(datetime.utcnow().timestamp())
        if remaining <= 0:
            try:
                await message.delete()
            except:
                pass

            users_data = load_users()
            guild = message.guild
            registered_members = [guild.get_member(int(uid)) for uid in users_data if guild.get_member(int(uid)) and not guild.get_member(int(uid)).bot]
            if not registered_members:
                await message.channel.send(f"**{title}**\n\nไม่มีผู้ลงทะเบียนให้สุ่ม 🎉")
                ACTIVE_COUNTDOWNS.pop(message.id, None)
                break

            winners = random.sample(registered_members, min(amount, len(registered_members)))
            winner_mentions = "\n".join([u.mention for u in winners])
            await message.channel.send(f"**{title}**\n\nRandomly selected registered users 🎉\n\n{winner_mentions}")
            ACTIVE_COUNTDOWNS.pop(message.id, None)
            break

        await asyncio.sleep(1 if remaining <= 5 else 5)

# ------------------------------
# Randomize command
# ------------------------------
@bot.command
async def random(ctx, title: str = None, amount: int = None, date: str = None, time: str = None):
    await delete_message_silently(ctx.message)
    if not all([title, amount, date, time]):
        return

    try:
        timestamp = parse_datetime_to_timestamp(date, time)
    except:
        return

    title_display = title.replace("-", " ")
    countdown_channel = discord.utils.get(ctx.guild.text_channels, name=COUNTDOWN_CHANNEL_NAME)
    if not countdown_channel:
        return

    countdown_msg = await ctx.send(f"@everyone\n\n**{title_display}**\n\nCountdown: <t:{timestamp}:R>")
    await countdown_channel.send(f"{countdown_msg.id}|{countdown_msg.channel.id}|{title_display}|{amount}|{timestamp}")
    ACTIVE_COUNTDOWNS[countdown_msg.id] = {"title": title_display, "amount": amount, "timestamp": timestamp, "message": countdown_msg}
    bot.loop.create_task(countdown_task(countdown_msg, title_display, amount, timestamp))

# ------------------------------
# Message management
# ------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content_lower = message.content.lower()
    allowed_owner_cmds = ["!reg", "!clear", "!randomize", "!users"]

    if message.author.id != message.guild.owner_id:
        if not content_lower.startswith("!reg"):
            await delete_message_silently(message)
    else:
        if content_lower.startswith("!") and not any(content_lower.startswith(cmd) for cmd in allowed_owner_cmds):
            await delete_message_silently(message)

    await bot.process_commands(message)

# ------------------------------
# Command error handling
# ------------------------------
@bot.event
async def on_command_error(ctx, error):
    await delete_message_silently(ctx.message)
    print(f"[COMMAND ERROR] {ctx.author} | {ctx.command} | {error}")

# ------------------------------
# Bot startup
# ------------------------------
@bot.event
async def on_ready():
    print(f"Bot is ready: {bot.user}")

    # Auto-register missing usernames
    users_data = load_users()
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
                    await edit_nick_silently(member, lower_name)
                    print(f"[AUTO-REGISTER STARTUP] Added missing username for {member}: {lower_name}")
    save_users(users_data)

    # Recover countdowns
    for guild in bot.guilds:
        countdown_channel = discord.utils.get(guild.text_channels, name=COUNTDOWN_CHANNEL_NAME)
        if not countdown_channel:
            continue

        async for msg in countdown_channel.history(limit=100):
            try:
                msg_id, countdown_channel_id, title, amount, timestamp = msg.content.split("|")
                msg_id, countdown_channel_id, amount, timestamp = int(msg_id), int(countdown_channel_id), int(amount), int(timestamp)
            except Exception as e:
                print(f"[RECOVER ERROR] Invalid save format: {msg.content} | {e}")
                continue

            if timestamp <= int(datetime.utcnow().timestamp()):
                await delete_message_silently(msg)
                continue

            try:
                real_channel = msg.guild.get_channel(countdown_channel_id)
                if not real_channel:
                    continue
                countdown_msg = await real_channel.fetch_message(msg_id)
            except Exception as e:
                print(f"[RECOVER ERROR] Could not fetch countdown message {msg_id}: {e}")
                continue

            ACTIVE_COUNTDOWNS[msg_id] = {"title": title, "amount": amount, "timestamp": timestamp, "message": countdown_msg}
            print(f"[RECOVER] Resumed countdown {title} ({msg_id})")
            bot.loop.create_task(countdown_task(countdown_msg, title, amount, timestamp))

# ------------------------------
# Run bot
# ------------------------------
server_on()
bot.run(os.getenv("TOKEN"))

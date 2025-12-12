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
# File paths
# ------------------------------
USERS_FILE = "users.json"

COUNTDOWN_CHANNEL_NAME = "countdown-saves"
ACTIVE_COUNTDOWNS = {}

# ------------------------------
# Create JSON file if missing
# ------------------------------
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f, indent=4)
    print(f"Created {USERS_FILE}")

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
# Command to send users.json
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

@bot.event
async def on_ready():
    print(f"Bot is ready: {bot.user}")

    # ------------------------
    # Auto-register missing usernames
    # ------------------------
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

    # ------------------------
    # Recover countdowns
    # ------------------------
    for guild in bot.guilds:
        countdown_channel = discord.utils.get(guild.text_channels, name=COUNTDOWN_CHANNEL_NAME)
        if not countdown_channel:
            continue

        async for msg in countdown_channel.history(limit=100):
            # 1. parse ข้อมูล save
            try:
                msg_id, countdown_channel_id, title, amount, timestamp = msg.content.split("|")
                msg_id = int(msg_id)
                countdown_channel_id = int(countdown_channel_id)
                amount = int(amount)
                timestamp = int(timestamp)
            except Exception as e:
                print(f"[RECOVER ERROR] Invalid save format: {msg.content} | {e}")
                continue

            # 2. เช็ก expired
            if timestamp <= int(datetime.utcnow().timestamp()):
                try:
                    await msg.delete()
                    print(f"[RECOVER] Countdown {title} expired, deleted save message")
                except:
                    pass
                continue

            # 3. fetch message จาก channel จริง
            try:
                real_channel = msg.guild.get_channel(countdown_channel_id)
                if real_channel is None:
                    print(f"[RECOVER ERROR] Channel {countdown_channel_id} not found")
                    continue
                countdown_msg = await real_channel.fetch_message(msg_id)
            except Exception as e:
                print(f"[RECOVER ERROR] Could not fetch countdown message {msg_id}: {e}")
                continue

            # 4. สร้าง task
            ACTIVE_COUNTDOWNS[msg_id] = {
                "title": title,
                "amount": amount,
                "timestamp": timestamp,
                "message": countdown_msg
            }
            print(f"[RECOVER] Resumed countdown {title} ({msg_id})")
            bot.loop.create_task(countdown_task(countdown_msg, title, amount, timestamp))


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

# --------------------------
# Helper: convert DD/MM/YY HH:MM to timestamp UTC
# --------------------------
def parse_datetime_to_timestamp(date_str, time_str):
    dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

# --------------------------
# Countdown task (เฉพาะผู้ลงทะเบียน)
# --------------------------
async def countdown_task(message, title, amount, timestamp):
    while True:
        now = int(datetime.utcnow().timestamp())
        remaining = timestamp - now
        if remaining <= 0:
            try:
                await message.delete()
            except:
                pass

            # โหลดข้อมูล users.json
            if os.path.exists(USERS_FILE):
                with open(USERS_FILE, "r") as f:
                    users_data = json.load(f)
            else:
                users_data = {}

            # เลือกเฉพาะสมาชิกที่ยังอยู่ในกิลด์และลงทะเบียน
            guild = message.guild
            registered_members = []
            for user_id_str, username in users_data.items():
                member = guild.get_member(int(user_id_str))
                if member and not member.bot:
                    registered_members.append(member)

            if not registered_members:
                await message.channel.send(f"**{title}**\n\nไม่มีผู้ลงทะเบียนให้สุ่ม 🎉")
                ACTIVE_COUNTDOWNS.pop(message.id, None)
                break

            winners = random.sample(registered_members, min(amount, len(registered_members)))

            winner_mentions = "\n".join([u.mention for u in winners])
            await message.channel.send(
                f"**{title}**\n\nRandomly selected registered users 🎉\n\n{winner_mentions}"
            )

            ACTIVE_COUNTDOWNS.pop(message.id, None)
            break

        # Dynamic sleep
        await asyncio.sleep(1 if remaining <= 5 else 5)

# --------------------------
# Command: !random
# --------------------------
@bot.command()
async def randomize(ctx, title: str = None, amount: int = None, date: str = None, time: str = None):
    # ลบข้อความผู้ใช้ทันที
    try:
        await ctx.message.delete()
    except:
        pass

    # ตรวจสอบ argument, ถ้าไม่ครบหรือผิด ก็ return เงียบ ๆ
    if not all([title, amount, date, time]):
        return

    try:
        timestamp = parse_datetime_to_timestamp(date, time)
    except:
        return  # เงียบ ๆ ไม่ส่ง error

    title_display = title.replace("-", " ")

    try:
        countdown_channel = discord.utils.get(ctx.guild.text_channels, name=COUNTDOWN_CHANNEL_NAME)
        if not countdown_channel:
            return

        countdown_msg = await ctx.send(
            f"@everyone\n\n**{title_display}**\n\nCountdown: <t:{timestamp}:R>"
        )

        # Save to #countdown-saves

        await countdown_channel.send(
            f"{countdown_msg.id}|{countdown_msg.channel.id}|{title_display}|{amount}|{timestamp}"
        )

        # Store in memory
        ACTIVE_COUNTDOWNS[countdown_msg.id] = {
            "title": title_display,
            "amount": amount,
            "timestamp": timestamp,
            "message": countdown_msg
        }

        # Start countdown
        bot.loop.create_task(countdown_task(countdown_msg, title_display, amount, timestamp))

    except:
        return  # ทุก error เงียบ ๆ

# --------------------------
# Command: !clear
# --------------------------
@bot.command()
async def clear(ctx):
    # เช็กว่าเป็น owner ของ guild
    if ctx.author.id != ctx.guild.owner_id:
        return  # เงียบ ๆ ไม่อนุญาต

    # ลบข้อความทั้งหมดใน channel ปัจจุบัน
    try:
        await ctx.channel.purge(limit=None)
    except:
        pass  # เงียบ ๆ ถ้ามี error

# --------------------------
# Auto delete
# --------------------------
@bot.event
async def on_message(message):
    # อย่าลบข้อความ bot เอง
    if message.author.bot:
        return

    content_lower = message.content.lower()

    # -------------------------
    # กรณี 1: สมาชิกทั่วไป
    # ลบข้อความทั้งหมด นอกจาก !reg
    # -------------------------
    if message.author.id != message.guild.owner_id:
        if not content_lower.startswith("!reg"):
            try:
                await message.delete()
            except:
                pass

    # -------------------------
    # กรณี 2: Owner
    # ลบข้อความที่ขึ้นต้นด้วย ! ยกเว้น !reg !clear !randomize !users
    # -------------------------
    else:  # owner
        if content_lower.startswith("!"):
            allowed = ["!reg", "!clear", "!randomize", "!users"]
            if not any(content_lower.startswith(cmd) for cmd in allowed):
                try:
                    await message.delete()
                except:
                    pass

    # ต้องเพิ่มบรรทัดนี้เสมอ เพื่อให้ command ทำงาน
    await bot.process_commands(message)

# -------------------------
# จับ error ของ command
# -------------------------
@bot.event
async def on_command_error(ctx, error):
    # ลบข้อความคำสั่งของผู้ใช้ถ้าเกิด error
    try:
        await ctx.message.delete()
    except:
        pass
    # สามารถ print log หรือ ignore ข้อความ error ได้
    print(f"[COMMAND ERROR] {ctx.author} | {ctx.command} | {error}")

# ------------------------------
# Run bot
# ------------------------------
server_on()
bot.run(os.getenv('TOKEN'))

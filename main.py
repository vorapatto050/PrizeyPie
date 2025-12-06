import os
import discord
from discord.ext import commands
import json
import os
import random
import asyncio
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

DATA_FILE = "users.json"
WINNERS_FILE = "winners.json"




# ------------------------------
# Create data files if not exists
# ------------------------------
for file in [DATA_FILE, WINNERS_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)



# ------------------------------
# Bot ready event
# ------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")



# ------------------------------
# Assign "Not Registered" role to new members
# ------------------------------
@bot.event
async def on_member_join(member):
    role_name = "Not Registered"
    role = discord.utils.get(member.guild.roles, name=role_name)
    if role:
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"Error assigning role: {e}")



# ------------------------------
# Remove username from database if user leaves
# ------------------------------
@bot.event
async def on_member_remove(member):
    user_id = str(member.id)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        if user_id in data:
            del data[user_id]
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"Username for {member.name} ({member.id}) is now available.")



# ------------------------------
# Remove winnerlogs from database if user leaves
# ------------------------------
@bot.event
async def on_member_remove(member):
    user_id = str(member.id)

    # ------------------ ลบจาก users.json ------------------
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        if user_id in data:
            del data[user_id]
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"Username for {member.name} ({member.id}) is now available.")

    # ------------------ ลบจาก winners.json ------------------
    if os.path.exists(WINNERS_FILE):
        with open(WINNERS_FILE, "r") as f:
            winners_data = json.load(f)
        if user_id in winners_data:
            del winners_data[user_id]
            with open(WINNERS_FILE, "w") as f:
                json.dump(winners_data, f, ensure_ascii=False, indent=4)
            print(f"Removed {member.name} ({member.id}) from winners.json")



# ------------------------------
# Register command (everyone can use)
# ------------------------------
@bot.command()
async def register(ctx, username: str = None):

    # Delete before sending
    try:
        await ctx.message.delete()
    except:
        pass

    if username is None:
        return

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    user_id = str(ctx.author.id)
    old_name = data.get(user_id)

    lower_username = username.lower()
    lower_existing_usernames = {name.lower() for name in data.values()}

    if lower_username in lower_existing_usernames and (old_name is None or old_name.lower() != lower_username):
        if old_name is None:
            await ctx.send(
                f":yellow_square: Username `{lower_username}` that {ctx.author.mention} tried to register is already taken!")
        else:
            await ctx.send(
                f":yellow_square: Username `{lower_username}` that {ctx.author.mention} tried to update to is already taken!")
        return

    data[user_id] = lower_username

    # Sort usernames alphabetically (ASCII)
    data = dict(sorted(data.items(), key=lambda item: item[1]))

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    registered_role = discord.utils.get(ctx.guild.roles, name="Registered")
    not_registered_role = discord.utils.get(ctx.guild.roles, name="Not Registered")

    if registered_role:
        try:
            await ctx.author.add_roles(registered_role)
            if not_registered_role and not_registered_role in ctx.author.roles:
                await ctx.author.remove_roles(not_registered_role)
        except:
            pass

        try:
            await ctx.author.edit(nick=lower_username)
        except:
            pass

    if old_name:
        await ctx.send(f":green_square: {ctx.author.mention} updated their username from `{old_name.lower()}` → `{lower_username}`")
    else:
        await ctx.send(f":green_square: {ctx.author.mention} has registered with username: `{lower_username}`")



# ------------------------------
# Enforce nickname matches username
# ------------------------------
@bot.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        user_id = str(after.id)
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        if user_id in data:
            lower_username = data[user_id].lower()
            if after.nick != lower_username:
                try:
                    await after.edit(nick=lower_username)
                except:
                    pass



# ------------------------------
# Helper function: log winners
# ------------------------------
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
        json.dump(winners_data, f, ensure_ascii=False, indent=4)



# ------------------------------
# randomuser (owner only)
# ------------------------------
@bot.command()
async def randomuser(ctx, *, args: str = None):

    # Owner only
    if ctx.author.id != ctx.guild.owner_id:
        return

    # Delete before sending
    try:
        await ctx.message.delete()
    except:
        pass

    if args is None:
        return

    parts = args.split()
    if parts[-1].isdigit():
        amount = int(parts[-1])
        title_raw = " ".join(parts[:-1])
    else:
        amount = 1
        title_raw = args

    title = title_raw.replace("-", " ")

    role = discord.utils.get(ctx.guild.roles, name="Registered")
    if not role:
        return

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    eligible_members = [m for m in ctx.guild.members if role in m.roles and str(m.id) in data]
    if not eligible_members:
        return

    amount = min(amount, len(eligible_members))
    winners = random.sample(eligible_members, amount)

    msg = f"**{title}**\n\nRandomly selected users 🎉\n\n"
    for w in winners:
        msg += f"{w.mention}\n\n"
    msg += "."

    await ctx.send(msg)
    log_winners(winners, title, data)



# ------------------------------
# randomusercount (owner only) - ใช้ Discord Timestamp
# ------------------------------
# สร้าง dictionary เก็บ countdown message และ task
@bot.command()
async def randomusercount(ctx, *, args: str = None):
    # Owner only
    if ctx.author.id != ctx.guild.owner_id:
        return

    # Delete command
    try:
        await ctx.message.delete()
    except:
        pass

    if args is None:
        return

    parts = args.split()
    if len(parts) < 4:
        return

    amount_str = parts[-3]
    if not amount_str.isdigit():
        return
    amount = int(amount_str)

    datetime_str = f"{parts[-2]} {parts[-1]}"
    try:
        target_time = datetime.strptime(datetime_str, "%d-%m-%Y %H:%M")
    except ValueError:
        return

    title_raw = " ".join(parts[:-3])
    title = title_raw.replace("-", " ")

    # Discord timestamp
    timestamp = int(target_time.timestamp())
    countdown_msg = await ctx.send(
        f"@everyone\n\n**{title}**\n\nCountdown: <t:{timestamp}:R>\n\n."
    )

    while True:
        now = datetime.utcnow()
        remaining = (target_time - now).total_seconds()
        if remaining <= 0:
            break

        # ตรวจสอบข้อความยังอยู่
        try:
            await countdown_msg.fetch()
        except discord.NotFound:
            return  # stop if message deleted

        # เปลี่ยน sleep ตามเวลาที่เหลือ
        if remaining <= 10:
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(5)

    role = discord.utils.get(ctx.guild.roles, name="Registered")
    if not role:
        await countdown_msg.delete()
        return

    # Load users
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    eligible_members = [m for m in ctx.guild.members if role in m.roles and str(m.id) in data]

    await countdown_msg.delete()  # Delete countdown

    if not eligible_members:
        return  # Do nothing if no eligible users

    amount = min(amount, len(eligible_members))
    winners = random.sample(eligible_members, amount)

    # Send winners message
    msg = f"**{title}**\n\nRandomly selected users 🎉\n\n"
    for w in winners:
        msg += f"{w.mention}\n\n"
    msg += "."

    await ctx.send(msg)
    log_winners(winners, title, data)




# ------------------------------
# winnerlog (owner only)
# ------------------------------
@bot.command()
async def winnerlog(ctx, member: discord.Member = None, channel: discord.TextChannel = None):

    # Owner only
    if ctx.author.id != ctx.guild.owner_id:
        return

    # Delete before sending
    try:
        await ctx.message.delete()
    except:
        pass

    if member is None:
        member = ctx.author

    if channel is None:
        channel = discord.utils.get(ctx.guild.text_channels, name="winnerlogs") or ctx.channel

    user_id = str(member.id)
    if not os.path.exists(WINNERS_FILE):
        return

    with open(WINNERS_FILE, "r") as f:
        winners_data = json.load(f)

    if user_id not in winners_data or not winners_data[user_id]:
        await channel.send(f"{member.mention} has no winning history yet.")
        return

    log_list = winners_data[user_id]
    msg = f"📜 Winning history of {member.mention}:\n\n"

    for entry in log_list:
        msg += f"- `{entry['username']}` won **{entry['title']}** at {entry['timestamp']} UTC\n"

    if len(msg) > 2000:
        for i in range(0, len(msg), 2000):
            await channel.send(msg[i:i+2000])
    else:
        await channel.send(msg)



# ------------------------------
# clear (owner only)
# ------------------------------
@bot.command()
async def clear(ctx):

    # Owner only
    if ctx.author.id != ctx.guild.owner_id:
        return

    # Delete before sending
    try:
        await ctx.message.delete()
    except:
        pass

    deleted = await ctx.channel.purge(limit=None)
    print(f"Cleared {len(deleted)} messages in #{ctx.channel.name}")



# ------------------------------
# Delete all message except in whitelist
# ------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # Do not delete messages from bots themselves

    # Check if the author is the server owner
    is_owner = message.author.id == message.guild.owner_id

    # List of commands exempt from deletion
    whitelist_owner = ["!register", "!randomuser", "!randomusercount", "!clear", "!winnerlog"]

    if is_owner:
        # Owner: delete only messages starting with '!' that are not in the whitelist
        if message.content.startswith("!") and not any(message.content.startswith(cmd) for cmd in whitelist_owner):
            try:
                await message.delete()
            except:
                pass
    else:
        # Regular users: delete all messages except !register
        if not message.content.startswith("!register"):
            try:
                await message.delete()
            except:
                pass

    # Must call process_commands so that commands continue to work
    await bot.process_commands(message)



# ------------------------------
# Handle command errors (delete message if command fails)
# ------------------------------
@bot.event
async def on_command_error(ctx, error):
    # ลบข้อความคำสั่งเสมอ
    try:
        await ctx.message.delete()
    except:
        pass



# ------------------------------
# Run the full bot
# ------------------------------
server_on()


bot.run(os.getenv('TOKEN'))








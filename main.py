import asyncio
import datetime
import io
import math
import signal
import shutil
import sys
import time
import os

import aiohttp
import requests
from PIL import Image, ImageDraw, ImageFont
import re
import discord
import traceback
from colorama import init, Fore, Style
from discord.ext import commands
from discord import Intents
from dotenv import load_dotenv
from config_handler import ConfigHandler

load_dotenv()


def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as error:
            tb = traceback.extract_tb(error.__traceback__)
            file = tb[-1].filename
            line = tb[-1].lineno
            error_message = f"An error occurred in {Fore.CYAN + Style.BRIGHT}{file}{Style.RESET_ALL}\n{Fore.CYAN + Style.BRIGHT}Line: {line}{Fore.RED} error: {error} {Style.RESET_ALL}"
            print(" " * console_width, end="\r")
            print(
                Fore.YELLOW
                + Style.BRIGHT
                + "\n"
                + error_message
                + "\n"
                + Style.RESET_ALL
            )

    return wrapper


@error_handler
def log_print(message, log_file_name="log.txt", max_lines=1000):
    def remove_color_codes(text):
        color_pattern = re.compile(r"(\x1b\[[0-9;]*m)|(\033\[K)")
        return color_pattern.sub("", text)

    def trim_log_file():
        try:
            with open(log_file_name, "r") as original_file:
                lines = original_file.readlines()

            if len(lines) >= max_lines:
                lines_to_remove = len(lines) - max_lines + 1
                new_lines = lines[lines_to_remove:]
                with open(log_file_name, "w") as updated_file:
                    updated_file.writelines(new_lines)

        except Exception as e:
            print(f"Error trimming log file: {e}")

    original_stdout = sys.stdout
    try:
        print(message)

        with open(log_file_name, "a") as log_file:
            sys.stdout = log_file
            message_without_colors = remove_color_codes(message)
            print(message_without_colors)
        trim_log_file()

    except Exception as e:
        sys.stdout = original_stdout
        print(f"Error logging to file: {e}")
    finally:
        sys.stdout = original_stdout


@error_handler
def main():
    @error_handler
    def get_timestamp():
        now = datetime.datetime.now()
        timestr = now.strftime("%Y-%m-%d %H:%M:%S")
        timestr = f"{Fore.YELLOW}[{Fore.RESET}{Fore.CYAN + timestr + Fore.RESET}{Fore.YELLOW}]{Fore.RESET}"
        return timestr

    def clear_console():
        os.system("cls" if os.name == "nt" else "clear")

    @error_handler
    def generate_timestamp_string(started_at):
        started_datetime = datetime.datetime.fromisoformat(started_at.rstrip("Z"))
        unix_timestamp = int(started_datetime.timestamp()) + 3600
        timestamp_string = f"<t:{unix_timestamp}:T>"
        return timestamp_string

    @error_handler
    async def check_stream(session, streamer_name):
        if not streamer_name:
            return False

        params = {
            "user_login": streamer_name,
        }

        async with session.get(
            API_BASE_URL, headers=HEADERS, params=params
        ) as response:
            if response.status == 200:
                data = await response.json()

                if "data" in data and len(data["data"]) > 0:
                    if streamer_name.lower() not in processed_streamers:
                        asyncio.create_task(
                            send_notification(streamer_name.strip(), data)
                        )
                        processed_streamers.append(streamer_name.lower())
                    return True
                if streamer_name.lower() in processed_streamers:
                    processed_streamers.remove(streamer_name.lower())

            return False

    @error_handler
    async def send_notification(streamer_name, data):
        streamer_lists = ch.get_user_ids_with_streamers()
        for user_id, streamers in streamer_lists.items():
            try:
                member = await bot.fetch_user(int(user_id))
                if member:
                    dm_channel = member.dm_channel
                    if dm_channel is None:
                        dm_channel = await member.create_dm()
                    for streamer in streamers:
                        if streamer_name == streamer.strip():
                            embed = discord.Embed(
                                title=f"{streamer_name} is streaming!",
                                description=f"Click [here](https://www.twitch.tv/{streamer_name}) to watch the stream.",
                                color=discord.Color.green(),
                            )
                            if "data" in data and len(data["data"]) > 0:
                                stream_data = data["data"][0]
                                started_at = stream_data["started_at"]
                                user_id = stream_data["user_id"]
                                user_url = (
                                    f"https://api.twitch.tv/helix/users?id={user_id}"
                                )
                                if (
                                    "game_name" in stream_data
                                    and stream_data["game_name"]
                                ):
                                    game = stream_data["game_name"]
                                    embed.add_field(name="Game", value=game)

                                title = stream_data["title"]
                                viewers = stream_data["viewer_count"]
                                if int(viewers) == 0:
                                    embed.add_field(
                                        name="Viewers",
                                        value="No viewers. Be the first!",
                                    )
                                else:
                                    embed.add_field(name="Viewers", value=viewers)
                                user_response = requests.get(user_url, headers=HEADERS)
                                user_data = user_response.json()
                                profile_picture_url = user_data["data"][0][
                                    "profile_image_url"
                                ]
                                profile_picture_url = profile_picture_url.replace(
                                    "{width}", "300"
                                ).replace("{height}", "300")
                                start_time_str = generate_timestamp_string(started_at)
                                embed.add_field(name="Stream Title", value=title)
                                embed.set_thumbnail(url=profile_picture_url)
                                embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
                                mention = f"||{member.mention}||"
                                embed.add_field(
                                    name="Stream Start Time (local)",
                                    value=start_time_str,
                                )
                                try:
                                    await dm_channel.send(mention, embed=embed)
                                    print(" " * console_width, end="\r")
                                    log_print(
                                        Fore.CYAN
                                        + get_timestamp()
                                        + Fore.RESET
                                        + " "
                                        + Fore.LIGHTGREEN_EX
                                        + f"Notification sent successfully for {Fore.CYAN + streamer_name + Fore.RESET}. {Fore.LIGHTGREEN_EX}to member {Fore.LIGHTCYAN_EX + member.name + Fore.RESET}"
                                    )
                                except discord.errors.Forbidden:
                                    print(" " * console_width, end="\r")
                                    log_print(
                                        Fore.CYAN
                                        + get_timestamp()
                                        + Fore.RESET
                                        + " "
                                        + f"Cannot send a message to user {member.name}. Missing permissions or DMs disabled."
                                    )
                            else:
                                print(" " * console_width, end="\r")
                                log_print(
                                    Fore.CYAN
                                    + get_timestamp()
                                    + Fore.RESET
                                    + " "
                                    + f"{streamer_name} is not streaming."
                                )
                                processed_streamers.remove(streamer_name)
            except discord.errors.NotFound:
                print(" " * console_width, end="\r")
                log_print(
                    Fore.CYAN
                    + get_timestamp()
                    + Fore.RESET
                    + " "
                    + Fore.RED
                    + f"User with ID {user_id} not found."
                    + Fore.RESET
                )

    @bot.command(
        name="watch",
        aliases=["w"],
        usage="watch <streamername_or_link>",
        help="Add a streamer to your watch list (provide either streamer name or link)",
    )
    async def watch(ctx, streamer_name_or_link: str):
        if "https://www.twitch.tv/" in streamer_name_or_link:
            streamer_name = re.search(
                r"https://www.twitch.tv/([^\s/]+)", streamer_name_or_link
            ).group(1)
            streamer_name = streamer_name.lower()
        else:
            streamer_name = streamer_name_or_link.lower()
        url = f"https://api.twitch.tv/helix/users?login={streamer_name}"
        headers = {
            "Client-ID": f"{CLIENT_ID}",
            "Authorization": f"Bearer {AUTHORIZATION}",
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        if not data["data"]:
            print(" " * console_width, end="\r")
            log_print(
                Fore.CYAN
                + get_timestamp()
                + Fore.RESET
                + " "
                + Fore.RED
                + f"{Fore.CYAN + streamer_name + Fore.RESET} Twitch profile not found."
                + Fore.RESET
            )
            embed = discord.Embed(
                title="Streamer not found",
                description=f"**__{streamer_name}__** was not found.",
                color=discord.Color.red(),
            )
            embed.set_thumbnail(url="https://i.imgur.com/lmVQboe.png")
            await ctx.send(embed=embed)
            return
        pfp = data["data"][0]["profile_image_url"]
        user_id = str(ctx.author.id)
        user_ids = ch.get_all_user_ids()
        if user_id in user_ids:
            streamer_list = ch.get_streamers_for_user(user_id)
            if streamer_name.lower() not in [s.lower().strip() for s in streamer_list]:
                ch.add_streamer_to_user(user_id, streamer_name.strip())
                streamer_list.append(streamer_name.strip())
                print(" " * console_width, end="\r")
                log_print(
                    Fore.CYAN
                    + get_timestamp()
                    + Fore.RESET
                    + " "
                    + Fore.LIGHTGREEN_EX
                    + f"Added {Fore.CYAN + streamer_name + Fore.RESET} to user {Fore.CYAN + ctx.author.name + Fore.RESET}'s watchlist."
                    + Fore.RESET
                )
                embed = discord.Embed(
                    title="Stream Watchlist",
                    description=f"Added **__{streamer_name}__** to your watchlist.",
                    color=65280,
                )
                embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
                embed.set_thumbnail(url=pfp)
                await ctx.send(embed=embed)
            else:
                print(" " * console_width, end="\r")
                log_print(
                    Fore.CYAN
                    + get_timestamp()
                    + Fore.RESET
                    + " "
                    + f"{Fore.CYAN + streamer_name + Fore.RESET} is already in user {Fore.CYAN + ctx.author.name + Fore.RESET}'s watchlist."
                )
                embed = discord.Embed(
                    title="Stream Watchlist",
                    description=f"{streamer_name} is already in your watchlist.",
                    color=16759808,
                )
                embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
                await ctx.send(embed=embed)
        else:
            ch.add_user(
                user_data={
                    "discord_username": ctx.author.name,
                    "discord_id": user_id,
                    "streamer_list": [streamer_name.strip()],
                }
            )
            print(" " * console_width, end="\r")
            log_print(
                Fore.CYAN
                + get_timestamp()
                + Fore.RESET
                + " "
                + Fore.LIGHTGREEN_EX
                + f"Created a new watchlist for user {Fore.CYAN + ctx.author.name + Fore.RESET} and added {Fore.CYAN + streamer_name + Fore.RESET}."
                + Fore.RESET
            )
            embed = discord.Embed(
                title="Stream Watchlist",
                description=f"Created a new watchlist for you and added {streamer_name}.",
                color=65280,
            )
            embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
            await ctx.send(embed=embed)

    @bot.command(
        name="unwatch",
        aliases=["u"],
        usage="unwatch <streamername_or_link>",
        help="Removes the streamer from your watch list (provide either streamer name or link)",
    )
    async def unwatch(ctx, streamer_name_or_link: str):
        if "https://www.twitch.tv/" in streamer_name_or_link:
            streamer_name = re.search(
                r"https://www.twitch.tv/([^\s/]+)", streamer_name_or_link
            ).group(1)
            streamer_name = streamer_name.lower()
        else:
            streamer_name = streamer_name_or_link.lower()

        user_id = str(ctx.author.id)
        user_ids = ch.get_all_user_ids()
        if user_id in user_ids:
            streamer_list = ch.get_streamers_for_user(user_id)
            if any(streamer_name.lower() == s.lower() for s in streamer_list):
                ch.remove_streamer_from_user(user_id, streamer_name)
                if (
                    streamer_name in processed_streamers
                    and streamer_name not in ch.get_all_streamers()
                ):
                    processed_streamers.remove(streamer_name.lower())
                print(" " * console_width, end="\r")
                log_print(
                    Fore.CYAN
                    + get_timestamp()
                    + Fore.RESET
                    + " "
                    + Fore.LIGHTGREEN_EX
                    + f"Removed {Fore.CYAN + streamer_name + Fore.RESET} from user {Fore.CYAN + ctx.author.name + Fore.RESET}'s watchlist."
                    + Fore.RESET
                )
                embed = discord.Embed(
                    title="Stream Watchlist",
                    description=f"Removed {streamer_name} from your watchlist.",
                    color=65280,
                )
                embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
                await ctx.channel.send(embed=embed)
            else:
                print(" " * console_width, end="\r")
                log_print(
                    Fore.CYAN
                    + get_timestamp()
                    + Fore.RESET
                    + " "
                    + f"{Fore.CYAN + streamer_name + Fore.RESET} is not in user {Fore.CYAN + ctx.author.name + Fore.RESET}'s watchlist."
                )
                embed = discord.Embed(
                    title="Stream Watchlist",
                    description=f"{streamer_name} is not in your watchlist.",
                    color=16759808,
                )
                embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
                await ctx.channel.send(embed=embed)

    @bot.command(
        name="clear",
        aliases=["c"],
        help="Clears all the messages sent by the bot",
        usage="clear",
    )
    async def clear_bot_messages(ctx):
        messages_to_remove = 1000
        user = await bot.fetch_user(ctx.author.id)

        async for message in ctx.history(limit=messages_to_remove):
            if message.author.id == bot.user.id:
                await message.delete()
                await asyncio.sleep(1)

        # Create and send an embed message
        embed = discord.Embed(
            title="Conversation Cleared",
            description="All messages have been cleared.",
            color=65280,
        )
        embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
        await ctx.send(embed=embed)

    async def fetch_streamer_data(session, streamer_name, pfps, names):
        streamer_name = streamer_name.replace(" ", "")
        url = f"https://api.twitch.tv/helix/users?login={streamer_name}"

        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                if "data" in data and len(data["data"]) > 0:
                    streamer_data = data["data"][0]
                    profile_picture_url = streamer_data.get("profile_image_url", "")
                    profile_picture_url = profile_picture_url.replace(
                        "{width}", "150"
                    ).replace("{height}", "150")
                    pfps.append(profile_picture_url)
                    names.append(streamer_data["display_name"])
                else:
                    print(" " * console_width, end="\r")
                    log_print(
                        f"{get_timestamp()} No data found for streamer: {streamer_name}"
                    )

    @bot.command(
        name="list",
        aliases=["l"],
        help="Returns an embed with a list of all the streamers you're currently watching",
        usage="list",
    )
    async def list_streamers(ctx):
        user_id = str(ctx.author.id)
        member = await bot.fetch_user(int(user_id))
        user_ids = ch.get_all_user_ids()

        if user_id in user_ids:
            streamer_list = ch.get_streamers_for_user(user_id)

            if streamer_list:
                streamer_names = ", ".join(streamer_list)
                print(" " * console_width, end="\r")
                log_print(
                    "\033[K"
                    + Fore.CYAN
                    + get_timestamp()
                    + Fore.RESET
                    + " "
                    + Fore.LIGHTYELLOW_EX
                    + ctx.author.name
                    + Fore.RESET
                    + f" requested their streamers: {len(streamer_list)}"
                )
                pfps = []
                names = []
                async with aiohttp.ClientSession() as session:
                    await asyncio.gather(
                        *[
                            fetch_streamer_data(session, streamer, pfps, names)
                            for streamer in streamer_list
                        ]
                    )

                num_pfps = len(pfps)
                max_images_per_row = 5
                image_width = 100
                image_height = 100
                num_rows = math.ceil(num_pfps / max_images_per_row)

                name_box_width = image_width
                name_box_height = 20
                name_box_color = (0, 0, 0)
                name_text_color = (255, 255, 255)
                font_size = 9
                font = ImageFont.truetype("arialbd.ttf", font_size)

                if num_pfps <= max_images_per_row:
                    combined_image_width = num_pfps * image_width
                else:
                    combined_image_width = max_images_per_row * image_width

                combined_image_height = num_rows * (image_height + name_box_height)

                combined_image = Image.new(
                    "RGB", (combined_image_width, combined_image_height)
                )

                x_offset = 0
                y_offset = name_box_height

                for i, (pfp_url, name) in enumerate(zip(pfps, names)):
                    pfp_response = requests.get(pfp_url)
                    pfp_image = Image.open(io.BytesIO(pfp_response.content))
                    pfp_image.thumbnail((image_width, image_height))

                    name_x = x_offset
                    name_y = y_offset - name_box_height

                    combined_image.paste(pfp_image, (x_offset, y_offset))

                    name_box = Image.new(
                        "RGB", (name_box_width, name_box_height), name_box_color
                    )

                    draw = ImageDraw.Draw(name_box)
                    text_bbox = draw.textbbox((0, 0), name, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                    text_x = (name_box_width - text_width) // 2
                    text_y = (name_box_height - text_height) // 2
                    draw.text((text_x, text_y), name, fill=name_text_color, font=font)

                    combined_image.paste(name_box, (name_x, name_y))

                    x_offset += image_width

                    if x_offset >= combined_image_width:
                        x_offset = 0
                        y_offset += image_height + name_box_height

                combined_image.save("combined_image.png")

                embed = discord.Embed(
                    title=f"Your Streamers {member.name}",
                    description=f"**You are currently watching the following streamers:**",
                    color=10242047,
                )
                embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
                embed.set_image(url="attachment://combined_image.png")

                with open("combined_image.png", "rb") as img_file:
                    file = discord.File(img_file)
                    await ctx.channel.send(file=file, embed=embed)
                os.remove("combined_image.png")

                return streamer_names, combined_image

            else:
                print(" " * console_width, end="\r")
                log_print(
                    Fore.CYAN
                    + get_timestamp()
                    + Fore.RESET
                    + " "
                    + Fore.YELLOW
                    + f"{Fore.CYAN + ctx.author.name + Fore.RESET} requested their streamers, but the watchlist is empty."
                    + Fore.RESET
                )
                embed = discord.Embed(
                    title="Stream Watchlist",
                    description="Your watchlist is empty.",
                    color=16759808,
                )
                embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
                await ctx.channel.send(embed=embed)
        else:
            print(" " * console_width, end="\r")
            log_print(
                Fore.CYAN
                + get_timestamp()
                + Fore.RESET
                + " "
                + Fore.RED
                + f"{Fore.CYAN + ctx.author.name + Fore.RESET} requested their streamers, but they don't have a watchlist yet."
                + Fore.RESET
            )
            embed = discord.Embed(
                title="Stream Watchlist",
                description="You don't have a watchlist yet.",
                color=16711680,
            )
            embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")
            await ctx.channel.send(embed=embed)

    @bot.command(
        name="help",
        aliases=["h", "commands", "command"],
        usage="help",
        help="Shows all the available commands and their descriptions",
    )
    async def list_commands(ctx):
        embed = discord.Embed(
            title="Bot Commands",
            description="Here are the available commands, their descriptions, and usage:",
            color=65280,
        )

        sorted_commands = sorted(bot.commands, key=lambda x: x.name)

        for command in sorted_commands:
            if command.hidden:
                continue

            description = command.help or "No description available."
            aliases = ", ".join(command.aliases) if command.aliases else "No aliases"
            usage = command.usage or f"No usage specified for {command.name}"

            embed.add_field(
                name=f"**{command.name.capitalize()}**",
                value=f"Description: {description}\nUsage: `{usage}`\nAliases: {aliases}",
                inline=False,
            )

        embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")

        await ctx.send(embed=embed)

    @bot.command(
        name="invite",
        aliases=["i"],
        help="Generates bot invite link",
        usage="invite",
    )
    async def invite(ctx):
        embed = discord.Embed(
            title="Invite Me!",
            description=f"[Click here](https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot)",
            color=65280,
        )
        embed.set_footer(text=f"{VERSION} | Made by Beelzebub2")

        await ctx.send(embed=embed)

    @bot.command(
        name="configrole",
        aliases=["cr"],
        usage="configrole <@role>",
        help="Change the role to add in the server configuration",
    )
    async def prefix_config_role(ctx, role: discord.Role):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send(
                "You do not have the necessary permissions to use this command."
            )
            return
        guild_id = ctx.guild.id
        role_id = role.id
        ch.change_role_to_add(guild_id, role_id)
        await ctx.send(
            f"The role to add has been updated to {role.mention} in the server configuration."
        )

    @bot.command(
        name="configprefix",
        aliases=["cx"],
        usage="configprefix <new_prefix>",
        help="changes the default prefix of the guild",
    )
    async def change_guild_prefix(ctx, new_prefix: str):
        if ctx.author.guild_permissions.administrator:
            guild_id = ctx.guild.id
            ch.change_guild_prefix(guild_id, new_prefix)
            await ctx.send(f"Prefix for this guild has been updated to `{new_prefix}`.")
        else:
            await ctx.send(
                "You do not have the necessary permissions to change the prefix."
            )

    @bot.command(
        name="unregister",
        aliases=["unreg"],
        help="Wipes out the watchlist.",
        usage="unregister",
    )
    async def unregister_user(ctx):
        user_id = str(ctx.author.id)

        if ch.delete_user(user_id):
            print(" " * console_width, end="\r")
            log_print(
                Fore.CYAN
                + get_timestamp()
                + Fore.RESET
                + " "
                + Fore.YELLOW
                + f"{Fore.RED + ctx.author.name + Fore.RESET} Unregistered from bot."
                + Fore.RESET
            )
            embed = discord.Embed(
                title="Unregistration Successful",
                description="You have been unregistered from the bot.",
                color=0x00FF00,
            )
            embed.set_thumbnail(url="https://i.imgur.com/TavP95o.png")
            await ctx.send(embed=embed)
        else:
            print(" " * console_width, end="\r")
            log_print(
                Fore.CYAN
                + get_timestamp()
                + Fore.RESET
                + " "
                + Fore.YELLOW
                + f"{Fore.RED + ctx.author.name + Fore.RESET} Tried to unregister from bot but wasn't registered to begin with."
                + Fore.RESET
            )
            embed = discord.Embed(
                title="Unregistration Error",
                description="You are not registered with the bot.",
                color=0xFF0000,
            )
            embed.set_thumbnail(url="https://i.imgur.com/lmVQboe.png")
            await ctx.send(embed=embed)

    @bot.command(
        name="restart",
        aliases=["rr"],
        help="Restarts Bot.",
        usage="restart",
        hidden=True,
    )
    async def restart(ctx):
        if str(ctx.author.id) != ch.get_bot_owner_id():
            embed = discord.Embed(
                title="Permission Error",
                description="You don't have permissions to use this command.",
                color=0xFF0000,
            )
            embed.set_thumbnail(url="https://i.imgur.com/lmVQboe.png")
            await ctx.send(embed=embed)
            return
        data = {"Restarted": True, "Streamers": processed_streamers}
        ch.save_to_temp_json(data)
        embed = discord.Embed(
            title="Restarting",
            description="Bot is restarting...",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/TavP95o.png")
        await ctx.send(embed=embed)

        python = sys.executable
        print(python)
        os.execl(python, python, *sys.argv)

    @bot.command(name="stats", aliases=["st"], help="Shows Bots stats.", usage="stats")
    async def uptime(ctx):
        current_time = datetime.datetime.now()
        uptime = current_time - bot_start_time
        uptime = str(uptime).split(".")[0]
        embed = discord.Embed(title="Bot Stats", color=discord.Color.green())
        embed.add_field(name="Uptime", value=f"My current uptime is {uptime}")
        embed.add_field(name="Users", value=len(ch.get_all_user_ids()))
        embed.add_field(name="Streamers", value=len(ch.get_all_streamers()))
        await ctx.send(embed=embed)

    @bot.event
    async def on_disconnect():
        clear_console()

    @bot.event
    async def on_resumed():
        print(" " * console_width, end="\r")
        log_print(
            Fore.CYAN
            + get_timestamp()
            + Fore.RESET
            + Fore.LIGHTGREEN_EX
            + f" Running as {Fore.LIGHTCYAN_EX + bot.user.name + Fore.RESET}"
        )
        clear_console()

    @bot.event
    async def on_ready():
        global bot_start_time
        bot_start_time = datetime.datetime.now()
        if not ch.check_restart_status():
            bot_owner_id = ch.get_bot_owner_id()
            if bot_owner_id:
                owner = bot.get_user(int(bot_owner_id))
                embed = discord.Embed(
                    title="Initialization Successful",
                    description="Bot started successfully.",
                    color=0x00FF00,
                )
            embed.set_thumbnail(url="https://i.imgur.com/TavP95o.png")
            await owner.send(embed=embed)
        clear_console()
        print(" " * console_width, end="\r")
        log_print(
            Fore.CYAN
            + get_timestamp()
            + Fore.RESET
            + Fore.LIGHTGREEN_EX
            + f" Running as {Fore.LIGHTCYAN_EX + bot.user.name + Fore.RESET}"
        )
        activity = discord.Activity(
            type=discord.ActivityType.watching, name="Mention me to see my prefix"
        )
        await bot.change_presence(activity=activity)

        while True:
            start_time = time.time()
            print(" " * console_width, end="\r")
            print(
                "\033[K"
                + Fore.CYAN
                + get_timestamp()
                + Fore.RESET
                + " "
                + Fore.LIGHTYELLOW_EX
                + "Checking"
                + Fore.RESET,
                end="\r",
            )

            streamers = ch.get_all_streamers()
            async with aiohttp.ClientSession() as session:
                await asyncio.gather(
                    *[check_stream(session, streamer) for streamer in streamers]
                )

            end_time = time.time()
            elapsed_time = end_time - start_time

            if len(processed_streamers) != 0:
                print(" " * console_width, end="\r")
                print(
                    Fore.CYAN
                    + get_timestamp()
                    + Fore.RESET
                    + " "
                    + Fore.LIGHTGREEN_EX
                    + f"Currently streaming (Time taken: {elapsed_time:.2f} seconds): "
                    + Fore.RESET
                    + Fore.LIGHTWHITE_EX
                    + str(processed_streamers)
                    + Fore.RESET,
                    end="\r",
                )
            else:
                print(" " * console_width, end="\r")
                print(
                    Fore.CYAN
                    + get_timestamp()
                    + Fore.RESET
                    + Fore.LIGHTWHITE_EX
                    + f" Checked {len(streamers)} streamers. Time taken: {elapsed_time:.2f} seconds"
                    + Fore.RESET,
                    end="\r",
                )

            await asyncio.sleep(5)

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            command = ctx.message.content
            print(" " * console_width, end="\r")
            log_print(
                Fore.CYAN
                + get_timestamp()
                + Fore.RESET
                + " "
                + Fore.RED
                + f"Command {Fore.CYAN + command + Fore.RESET} doesn't exist."
                + Fore.RESET
            )
            embed = discord.Embed(
                title="Command not found",
                description=f"Command **__{command}__** does not exist use .help for more info.",
                color=discord.Color.red(),
            )
            embed.set_thumbnail(url="https://i.imgur.com/lmVQboe.png")
            await ctx.send(embed=embed)
        else:
            # Handle other errors
            await ctx.send(f"An error occurred: {error}")

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return

        if bot.user.mentioned_in(message):
            if isinstance(message.channel, discord.DMChannel):
                embed = discord.Embed(
                    title=f"Hello, {message.author.display_name}!",
                    description=f"My prefix is: `{ch.get_prefix()}`",
                    color=discord.Color.green(),
                )

            elif isinstance(message.channel, discord.TextChannel):
                guild_prefix = bot.command_prefix
                if message.guild:
                    guild_prefix = ch.get_guild_prefix(message.guild.id)

                embed = discord.Embed(
                    title=f"Hello, {message.author.display_name}!",
                    description=f"My prefix for this server is: `{guild_prefix}`",
                    color=discord.Color.green(),
                )
            await message.channel.send(embed=embed)

        await bot.process_commands(message)

    @bot.event
    async def on_guild_join(guild):
        guild_id = guild.id
        guild_name = guild.name
        if not ch.is_guild_in_config(guild_id):
            ch.create_new_guild_template(guild_id, guild_name)

    @bot.event
    async def on_member_join(member):
        guild_id = member.guild.id

        role_id = int(ch.get_role_to_add(guild_id))
        general_channel = member.guild.text_channels[0]

        if not role_id:
            await general_channel.send(
                f"Welcome {member.mention} to the server, but it seems the server administrator has not configured the role assignment. Please contact an admin for assistance."
            )
        else:
            role = member.guild.get_role(role_id)
            if role:
                if role not in member.roles:
                    await member.add_roles(role)
                    print(" " * console_width, end="\r")
                    log_print(
                        f"{get_timestamp()} Assigned role named {role.name} to {member.display_name} in the target guild."
                    )
            else:
                await general_channel.send(
                    f"Welcome {member.mention} to the server, but the configured role with ID {role_id} does not exist. Please contact an admin to update the role ID."
                )


@error_handler
def create_env():
    if os.path.exists(".env"):
        return
    if CLIENT_ID and AUTHORIZATION and TOKEN:
        return

    if "REPLIT_DB_URL" in os.environ:
        if CLIENT_ID is None or AUTHORIZATION is None or TOKEN is None:
            print("Running on Replit")

    if "DYNO" in os.environ:
        if CLIENT_ID is None or AUTHORIZATION is None or TOKEN is None:
            print("Running on Heroku")

    env_keys = {
        "client_id": "Your Twitch application client id",
        "authorization": "Your Twitch application authorization token",
        "token": "Your discord bot token",
    }
    with open(".env", "w") as env_file:
        for key, value in env_keys.items():
            env_file.write(f"{key}={value}\n")

    if os.path.exists(".env"):
        print(
            "Secrets missing! created successfully please change filler text on .env or host secrets"
        )
        os._exit(0)


async def get_custom_prefix(bot, message):
    if message.guild:
        guild_id = message.guild.id
        custom_prefix = ch.get_guild_prefix(guild_id)
        if custom_prefix:
            return custom_prefix
    return ch.get_prefix()


def custom_interrupt_handler(signum, frame):
    print(" " * console_width, end="\r")
    if len(processed_streamers) > 0:
        print(
            f"{Fore.LIGHTYELLOW_EX}[{Fore.RESET + Fore.LIGHTGREEN_EX}KeyboardInterrupt{Fore.LIGHTYELLOW_EX}]{Fore.RESET}{Fore.LIGHTWHITE_EX} Saving currently streaming streamers and exiting..."
        )
        data = {"Restarted": True, "Streamers": processed_streamers}
        ch.save_to_temp_json(data)
        os._exit(0)

    print(
        f"{Fore.LIGHTYELLOW_EX}[{Fore.RESET + Fore.LIGHTGREEN_EX}KeyboardInterrupt{Fore.LIGHTYELLOW_EX}]{Fore.RESET}{Fore.LIGHTWHITE_EX} No streamers currently streaming. exiting..."
    )
    os._exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, custom_interrupt_handler)
    CLIENT_ID = os.environ.get("client_id")
    AUTHORIZATION = os.environ.get("authorization")
    TOKEN = os.environ.get("token")
    create_env()
    ch = ConfigHandler("data.json")
    intents = Intents.all()
    intents.dm_messages = True
    bot = commands.Bot(
        command_prefix=commands.when_mentioned_or(ch.get_prefix), intents=intents
    )
    try:
        console_width = shutil.get_terminal_size().columns
    except AttributeError:
        console_width = 80
    bot.command_prefix = get_custom_prefix
    bot.remove_command("help")  # delete default help command
    if ch.check_restart_status():
        processed_streamers = ch.processed_streamers
    else:
        processed_streamers = []
    API_BASE_URL = "https://api.twitch.tv/helix/streams"
    VERSION = ch.get_version()
    HEADERS = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {AUTHORIZATION}",
    }
    init()
    main()
    bot.run(TOKEN)

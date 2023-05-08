#!/usr/bin/env python3

# common libs
import os
import sys
import time
import hashlib
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# 3rd party libs
import discord
from dotenv import load_dotenv

# constants
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
TEST_GUILD_ID = int(os.getenv('TEST_GUILD_ID'))
MAGIC_USER_ID = int(os.getenv('MAGIC_USER_ID')) # only a certain user can trigger extra behaviors
MAGIC_TRIGGER_STRING = "Take it away, Link Bot!"
LOGS_DIR = 'logs'
AUTH_FILE = f'{LOGS_DIR}/auth.log'
LOG_FILE = f'{LOGS_DIR}/main.log'
ERR_FILE = f'{LOGS_DIR}/err.log'
PREFILL_FORM_LINK_TEMPLATE = 'https://docs.google.com/forms/d/e/1FAIpQLSc6_HtfblPc_hikKztWNh6SfEhKAEzFxTgUQqbFDXQ7qFq08A/viewform?usp=pp_url&entry.1426369734={username}&entry.1675772246={userid}&entry.1231032926={auth_token}'
SPECIAL_MESSAGE = f"""
Thanks <@{MAGIC_USER_ID}>, and hi @everyone! React to this message, and I'll DM you an authenticated link to fill out the consent form.
"""

# client setup
intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True
client : discord.Client = discord.Client(intents=intents)


# auth definitions
@dataclass
class UserAuth:

    discord_username: str
    discord_userid: str
    timestamp: float
    nonce: int
    hash_digest: str = None

    def get_hash_data_str(self) -> str:
        return f'{self.discord_username},{self.discord_userid},{self.timestamp},{self.nonce}'

    def get_full_auth_str(self) -> str:
        return f'{self.get_hash_data_str()},{self.hash_digest}'


def get_token(discord_username: str, discord_userid: int) -> UserAuth:
    auth = UserAuth(
        discord_username=discord_username,
        discord_userid=discord_userid,
        timestamp=time.time(),
        nonce=os.urandom(16).hex())
    auth.hash_digest = hashlib.sha256(string=auth.get_hash_data_str().encode('utf-8'), usedforsecurity=True).hexdigest()
    return auth


async def send_user_authenticated_link(user: discord.User):
    discord_username = f'{user.name}#{user.discriminator}'
    discord_userid = user.id
    log(f"starting authentication request for {discord_username} (id={user.id})")
    auth_token = get_token(discord_username=discord_username, discord_userid=discord_userid)
    log(auth_token.get_full_auth_str(), filename=AUTH_FILE)

    resolved_prefill_form_link = PREFILL_FORM_LINK_TEMPLATE.format(
        username=urllib.parse.quote(discord_username),
        userid=discord_userid,
        auth_token=auth_token.hash_digest
    )

    await user.send(f"""
Authenticated as <@{discord_userid}>.
security stuff, if you're curious: ||userid={discord_userid}, epoch timestamp={auth_token.timestamp}, nonce={auth_token.nonce}, generated auth token={auth_token.hash_digest}
auth token = SHA256("{auth_token.get_hash_data_str()}".encode('utf-8'))||
Your authenticated URL: {resolved_prefill_form_link}
To get a new URL, either send me a message, or react on any of my messages!
""")


# utils
def log(message: str, filename: str=LOG_FILE, print_dest=sys.stdout):
    # create log folder if not yet created
    if not log.path_verified:
        Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
        log.path_verified = True
    # get fully formatted message
    now = datetime.now()
    full_msg = f'{now.isoformat()}: {message}'
    # print message to console
    if print_dest:
        print(full_msg, file=print_dest)
    # log message to file
    with open(filename, 'a') as f:
        f.write(full_msg + '\n')
log.path_verified = False


# handlers
@client.event
async def on_ready():
    log(f'{client.user} has connected to Discord!')

    # Print all guilds I'm a member of
    for guild in client.guilds:
        display_str = f'Connected to {guild.name} (id: {guild.id})'
        if guild.id == TEST_GUILD_ID:
            display_str +=  " (TEST SERVER)"
        log(display_str)


@client.event
async def on_message(message: discord.Message):
    # don't respond to my own messages
    if message.author == client.user:
        return
    # if in DM
    if not message.guild:
        user: discord.User = message.author
        log(f"received DM from {user.name}#{user.discriminator}, sending authenticated link")
        await send_user_authenticated_link(user=message.author)
    # if in server
    else:
        # if message is sent by magic user, and contains the magic trigger phrase,
        member: discord.Member = message.author
        if member.id == MAGIC_USER_ID and MAGIC_TRIGGER_STRING in message.content:
            # print the special message
            log(f"Detected the magic trigger from the magic user. Sending special message!")
            await message.reply(content=SPECIAL_MESSAGE)
        

@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # get message
    channel = await client.fetch_channel(int(payload.channel_id))
    message = await channel.fetch_message(int(payload.message_id))
    # if I'm not the author of the message, don't do anything
    if message.author != client.user:
        return
    # get the user and send them an authenticated link
    user = await client.fetch_user(int(payload.user_id))
    log(f"observed reaction on my post from {user.name}#{user.discriminator}, sending authenticated link")
    await send_user_authenticated_link(user=user)


client.run(TOKEN)
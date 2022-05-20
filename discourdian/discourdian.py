import discord
import tweepy
import praw
from instagrapi import Client as InstaClient


import logging
from dataclasses import dataclass
import nest_asyncio

import keys

nest_asyncio.apply()

logging.basicConfig(level=logging.INFO)


@dataclass
class Content:
    imageUrls: [str]
    caption: str


def postToReddit(content):
    reddit = praw.Reddit(
        client_id="91eAnEPHxBs-vesjSdnNCA",
        client_secret=keys.redditSecret,
        password=keys.redditPw,
        user_agent="discourdian posting script by u/musengdir",
        username="musengdir",
    )
    subreddit = reddit.subreddit("MakUrSpace")
    subreddit.submit_image(content.caption, content.imageUrls[0])


def postToTwitter(content):
    api = tweepy.API(tweepy.OAuth1UserHandler(
        keys.apiKey, keys.apiSecret,
        keys.accessToken, keys.accessSecret
    ))
    media_ids = [api.media_upload(imageUrl).media_id for imageUrl in content.imageUrls]
    return api.update_status(status=content.caption, media_ids=media_ids)


def postToInstagram(content):
    ic = InstaClient()
    ic.login("makurspacellc", keys.instaPw)
    media_ids = []
    for imageUrl in content.imageUrls:
        media_ids.append(ic.photo_upload(imageUrl, content.caption))
    return media_ids


class Discourdian(discord.Client):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

    async def retrieve_attachments(self, message):
        urls = []
        for attachment in message.attachments:
            filename = attachment.filename
            if filename.split('.')[-1] == 'jpg':
                path = f"./discourdian_{attachment.filename}"
                await attachment.save(f"./newMessage_{attachment.filename}")
                urls.append(path)
        return urls

    async def post_content(self, message):
        urls = await self.retrieve_attachments(message)
        content = Content(imageUrls=urls, caption=message.content)
        postToReddit(content)
        postToTwitter(content)
        postToInstagram(content)

    async def on_raw_reaction_add(self, payload):
        channel = self.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if len(message.attachments) < 1:
            return

        # Look for post signal from FinniusDeLaBoomBoom - gear emoji
        message_approved = False
        for reaction in message.reactions:
            if reaction.emoji not in ['🔑']:
                continue
            users = [user.name for user in await reaction.users().flatten()]
            if 'FinniusDeLaBoomBoom' in users:
                message_approved = True
                break

        if message_approved:
            await self.post_content(message)


client = Discourdian()
client.run(keys.discordKey)

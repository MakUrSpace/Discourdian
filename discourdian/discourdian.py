import discord
import tweepy
import praw
from instagrapi import Client as InstaClient
from random import random
from PIL import Image, ImageOps, ImageColor

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

    @staticmethod
    def fileTypeCheck(filename, types=None):
        fileType = filename.split(".")[-1]
        types = types if types is not None else ['jpg', 'png']
        return fileType in types

    def allFilesTypeCheck(self, types=None):
        return sum([self.fileTypeCheck(url, types) for url in self.imageUrls]) == len(self.imageUrls)


def postToReddit(content):
    reddit = praw.Reddit(
        client_id="91eAnEPHxBs-vesjSdnNCA",
        client_secret=keys.redditSecret,
        password=keys.redditPw,
        user_agent="discourdian posting script by u/musengdir",
        username="musengdir",
    )
    subreddit = reddit.subreddit("MakUrSpace")
    contentUrl = None
    for url in content.imageUrls:
        if content.fileTypeCheck(url, ['jpg', 'png', 'gif']):
            contentUrl = url
            break
    if contentUrl is not None:
        subreddit.submit_image(content.caption, contentUrl)


def postToTwitter(content):
    api = tweepy.API(tweepy.OAuth1UserHandler(
        keys.apiKey, keys.apiSecret,
        keys.accessToken, keys.accessSecret
    ))
    selectedUrls = [url for url in content.imageUrls if Content.fileTypeCheck(url, ['png', 'jpg'])]
    media_ids = [api.media_upload(imageUrl).media_id for imageUrl in selectedUrls]
    if media_ids:
        return api.update_status(status=content.caption, media_ids=media_ids)


def postToInstagram(content):
    ic = InstaClient()
    ic.login("makurspacellc", keys.instaPw)
    media_ids = []
    for imageUrl in content.imageUrls[:1]:
        if not content.fileTypeCheck(imageUrl, ['jpg', 'png']):
            continue
        jpgPath = f".{''.join(imageUrl.split('.')[:-1])}.jpg"
        image = Image.open(imageUrl).convert("RGB")
        color = ImageColor.getrgb("orange" if random() > 0.49 else "gray")
        expandedImage = ImageOps.expand(image, border=50, fill=color)
        newLength = max(*expandedImage.size)
        alteredImage = ImageOps.pad(image, (newLength, newLength), color=color)
        alteredImage.save(jpgPath)
        media_ids.append(ic.photo_upload(jpgPath, content.caption))
    return media_ids


class Discourdian(discord.Client):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

    async def retrieve_attachments(self, message):
        urls = []
        for attachment in message.attachments:
            filename = attachment.filename
            if filename.split('.')[-1] in ['jpg', 'png', 'gif']:
                path = f"./discourdian_{attachment.filename}"
                await attachment.save(path)
                urls.append(path)
        return urls

    async def post_content(self, message):
        urls = await self.retrieve_attachments(message)
        content = Content(imageUrls=urls, caption=message.content)
        print(f"Posting content: {content}...")
        postToReddit(content)
        postToTwitter(content)
        postToInstagram(content)
        print("Content posted.")

    async def on_raw_reaction_add(self, payload):
        channel = self.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.channel.name != "socialplatformcontent" or len(message.attachments) < 1:
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
            print("Approved Message Found! Posting...")
            await self.post_content(message)


if __name__ == "__main__":
    client = Discourdian()
    client.run(keys.discordKey)

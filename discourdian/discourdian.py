import json
from random import random
from datetime import datetime, timedelta

import discord
import tweepy
import praw
from instagrapi import Client as InstaClient
from random import random
from PIL import Image, ImageOps, ImageColor

import logging
from dataclasses import dataclass, asdict
from asyncio import sleep
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
        color = ImageColor.getrgb("orange" if random() > 0.45 else "gray")
        expandedImage = ImageOps.expand(image, border=50, fill=color)
        newLength = max(*expandedImage.size)
        alteredImage = ImageOps.pad(image, (newLength, newLength), color=color)
        alteredImage.save(jpgPath)
        media_ids.append(ic.photo_upload(jpgPath, content.caption))
    return media_ids


def postToActivityStream(content):
    pass
         

class ContentSchedule:
    def __init__(self):
        self.read()

    def write(self):
        with open("discourdianSchedule.json", "w") as f:
            f.write(json.dumps(self._schedule, indent=2))

    def read(self):
        with open("discourdianSchedule.json", "r") as f:
            self._schedule = json.loads(f.read())

    def schedule(self, when: datetime, content: Content):
        when = datetime.isoformat(when)
        if when not in self._schedule:
            self._schedule[when] = []
        self._schedule[when].append(asdict(content))
        self.write()

    def contentToPost(self):
        now = datetime.utcnow().isoformat()
        for when, content in self._schedule.items():
            if when <= now:
                yield content

    def clearSchedule(self):
        self._schedule = {}

    def syncSchedule(self):
        now = datetime.utcnow().isoformat()
        self._schedule = {when: content for when, content in self._schedule.items() if when > now}
        self.write()

    @property
    def lastScheduled(self):
        return datetime.fromisoformat(max(["2022-08-14T22:19:59.183966"] + list(self._schedule.keys())))


class Discourdian(discord.Client):
    contentSchedule = ContentSchedule()

    async def on_ready(self):
        print(f"Logged on as {self.user}!")
        print("Starting schedule loop...")
        while True:
            now = datetime.utcnow().isoformat()
            try:
                contentToPost = list(*self.contentSchedule.contentToPost())[0]
                contentToPost = Content(**contentToPost)
                await self.post_content(contentToPost)
                self.contentSchedule.syncSchedule()
            except IndexError:
                print("No content to post")

            print("Sleeping for a day")
            await sleep(30)

    async def retrieve_attachments(self, message):
        urls = []
        for attachment in message.attachments:
            filename = attachment.filename
            if filename.split('.')[-1] in ['jpg', 'png', 'gif']:
                path = f"./discourdian_{attachment.filename}"
                await attachment.save(path)
                urls.append(path)
        return urls

    async def schedule_content(self, message):
        urls = await self.retrieve_attachments(message)
        content = Content(imageUrls=urls, caption=message.content)
        contentDate = self.contentSchedule.lastScheduled + timedelta(days=1 + 2 * random(), hours=1 + 12  * random())

        self.contentSchedule.schedule(when=contentDate, content=content)
        print(f"Content scheduled for: {contentDate}")

    async def post_content(self, content):
        print(f"Posting content: {content}...")
        postToReddit(content)
        postToTwitter(content)
        postToInstagram(content)
        postToActivityStream(content)
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
            print("Approved Message Found! Scheduling...")
            await self.schedule_content(message)


if __name__ == "__main__":
    client = Discourdian()
    client.run(keys.discordKey)
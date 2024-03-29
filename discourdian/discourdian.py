import json
from random import random
from datetime import datetime, timedelta
from traceback import format_exc
from random import random

import discord
import tweepy
import praw
from playwright.async_api import async_playwright
from PIL import Image, ImageOps, ImageColor
import os

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


async def postToInstagram(content):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.instagram.com/")
        await page.get_by_label("Phone number, username, or email").click()
        await page.get_by_label("Phone number, username, or email").fill("makurspacellc")
        await page.get_by_label("Phone number, username, or email").press("Tab")
        await page.get_by_label("Password").fill(keys.instaPw)
        await page.get_by_role("button", name="Log in").first.click()
        await sleep(3 * random() + 1)
        await page.get_by_role("button", name="Not Now").click()
        await sleep(3 * random() + 1)
        await page.get_by_role("button", name="Not Now").click()
        await sleep(3 * random() + 1)

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

            await page.get_by_role("link", name="New post Create").click()
            await sleep(3 * random())

            async with page.expect_file_chooser() as fc_info:
                await page.get_by_role("button", name="Select from computer").click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(jpgPath)
            await sleep(3)
            await page.get_by_role("button", name="Select crop").nth(1).click()
            await sleep(3 * random())
            await page.get_by_role("button", name="Original Photo outline icon").click()
            await sleep(3 * random())
            await page.get_by_role("button", name="Next").click()
            await sleep(3 * random())
            await page.get_by_role("button", name="Next").click()
            await sleep(3 * random())
            await page.get_by_placeholder("Write a caption...").click()
            await sleep(3 * random())
            await page.get_by_placeholder("Write a caption...").fill("This is the way")
            await sleep(3 * random())
            await page.get_by_role("button", name="Share").click()
            await sleep(3 * random())

        # ---------------------
        await context.close()
        await browser.close()


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
        when = when.isoformat()
        if when not in self._schedule:
            self._schedule[when] = []
        self._schedule[when].append(asdict(content))
        self.write()

    def shiftSchedule(self, startDate=None):
        startDate = startDate if startDate is not None else datetime.utcnow()
        minDate = datetime.fromisoformat(min(self._schedule.keys()))
        dateDelta = startDate - minDate
        newSchedule = {
            (datetime.fromisoformat(key) + dateDelta).isoformat(): content
            for key, content in self._schedule.items()}
        self._schedule = newSchedule

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

    async def postContent(self, contentToPost):
        contentToPost = Content(**contentToPost)
        await self.post_content(contentToPost)
        self.contentSchedule.syncSchedule()

    async def on_ready(self):
        print(f"Logged on as {self.user}!")
        print("Starting schedule loop...")
        while True:
            now = datetime.utcnow().isoformat()
            try:
                for contentToPost in self.contentSchedule.contentToPost():
                    await self.postContent(contentToPost[0])
            except IndexError:
                print("No content to post")

            print("Sleeping for a day")
            await sleep(30)

    async def retrieve_attachments(self, message):
        urls = []
        for attachment in message.attachments:
            filename = attachment.filename
            if filename.split('.')[-1] in ['jpg', 'png', 'gif']:
                path = f"./imageCache/discourdian_{attachment.filename}"
                await attachment.save(path)
                urls.append(path)
        return urls

    def cleanImageCache(self):
        cacheContents = [f for f in os.listdir('./imageCache') if not os.path.isfile(f)]
        for when, content in self.contentSchedule._schedule.items():
            pass

    async def schedule_content(self, message):
        urls = await self.retrieve_attachments(message)
        content = Content(imageUrls=urls, caption=message.content)
        contentDate = self.contentSchedule.lastScheduled + timedelta(days=1, hours=32  * random())

        self.contentSchedule.schedule(when=contentDate, content=content)
        print(f"Content scheduled for: {contentDate}")

    async def post_content(self, content):
        print(f"Posting content: {content}...")

        try:
            postToReddit(content)
        except:
            print(f"Failed to post to Reddit: {format_exc()}")

        try:
            postToTwitter(content)
        except:
            print(f"Failed to post to Twitter: {format_exc()}")

        try:
            await postToInstagram(content)
        except:
            print(f"Failed to post to Instagram: {format_exc()}")

        try:
            postToActivityStream(content)
        except:
            print(f"Failed to post to Activity Stream: {format_exc()}")

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

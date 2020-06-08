import discord
from discord.ext import commands
from util.logger import logger
from util.wiki import *
import requests, json
import re
from urllib.parse import quote
from pyquery import PyQuery as pq

titleParams = {**baseParams, 'list':'search', 'srwhat':'title', 'srsearch':'role'}
pageParams = {**baseParams, 'prop':'categories|revisions', 'rvprop':'content', 'titles':'title'}

class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='role', aliases=['char'], description='Search for a "Blood on the Clocktower" role', help='Search for a "Blood on the Clocktower" role')
    async def role(self, ctx, *, role):
        role = role.lower()
        if role == '':
            return
        try:
            page = self.getPage(role)
            embed = self.getEmbed(page, ctx)
        except ValueError:
            embed = discord.Embed(title='Error', description=f'No roles matched `{role}`.', color=colors['Error'])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 503:
                embed = discord.Embed(title='Error', description= 'Wiki is currently offline. Please try again later.', color=colors['Error'])
            else:
                return
        await ctx.send('', embed=embed)

    def getPage(self, role):
        r = requests.get(url=apiUrl, params={**titleParams, 'srsearch':role})
        if r.status_code != requests.codes.ok:
            r.raise_for_status()
        data = r.json()['query']['search']
        if len(data) == 0:
            raise ValueError("not found")
        title = data[0]['title']
        r = requests.get(url=apiUrl, params={**pageParams, 'titles':title})
        data = r.json()['query']
        if not '-1' in data:
            page = data['pages'][next(iter(data['pages'].keys()))]
            return page

    def getEmbed(self, page, ctx):
        title = page['title']
        team = 'no team'
        edition = 'no edition'
        for category in page['categories']:
            t = category['title']
            if t in colors.keys():
                color = colors[t]
                team = t.replace('Category:', '')
            else:
                edition = t.replace('Category:', '')
        d = pq(page['revisions'][0]['*'])
        content = re.sub(r'==.*?==', '###', d('.columns').text(), re.IGNORECASE)
        content = re.sub(r'[\n\t]', '', content, re.IGNORECASE)
        content = content.split('###')
        description = f'**{edition}/{team}**\n'
        description += content[0]
        description += '```' + content[1][1:-2] + '```'
        image = re.findall(r'\[\[File:(.*?)\|', d('.columns').text())[0]
        footer = f"Use {ctx.prefix}help to get a list of available commands."
        embed = discord.Embed(title=title, description=description, url=wikiUrl+quote(title), color=color, footer=footer)
        embed.set_thumbnail(url=imageUrl+image)
        return embed

def setup(bot):
    bot.add_cog(Roles(bot))

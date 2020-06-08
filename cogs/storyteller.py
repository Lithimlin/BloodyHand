import discord
from discord.ext import commands
from util.logger import logger
from util.wiki import *
import requests, json
import random
from urllib.parse import quote
from pyquery import PyQuery as pq
from functools import reduce

editionsParams = {**baseParams, 'list':'allcategories', 'acprop':'size', 'aclimit':'50'}
rolesParams = {**baseParams, 'list':'categorymembers', 'cmtitle':'edition', 'cmlimit':'100'}
pageParams = {**baseParams, 'prop':'categories', 'pageids':'id'}

teams = [team for team in colors.keys()]
editions = ['Trouble Brewing', 'Sects & Violets', 'Bad Moon Rising']
residentsDict = {5:[3,0,1,1], 6:[3,1,1,1], 7:[5,0,1,1], 8:[5,1,1,1], 9:[5,2,1,1], 10:[7,0,2,1], 11:[7,1,2,1], 12:[7,2,2,1], 13:[9,0,3,1], 14:[9,1,3,1], 15:[9,2,3,1]}
statusEmojis = {'yes':'✅', 'no':'❌'}
numEmojis = {1:'1️⃣', 2:'2️⃣', 3:'3️⃣', 4:'4️⃣', 5:'5️⃣', 6:'6️⃣', 7:'7️⃣', 8:'8️⃣', 9:'9️⃣', 0:'0️⃣'}

class Storyteller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='list-editions', aliases=['editions'], description='List the official "Blood on the Clocktower" editions', help='List the official editions')
    async def list_sets(self, ctx):
        r = requests.get(url=apiUrl, params=editionsParams)
        categories = r.json()['query']['allcategories']
        categories = [c['*'] for c in categories if c['pages'] > 20 and c['*'] not in types]

        print(categories)
        print(r.url)

    @commands.command(name='setup', aliases=['new-game'], description='Setup a new game of "Blood on the Clocktower".', help='Setup a new game.')
    @commands.guild_only()
    async def setup_game(self, ctx):
        teller = ctx.message.author
        if teller.voice == None:
            embed = discord.Embed(title='Error', color=colors['Error'])
            embed.add_field(value="You must be in a voice channel to do this.", name='Please join a voice channel.')
            await ctx.send(embed=embed)
            return
        vc = teller.voice.channel
        players = [m for m in vc.members if m!=teller]
        p_names = [p.nick if p.nick else p.name for p in players]
        print(p_names)
        embed = discord.Embed(title="Players")
        if len(players) < 5:
            embed.add_field(name="Sorry.", value='There not enough players to play.')
            embed.color = colors['Error']
            await ctx.send(embed=embed)
            return
        embed.add_field(name=f"Do you want to play with these {len(p_names)} players:", value="```\n" + '\n'.join(p_names) + "```")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(statusEmojis['yes'])
        await msg.add_reaction(statusEmojis['no'])
        def check(r, u):
            return r.message.id == msg.id and r.emoji in statusEmojis.values() and u == teller

        reaction, _ = await self.bot.wait_for('reaction_add', check=check)
        if reaction.emoji == statusEmojis['no']:
            return
        embed = discord.Embed(title="Edition")
        embed.add_field(name="Which of these editions do you want to use?", value="```\n" + '\n'.join([f'{i+1}: {e}' for i,e in enumerate(editions+['Custom (not supported)'])]) + "```")
        msg = await ctx.send(embed=embed)
        selection = {}
        for i in range(1, len(editions)+2):
            await msg.add_reaction(numEmojis[i])
            selection[numEmojis[i]] = i
        def check(r, u):
            return r.message.id == msg.id and r.emoji in selection.keys() and u == teller

        reaction, _ = await self.bot.wait_for('reaction_add', check=check)
        if selection[reaction.emoji] > len(editions):
            await ctx.send("Sorry, I cannot help you then.")
            return
        edition = editions[selection[reaction.emoji]-1]
        roles = self.getRoles(edition)
        roles = self.sortedGroups(roles)
        if len(players) > 15:
            travelers = self.getRoles('Travelers')
        residents = residentsDict[len(players)]
        text = f"Please select {residents[0]} Townsfolk,"
        if residents[1] > 0:
            text += f"  {residents[1]} Outsiders,"
        text += f"{residents[2]} Minions, and {residents[3]} Demons:\n"
        embed = discord.Embed(title=text)
        i = 1
        for team, teamroles in roles.items():
            if team == 'Category:Outsiders' and residents[1] == 0:
                continue
            valueStr = "```\n"
            teamDict = {}
            for teamrole in teamroles:
                valueStr += f"{i}: {teamrole}\n"
                teamDict[i]=teamrole
                i += 1
            valueStr += "```"
            embed.add_field(name=team.replace('Category:', ''), value=valueStr)
            roles[team] = teamDict
        if len(players) > 15:
            for traveler in travelers:
                valueStr = f"{i}: {traveler}"
                travelers[traveler] = i
                i += 1
            embed.add_field(name='Travelers', value=valueStr)
            roles['Category:Travelers'] = travelers
        embed.set_footer(text='In your next message, please list the indices of the roles you want to include in the game')
        await ctx.send(embed=embed)
        print(roles)
        selected = []
        while True:
            msg = await self.bot.wait_for('message', check=lambda m: m.author == teller)
            content = msg.content.replace(',', '').split(' ')
            embed = discord.Embed(title='Roles', color=colors['Error'], footer="Please try again")
            try:
                townsfolk = [roles['Category:Townsfolk'][int(idx)] for idx in content if int(idx) in roles['Category:Townsfolk'].keys()]
                if residents[1] == 0:
                    outsiders = []
                else:
                    outsiders = [roles['Category:Outsiders'][int(idx)] for idx in content if int(idx) in roles['Category:Outsiders'].keys()]
                minions = [roles['Category:Minions'][int(idx)] for idx in content if int(idx) in roles['Category:Minions'].keys()]
                demons = [roles['Category:Demons'][int(idx)] for idx in content if int(idx) in roles['Category:Demons'].keys()]
            except ValueError:
                embed.add_field(name='Error', value='The indices must be numbers')
                await ctx.send(embed=embed)
                continue
            if sum(residents) == len(content):
                if len(townsfolk) == residents[0] and len(outsiders) == residents[1] and len(minions) == residents[2] and len(demons) == residents[3]:
                    selected = townsfolk + outsiders + minions + demons
                    break
                else:
                    embed.add_field(name='Error', value='The number of roles was incorrect')
                    await ctx.send(embed=embed)
                    continue
            embed.add_field(name='Error', value='The number of indices does not match the number of roles to be selected')
            await ctx.send(embed=embed)
        random.shuffle(selected)
        print(selected)
        guild = ctx.message.guild
        nums = []
        blackPerms = discord.PermissionOverwrite(read_messages=False)
        readPerms = discord.PermissionOverwrite(read_messages=True)
        if 'session' not in [c.name.lower() for c in guild.categories]:
            await guild.create_category('Session')
        cat = [c for c in guild.categories if c.name.lower() == 'session'][0]
        _, dPerms = cat.overwrites_for(guild.default_role).pair()
        if not dPerms.read_messages:
            await cat.set_permissions(guild.default_role, read_messages=False)

        for channel in cat.text_channels:
            await channel.delete()

        for player, name in zip(players, p_names):
            while True:
                n = int(random.random()*100)
                if n not in nums:
                    break
            if ' - ' in name:
                name = name.split(' - ')[1]
            name = f"{n:02d} - {name}"
            await player.edit(nick=name)
            channel = await cat.create_text_channel(selected.pop(),
                        overwrites={guild.default_role:blackPerms,
                                    player:readPerms,
                                    teller:readPerms,
                                    self.bot.user:readPerms})
        await ctx.send(embed=discord.Embed(title='Done'))



    def getRoles(self, edition):
        r = requests.get(url=apiUrl, params={**rolesParams, 'cmtitle':'Category:'+edition})
        data = r.json()['query']['categorymembers']
        roles = {role['title']:role['pageid'] for role in data}
        pages = {}
        for chunk in self.chunks(roles.values(), 5):
            r = requests.get(url=apiUrl, params={**pageParams, 'pageids':'|'.join([str(roleID) for roleID in chunk])})
            s_pages = r.json()['query']['pages']
            pages = {**pages, **s_pages}
        for role in roles.keys():
            categories = pages[str(roles[role])]['categories']
            team = [c['title'] for c in categories if c['title'] in teams][0]
            roles[role]=team
        return roles

    def chunks(self, lst, n):
        lst = list(lst)
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    def sortedGroups(self, dct):
        v = dict()
        for key, val in dct.items():
            if val not in v:
                v[val]=[]
            v[val].append(key)
        for key, val in v.items():
            v[key] = sorted(val)
        return v

def setup(bot):
    bot.add_cog(Storyteller(bot))

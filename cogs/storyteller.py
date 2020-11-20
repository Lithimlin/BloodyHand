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
residentsDict = {5:[3,0,1,1], 6:[3,1,1,1], 7:[5,0,1,1], 8:[5,1,1,1], 9:[5,2,1,1], 10:[7,0,2,1], 11:[7,1,2,1], 12:[7,2,2,1], 13:[9,0,3,1], 14:[9,1,3,1], 15:[9,2,3,1]}
statusEmojis = {'yes':'✅', 'no':'❌'}
numEmojis = {1:'1️⃣', 2:'2️⃣', 3:'3️⃣', 4:'4️⃣', 5:'5️⃣', 6:'6️⃣', 7:'7️⃣', 8:'8️⃣', 9:'9️⃣', 0:'0️⃣'}
pmEmojis = {'+':'➕', '-':'➖'}

class Storyteller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='list-editions', aliases=['editions'], description='List the official "Blood on the Clocktower" editions', help='List the official editions')
    async def list_sets(self, ctx):
        editions = self.getEditions()
        embed = discord.Embed(title='Editions', value="These are the official editions:\n```\n" + '\n'.join(editions) + "```")

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
        editions = self.getEditions()
        embed.add_field(name="Which of these editions do you want to use?", value="```\n" + '\n'.join([f'{i+1}: {e}' for i,e in enumerate(editions+['Custom (not supported)'])]) + "```")
        msg = await ctx.send(embed=embed)
        selection = await self.addNumReactions(msg, len(editions)+2)
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
            #TODO: get Travelers!!
        residents = residentsDict[len(players)].copy()
        embed = discord.Embed(title="Demon", color=colors['Category:Demons'])
        embed.add_field(name="Please select your demon:", value="```\n" + '\n'.join([f"{i+1}: {d}" for i,d in enumerate(roles['Demon'])]) + "```")
        msg = await ctx.send(embed=embed)
        selection = await self.addNumReactions(msg, len(roles['Demon'])+1)
        def check(r, u):
            return r.message.id == msg.id and r.emoji in selection.keys() and u == teller
        reaction, _ = await self.bot.wait_for('reaction_add', check=check)
        demon = roles['Demon'][selection[reaction.emoji]-1]

        if demon == "Fang Gu":
            residents[1] += 1
            residents[0] -= 1
        if demon == "Vigormortis":
            residents[1] -= 1
            residents[0] += 1

        selected = [demon]

        embed = discord.Embed(title="Minions", color=colors['Category:Minions'])
        embed.set_footer(text='In your next message, please list the indices of the Minions you want to include in the game')
        minionStr = ""
        minions = {}
        for i, minion in enumerate(roles['Minion']):
            minionStr += f"{i+1}: {minion}\n"
            minions[i+1] = minion
        embed.add_field(name=f"Please select {residents[2]} Minions:", value="```\n" + minionStr + "```")
        await ctx.send(embed=embed)
        while True:
            msg = await self.bot.wait_for('message', check=lambda m: m.author == teller)
            content = msg.content.replace(',', '').split(' ')
            embed = discord.Embed(title='Minions', color=colors['Error'], footer="Please try again")
            if len(content) != residents[2]:
                embed.add_field(name='Error', value='The number of indices does not match the number of roles to be selected')
                await ctx.send(embed=embed)
                continue
            try:
                minions = [minions[int(idx)] for idx in content]
                break
            except KeyError:
                embed.add_field(name='Error', value='Incorrect index')
            except ValueError:
                embed.add_field(name='Error', value='The indices must be numbers')
                await ctx.send(embed=embed)
                continue

        if "Baron" in minions:
            residents[1] += 2
            residents[0] -= 2
        if "Godfather" in minions:
            embed = discord.Embed(title='Godfather', value='Do you want to add or remove an outsider?', color=colors['Category:Minions'])
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(pmEmojis['+'])
            await msg.add_reaction(pmEmojis['-'])
            def check(r, u):
                return r.message.id == msg.id and r.emoji in pmEmojis.values() and u == teller
            reaction, _ = await self.bot.wait_for('reaction_add', check=check)
            if reaction.emoji == pmEmojis['+']:
                residents[1] += 1
                residents[0] -= 1
            else:
                residents[1] -= 1
                residents[0] += 1

        selected += minions
        if residents[1] < 0:
            residents[0] += residents[1]
            residents[1] = 0

        text = f"Please select {residents[0]} Townsfolk"
        if residents[1] > 0:
            plural = 's' if residents[1] > 1 else ''
            text += f"and  {residents[1]} Outsider{plural}"
        text += ':'
        embed = discord.Embed(title=text)
        i = 1
        valueStr = "```\n"
        teamDict = {}
        for role in roles['Townsfolk']:
            valueStr += f"{i}: {role}\n"
            teamDict[i]=role
            i += 1
        valueStr += "```"
        embed.add_field(name="Townsfolk", value=valueStr)
        roles['Townsfolk'] = teamDict

        if residents[1] > 0:
            valueStr = "```\n"
            teamDict = {}
            for role in roles['Outsider']:
                valueStr += f"{i}: {role}\n"
                teamDict[i]=role
                i += 1
            valueStr += "```"
            embed.add_field(name="Outsiders", value=valueStr)
            roles['Outsider'] = teamDict

        if len(players) > 15:
            for traveler in travelers:
                valueStr = f"{i}: {traveler}"
                travelers[traveler] = i
                i += 1
            embed.add_field(name='Travelers', value=valueStr)
            roles['Traveler'] = travelers
            #TODO!!
        embed.set_footer(text='In your next message, please list the indices of the roles you want to include in the game')
        await ctx.send(embed=embed)
        while True:
            msg = await self.bot.wait_for('message', check=lambda m: m.author == teller)
            content = msg.content.replace(',', '').split(' ')
            embed = discord.Embed(title='Roles', color=colors['Error'], footer="Please try again")
            try:
                townsfolk = [roles['Townsfolk'][int(idx)] for idx in content if int(idx) in roles['Townsfolk'].keys()]
                if residents[1] == 0:
                    outsiders = []
                else:
                    outsiders = [roles['Outsider'][int(idx)] for idx in content if int(idx) in roles['Outsider'].keys()]
            except ValueError:
                embed.add_field(name='Error', value='The indices must be numbers')
                await ctx.send(embed=embed)
                continue
            if sum(residents) == (len(content) + len(selected)):
                if len(townsfolk) == residents[0] and len(outsiders) == residents[1]:
                    selected += townsfolk + outsiders
                    break
                else:
                    embed.add_field(name='Error', value='The number of roles was incorrect')
                    await ctx.send(embed=embed)
                    continue
            embed.add_field(name='Error', value='The number of indices does not match the number of roles to be selected')
            await ctx.send(embed=embed)

        if "Drunk" in selected:
            drunk = None
            embed = discord.Embed(title='Drunk', color=colors['Category:Outsiders'])
            valueStr = "```\n"
            for i, role in roles['Townsfolk'].items():
                valueStr += f"{i}: {role}\n"
            valueStr += "```"
            embed.add_field(name='Please select a Townsfolk for the Drunk', value=valueStr)
            await ctx.send(embed=embed)
            while True:
                msg = await self.bot.wait_for('message', check=lambda m: m.author == teller)
                embed = discord.Embed(title='Drunk', color=colors['Error'], footer="Please try again")
                try:
                    idx = int(msg.content.strip())
                except ValueError:
                    embed.add_field(name='Error', value='The index must be a number')
                    await ctx.send(embed=embed)
                    continue
                try:
                    drunk = roles['Townsfolk'][idx]
                    break
                except KeyError:
                    embed.add_field(name='Error', value='The index must match a Townsfolk')
                    await ctx.send(embed=embed)
                    continue
            selected.remove("Drunk")
            selected.append(drunk)

        if "Lunatic" in selected:
            embed = discord.Embed(title='Lunatic', color=colors['Category:Outsiders'])
            embed.add_field(name='Please select a Demon for the lunatic', value="```\n" + '\n'.join([f"{i+1}: {d}" for i,d in enumerate(roles['Demon'])]) + "```")
            msg = await ctx.send(embed=embed)
            selection = await self.addNumReactions(msg, len(roles['Demon'])+1)
            def check(r, u):
                return r.message.id == msg.id and r.emoji in selection.keys() and u == teller
            reaction, _ = await self.bot.wait_for('reaction_add', check=check)
            lunatic = roles['Demon'][selection[reaction.emoji]-1]
            selected.remove("Lunatic")
            selected.append(lunatic)

        #z_players = dict(zip(players, p_names))
        random.shuffle(selected)
        guild = ctx.message.guild
        nums = []
        blackPerms = discord.PermissionOverwrite(read_messages=False)
        readPerms = discord.PermissionOverwrite(read_messages=True)

        if 'session' not in [c.name.lower() for c in guild.categories]:
            await guild.create_category('Session')
        cat = [c for c in guild.categories if c.name.lower() == 'session'][0]
        await cat.set_permissions(self.bot.user, read_messages=True)
        await cat.set_permissions(teller, read_messages=True)
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
            nums.append(n)
            channel = await cat.create_text_channel(selected.pop(),
                        overwrites={guild.default_role:blackPerms,
                                    player:readPerms,
                                    teller:readPerms,
                                    self.bot.user:readPerms})
        await ctx.send(embed=discord.Embed(title='Done'))


    def getRoles(self, edition):
        r = requests.get(rolesUrl)
        data = r.json()
        roles = {role['name']:role['roleType'].title() for role in data if edition in role['version']}
        return roles

    def getEditions(self):
        r = requests.get(rolesUrl)
        editions = []
        for role in r.json():
            edition = role['version'].split('-')[1].strip()
            if edition not in editions:
                editions.append(edition)
        return editions

    async def addNumReactions(self, msg, max):
        selection = {}
        for i in range(1, max):
            await msg.add_reaction(numEmojis[i])
            selection[numEmojis[i]] = i
        return selection

    def sortedGroups(self, dct):
        v = dict()
        for key, val in dct.items():
            if val not in v:
                v[val]=[]
            v[val].append(key)
        for key, val in v.items():
            v[key] = sorted(val)
        return v

    def getNightOrder(self):
        r = requests.get(orderUrl)
        first = r.json()['firstNight']
        other = r.json()['otherNight']
        first = {b:a for a,b in enumerate(first)}
        other = {b:a for a,b in enumerate(other)}
        return first, other


def setup(bot):
    bot.add_cog(Storyteller(bot))

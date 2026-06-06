import discord
from discord import app_commands
import sqlite3
import asyncio
import os

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

db = sqlite3.connect("invites.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS invites (
    inviter_id INTEGER PRIMARY KEY,
    total_invites INTEGER DEFAULT 0,
    left_members INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS joined_members (
    member_id INTEGER PRIMARY KEY,
    inviter_id INTEGER
)
""")

db.commit()

guild_invites = {}

@client.event
async def on_ready():
    print(f"Connecté en tant que {client.user}")

    for guild in client.guilds:
        try:
            guild_invites[guild.id] = await guild.invites()
            print(f"Invitations chargées : {guild.name}")
        except:
            print(f"Impossible de lire les invitations de {guild.name}")

    synced = await tree.sync()
    print(f"{len(synced)} commandes synchronisées")

@client.event
async def on_member_join(member):

    print(f"JOIN : {member}")

    await asyncio.sleep(2)

    guild = member.guild

    try:
        new_invites = await guild.invites()
    except:
        return

    old_invites = guild_invites.get(guild.id, [])

    inviter = None

    for new_invite in new_invites:
        for old_invite in old_invites:

            if (
                new_invite.code == old_invite.code
                and new_invite.uses > old_invite.uses
            ):
                inviter = new_invite.inviter
                break

        if inviter:
            break

    guild_invites[guild.id] = new_invites

    if inviter:

        cursor.execute("""
        INSERT OR IGNORE INTO invites
        (inviter_id,total_invites,left_members)
        VALUES (?,0,0)
        """, (inviter.id,))

        cursor.execute("""
        UPDATE invites
        SET total_invites = total_invites + 1
        WHERE inviter_id = ?
        """, (inviter.id,))

        cursor.execute("""
        INSERT OR REPLACE INTO joined_members
        (member_id, inviter_id)
        VALUES (?,?)
        """, (member.id, inviter.id))

        db.commit()

        print(f"{member} a rejoint grâce à {inviter}")

@client.event
async def on_member_remove(member):

    cursor.execute("""
    SELECT inviter_id
    FROM joined_members
    WHERE member_id = ?
    """, (member.id,))

    result = cursor.fetchone()

    if result:

        inviter_id = result[0]

        cursor.execute("""
        UPDATE invites
        SET left_members = left_members + 1
        WHERE inviter_id = ?
        """, (inviter_id,))

        db.commit()

@tree.command(name="stats", description="Voir tes invitations")
async def stats(interaction: discord.Interaction):

    cursor.execute("""
    SELECT total_invites, left_members
    FROM invites
    WHERE inviter_id = ?
    """, (interaction.user.id,))

    result = cursor.fetchone()

    if not result:
        await interaction.response.send_message(
            "Tu n'as encore invité personne."
        )
        return

    total, left = result

    embed = discord.Embed(
        title="📊 Tes statistiques",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Invitations",
        value=str(total),
        inline=False
    )

    embed.add_field(
        name="Membres partis",
        value=str(left),
        inline=False
    )

    await interaction.response.send_message(embed=embed)

@tree.command(name="leaderboard", description="Classement")
async def leaderboard(interaction: discord.Interaction):

    cursor.execute("""
    SELECT inviter_id,total_invites
    FROM invites
    ORDER BY total_invites DESC
    LIMIT 10
    """)

    rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message(
            "Aucune donnée."
        )
        return

    texte = ""

    for pos, row in enumerate(rows, start=1):

        inviter_id, total = row

        membre = interaction.guild.get_member(inviter_id)

        if membre:
            texte += f"#{pos} • {membre.display_name} → {total} invitations\n"

    embed = discord.Embed(
        title="🏆 Leaderboard",
        description=texte,
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed)

client.run(TOKEN)
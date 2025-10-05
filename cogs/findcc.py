import discord
from discord import app_commands
from discord.ext import commands
from config import CLASSES_TABLE as table

class FindCC(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="findcc", description="Find a class code using a role")
    @app_commands.describe(role="The role of the class")
    async def findcc(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer()

        response = table.scan(
            FilterExpression='roleID = :r',
            ExpressionAttributeValues={':r': str(role.id)}
        )
        items = response.get('Items', [])

        if items:
            class_code = items[0]["classCode"]
            await interaction.followup.send(f"✅ Class code for {role.mention} is: {class_code}")
        else:
            await interaction.followup.send(f"❌ No class found for role: {role.mention}")

# ---------------- Setup ----------------
async def setup(bot: commands.Bot):
    await bot.add_cog(FindCC(bot))
import asyncio
import re
import discord
from boto3.dynamodb.conditions import Attr
from discord import Interaction, Role, app_commands
from discord.ext import commands
from config import CLASSES_TABLE


class AddCC(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.table = CLASSES_TABLE

    def class_exists_by_role(self, role_id: str):
        try:
            response = self.table.scan(FilterExpression=Attr('roleID').eq(role_id))
            items = response.get('Items')
            return items[0] if items else None
        except Exception as e:
            print("Error scanning by role:", e)
            return None

    def class_exists_by_code(self, class_code: str):
        try:
            response = self.table.get_item(Key={'classCode': class_code})
            return response.get('Item')
        except Exception as e:
            print("Error getting class by code:", e)
            return None

    def add_class_to_dynamodb(self, class_code, channel_ids, role_id, title,
                              image_url, type_, number_of_assignments, server_id):
        try:

            channel_ids = [str(cid).strip() for cid in channel_ids if cid]

            self.table.put_item(
                Item={
                    "classCode": class_code,
                    "channelIDs": channel_ids,
                    "roleID": role_id,
                    "title": title,
                    "image_url": image_url,
                    "type": type_,
                    "numberOfAssignments": number_of_assignments,
                    "serverID": server_id
                }
            )
            return True
        except Exception as e:
            print("Error adding class to DynamoDB:", e)
            return False


    @app_commands.command(name="addcc", description="Add a class to the database")
    @app_commands.describe(
        class_code="Class code (e.g., CS101)",
        channel_ids="Comma-separated list of channel IDs or mentions (e.g. <#123>,<#456>)",
        role="Role for the class",
        title="Title of the class",
        image_url="Optional image URL",
        number_of_assignments="Number of assignments (optional)"
    )
    async def addcc(self, interaction: Interaction, class_code: str, channel_ids: str,
                    role: Role, title: str, image_url: str = "", number_of_assignments: int = 0):
        await interaction.response.defer()
        await asyncio.sleep(0)

        server_id = str(interaction.guild.id)
        class_code = class_code.strip()

        # ---------- Validation ----------
        if len(class_code) < 6 or len(class_code) > 7:
            await interaction.followup.send("❌ Class code should have 6 or 7 characters.")
            return

        existing_role_class = self.class_exists_by_role(str(role.id))
        if existing_role_class and existing_role_class['classCode'] != class_code:
            await interaction.followup.send(
                f"❌ This role already has a class code `{existing_role_class['classCode']}`."
            )
            return

        existing_code_class = self.class_exists_by_code(class_code)
        if existing_code_class and existing_code_class['roleID'] != str(role.id):
            await interaction.followup.send(
                f"❌ Class code `{class_code}` is already registered for another class."
            )
            return

        raw_ids = re.findall(r'\d{15,20}', channel_ids)
        valid_channels = []
        invalid_channels = []

        for cid in raw_ids:
            channel = interaction.guild.get_channel(int(cid))
            if channel:
                valid_channels.append(cid)
            else:
                invalid_channels.append(cid)

        if not valid_channels:
            await interaction.followup.send("❌ No valid channel IDs found in your input.")
            return

        success = self.add_class_to_dynamodb(
            class_code, valid_channels, str(role.id), title,
            image_url, "full_class", number_of_assignments, server_id
        )


        if success:
            embed = discord.Embed(
                title="✅ Class Added Successfully!",
                description=(
                    f"**Class Code:** `{class_code}`\n"
                    f"**Title:** {title}\n"
                    f"**Role:** {role.mention}\n"
                    f"**Channels:** {' '.join(f'<#{cid}>' for cid in valid_channels)}"
                ),
                color=discord.Color.green()
            )
            if image_url:
                embed.set_image(url=image_url)

            await interaction.followup.send(embed=embed)

            if invalid_channels:
                await interaction.followup.send(
                    f"⚠️ The following channels were not found: {', '.join(invalid_channels)}"
                )
        else:
            await interaction.followup.send("❌ Failed to add class to DynamoDB. Check logs.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AddCC(bot))

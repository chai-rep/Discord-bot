import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from config import HOMEWORK_TABLE, CLASSES_TABLE  

class HomeworkLogCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="loghw",
        description="Log homework submissions in a channel between two dates"
    )
    @app_commands.describe(
        class_code="Class code (e.g., 103456)",
        start_date="Start date YYYY/MM/DD",
        start_time="Start time HH:MM",
        end_date="End date YYYY/MM/DD",
        end_time="End time HH:MM",
        multiple_entries="Allow multiple entries from the same student?"
    )
    async def loghw(
        self,
        interaction: discord.Interaction,
        class_code: str,
        start_date: str,
        start_time: str,
        end_date: str,
        end_time: str,
        multiple_entries: bool = False
    ):
        await interaction.response.defer()

        # Convert start and end to datetime
        try:
            start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y/%m/%d %H:%M")
            end_dt = datetime.strptime(f"{end_date} {end_time}", "%Y/%m/%d %H:%M")
        except ValueError:
            await interaction.followup.send("❌ Invalid date/time format. Use YYYY/MM/DD HH:MM")
            return

        # Convert to milliseconds for DynamoDB filtering
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)

        # Get the class info from CLASSES_TABLE
        response = CLASSES_TABLE.get_item(Key={"classCode": class_code})
        class_info = response.get("Item")
        if not class_info:
            await interaction.followup.send(f"❌ Class code {class_code} not found")
            return

        channel_id = class_info["channelID"]

        # Query DynamoDB for homework submissions
        response = HOMEWORK_TABLE.scan(
            FilterExpression=(
                "classCode = :c AND channelID = :ch AND timestamp_ms BETWEEN :start AND :end"
            ),
            ExpressionAttributeValues={
                ":c": class_code,
                ":ch": channel_id,
                ":start": start_ms,
                ":end": end_ms
            }
        )

        submissions = response.get("Items", [])
        if not submissions:
            await interaction.followup.send("❌ No homework submissions found in this period")
            return

        # Filter duplicates if needed
        if not multiple_entries:
            seen_students = set()
            unique_submissions = []
            for s in submissions:
                if s["studentID"] not in seen_students:
                    unique_submissions.append(s)
                    seen_students.add(s["studentID"])
            submissions = unique_submissions

        # Build report
        report_lines = [
            f"👤 <@{s['studentID']}> | Assignment {s['assignmentNumber']} | {datetime.utcfromtimestamp(s['timestamp_ms']/1000).strftime('%Y-%m-%d %H:%M')}"
            for s in submissions
        ]

        report_text = "\n".join(report_lines)
        await interaction.followup.send(f"📋 Homework submissions for class {class_code}:\n{report_text}")

async def setup(bot: commands.Bot):
    await bot.add_cog(HomeworkLogCog(bot))

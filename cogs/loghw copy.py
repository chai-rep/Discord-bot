import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from config import HOMEWORK_TABLE  # DynamoDB table
from boto3.dynamodb.conditions import Key, Attr

class LogHomework(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------- Helper to parse date/time ----------------
    @staticmethod
    def parse_datetime(date_str: str, time_str: str) -> datetime:
        """Parse date and time strings to a datetime object"""
        return datetime.strptime(f"{date_str} {time_str}", "%Y/%m/%d %H:%M")

    # ---------------- Slash Command ----------------
    @app_commands.command(
        name="loghw",
        description="Log homework submissions in a channel for a class"
    )
    @app_commands.describe(
        class_code="Class code to log",
        start_date="Start date YYYY/MM/DD",
        start_time="Start time HH:MM",
        end_date="End date YYYY/MM/DD",
        end_time="End time HH:MM",
        multiple_entries="Allow multiple entries per student"
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

        # Parse start and end datetime
        try:
            start_dt = self.parse_datetime(start_date, start_time)
            end_dt = self.parse_datetime(end_date, end_time)
        except ValueError:
            await interaction.followup.send("❌ Invalid date/time format. Use YYYY/MM/DD HH:MM")
            return

        # Scan DynamoDB for the class and time range
        response = HOMEWORK_TABLE.scan(
            FilterExpression=Attr("classCode").eq(class_code) & 
                             Attr("timestamp").between(start_dt.isoformat(), end_dt.isoformat())
        )
        items = response.get("Items", [])
        if not items:
            await interaction.followup.send("❌ No homework submissions found in this period.")
            return

        # Handle multiple entries per student
        logged_students = {}
        for hw in items:
            student_id = hw["studentID"]
            if multiple_entries:
                logged_students.setdefault(student_id, []).append(hw)
            else:
                if student_id not in logged_students:
                    logged_students[student_id] = [hw]

        # Format the message
        message_lines = [f"📚 Homework log for class `{class_code}`:"]
        for student_id, submissions in logged_students.items():
            for hw in submissions:
                ts = hw.get("timestamp", "unknown")
                assignment = hw.get("assignmentNumber", "unknown")
                message_lines.append(f"- <@{student_id}> submitted assignment {assignment} at {ts}")

        # Send message
        await interaction.followup.send("\n".join(message_lines))


# ---------------- Setup ----------------
async def setup(bot: commands.Bot):
    await bot.add_cog(LogHomework(bot))
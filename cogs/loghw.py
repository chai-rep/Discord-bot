import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Attr
from config import HOMEWORK_TABLE, CLASSES_TABLE, LOG_CHANNELS

KST = timezone(timedelta(hours=9))

class LogHomework(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="loghw",
        description="Logs homework submissions between two KST times."
    )
    @app_commands.describe(
        class_code="Class code (e.g. 103456)",
        start_date="Start date (YYYY/MM/DD)",
        start_time="Start time (HH:MM in KST)",
        end_date="End date (YYYY/MM/DD)",
        end_time="End time (HH:MM in KST)",
        multiple_entries="Allow multiple submissions from the same student (true/false)",
        min_entries="Minimum number of submissions a student must have to appear in the logbook"
    )
    async def loghw(
        self,
        interaction: discord.Interaction,
        class_code: str,
        start_date: str,
        start_time: str,
        end_date: str,
        end_time: str,
        multiple_entries: bool = False,
        min_entries: int = 1  # New option
    ):
        await interaction.response.defer(thinking=True)

        # Convert KST to UTC timestamps
        try:
            start_kst = datetime.strptime(f"{start_date} {start_time}", "%Y/%m/%d %H:%M").replace(tzinfo=KST)
            end_kst = datetime.strptime(f"{end_date} {end_time}", "%Y/%m/%d %H:%M").replace(tzinfo=KST)
            start_ts = int(start_kst.astimezone(timezone.utc).timestamp())
            end_ts = int(end_kst.astimezone(timezone.utc).timestamp())
        except Exception:
            await interaction.followup.send("⚠️ Invalid date/time format.")
            return

        # Get class info
        class_data = CLASSES_TABLE.get_item(Key={"classCode": class_code}).get("Item")
        if not class_data:
            await interaction.followup.send(f"❌ Class `{class_code}` not found.")
            return

        title = class_data.get("title", "Unknown Class")
        role_id = class_data.get("roleID")
        image_url = class_data.get("image_url", "")

        # Query homework table
        response = HOMEWORK_TABLE.scan(
            FilterExpression=Attr("classCode").eq(class_code)
            & Attr("timestamp").between(start_ts, end_ts)
        )
        homeworks = response.get("Items", [])

        if not homeworks:
            await interaction.followup.send("❌ No homework submissions found.")
            return

        # Count submissions per student per assignment
        students_by_hw = {}
        submission_counts = {}  # Track total submissions per student
        for hw in homeworks:
            student_id = hw["studentID"]
            hw_number = hw.get("assignmentNumber", "unknown")
            students_by_hw.setdefault(hw_number, []).append(student_id)
            submission_counts[student_id] = submission_counts.get(student_id, 0) + 1

        # Apply min_entries filter
        for hw_number, students in students_by_hw.items():
            students_by_hw[hw_number] = [
                sid for sid in students if submission_counts[sid] >= min_entries
            ]

        # Remove empty homework entries after filter
        students_by_hw = {k: v for k, v in students_by_hw.items() if v}

        if not students_by_hw:
            await interaction.followup.send(f"❌ No students meet the minimum submission requirement of {min_entries}.")
            return

        # Build logbook message
        lines = [
            f"**LOGBOOK: {title}**",
            f"<@&{role_id}>" if role_id else "",
            datetime.now(KST).strftime("%A, %-d %B %Y"),
            datetime.now(KST).strftime("%Y년 %-m월 %-d일 %A"),
            ""
        ]

        for hw_number, student_ids in sorted(students_by_hw.items(), key=lambda x: int(x[0])):
            mentions = " ".join(f"<@{sid}>" for sid in student_ids)
            lines.append(f"**Homework {hw_number}:** {mentions}")

        # Determine target channel
        target_channel = interaction.channel
        if str(interaction.guild_id) in LOG_CHANNELS:
            target_channel_id = int(LOG_CHANNELS[str(interaction.guild_id)])
            target_channel = self.bot.get_channel(target_channel_id) or target_channel

        await target_channel.send("\n".join(lines))

        if image_url:
            embed = discord.Embed()
            embed.set_image(url=image_url)
            await target_channel.send(embed=embed)

        await interaction.followup.send(f"✅ Homework log posted in {target_channel.mention}")

async def setup(bot: commands.Bot):
    await bot.add_cog(LogHomework(bot))

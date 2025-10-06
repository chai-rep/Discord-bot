import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Attr
from config import HOMEWORK_TABLE, CLASSES_TABLE, LOG_CHANNELS  # Ensure CLASSES_TABLE + LOG_CHANNELS exist

KST = timezone(timedelta(hours=9))  # Korea Standard Time (UTC+9)


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
        multiple_entries="Allow multiple submissions from the same student (true/false)"
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
        await interaction.response.defer(thinking=True)

        # Convert user-provided KST times → UTC timestamps
        try:
            start_kst = datetime.strptime(f"{start_date} {start_time}", "%Y/%m/%d %H:%M").replace(tzinfo=KST)
            end_kst = datetime.strptime(f"{end_date} {end_time}", "%Y/%m/%d %H:%M").replace(tzinfo=KST)
            start_ts = int(start_kst.astimezone(timezone.utc).timestamp())
            end_ts = int(end_kst.astimezone(timezone.utc).timestamp())
        except Exception:
            await interaction.followup.send("⚠️ Invalid date/time format. Use YYYY/MM/DD HH:MM (24-hour KST).")
            return

        # Get class info (title, role, image_url)
        class_data = CLASSES_TABLE.get_item(Key={"classCode": class_code}).get("Item")
        if not class_data:
            await interaction.followup.send(f"❌ Class code `{class_code}` not found.")
            return

        title = class_data.get("title", "Unknown Class")
        role_id = class_data.get("roleID")
        image_url = class_data.get("image_url", "")

        # Query DynamoDB for homework within the date range
        response = HOMEWORK_TABLE.scan(
            FilterExpression=Attr("classCode").eq(class_code)
            & Attr("timestamp").between(start_ts, end_ts)
        )
        homeworks = response.get("Items", [])

        if not homeworks:
            await interaction.followup.send("❌ No homework submissions found in this time period.")
            return

        # Group homeworks by assignment number
        students_by_hw = {}
        seen_students = set()

        for hw in sorted(homeworks, key=lambda x: x["timestamp"], reverse=True):
            student_id = hw["studentID"]
            hw_number = hw.get("assignmentNumber", "unknown")

            if not multiple_entries and student_id in seen_students:
                continue

            students_by_hw.setdefault(hw_number, []).append(student_id)
            seen_students.add(student_id)

        # Sort homework numbers in ascending order (1, 2, 3, ...)
        sorted_hw = sorted(
            students_by_hw.items(),
            key=lambda x: int(x[0]) if str(x[0]).isdigit() else 999
        )

        # KST post date formatting
        now_kst = datetime.now(KST)
        date_str_eng = now_kst.strftime("%A, %-d %B %Y")
        date_str_kor = now_kst.strftime("%Y년 %-m월 %-d일 %A")

        role_mention = f"<@&{role_id}>" if role_id else ""
        header_lines = [
            f"**LOGBOOK: {title}**",
            f"{role_mention}",
            f"{date_str_eng}",
            f"{date_str_kor}",
            "",
        ]

        # Build homework list
        for hw_num, student_ids in sorted_hw:
            mentions = " ".join(f"<@{sid}>" for sid in student_ids)
            header_lines.append(f"**Homework {hw_num}:** {mentions}")

        # Determine which channel to post in
        server_id_str = str(interaction.guild_id)
        target_channel = None

        if server_id_str in LOG_CHANNELS:
            target_channel_id = int(LOG_CHANNELS[server_id_str])
            target_channel = self.bot.get_channel(target_channel_id)
            if not target_channel:
                try:
                    guild = self.bot.get_guild(interaction.guild_id)
                    target_channel = await guild.fetch_channel(target_channel_id)
                except Exception:
                    target_channel = None

        if not target_channel:
            target_channel = interaction.channel
            await interaction.followup.send("⚠️ Could not find the mapped log channel. Posting here instead.")

        # Send the logbook text, handling long messages
        log_message = "\n".join(header_lines)
        if len(log_message) > 2000:
            parts = [log_message[i:i + 2000] for i in range(0, len(log_message), 2000)]
            for part in parts:
                await target_channel.send(part)
        else:
            await target_channel.send(log_message)

        # Send image as a separate embed if available
        if image_url:
            embed = discord.Embed(color=discord.Color.blue())
            embed.set_image(url=image_url)
            await target_channel.send(embed=embed)

        await interaction.followup.send(f"✅ Homework log posted in {target_channel.mention}")


async def setup(bot: commands.Bot):
    await bot.add_cog(LogHomework(bot))

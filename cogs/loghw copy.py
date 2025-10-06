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
        description="Posts logbooks of hw logged between two KST times."
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

        #  Parse KST input
        try:
            start_kst = datetime.strptime(f"{start_date} {start_time}", "%Y/%m/%d %H:%M").replace(tzinfo=KST)
            end_kst = datetime.strptime(f"{end_date} {end_time}", "%Y/%m/%d %H:%M").replace(tzinfo=KST)
            start_ts = int(start_kst.astimezone(timezone.utc).timestamp())
            end_ts = int(end_kst.astimezone(timezone.utc).timestamp())
        except Exception:
            await interaction.followup.send("⚠️ Invalid date/time format. Use YYYY/MM/DD HH:MM (24-hour KST).")
            return

        # Fetch class info
        class_info_response = CLASSES_TABLE.scan(
            FilterExpression=Attr("classCode").eq(class_code)
        )
        class_items = class_info_response.get("Items", [])
        if not class_items:
            await interaction.followup.send(f"❌ No class found with code `{class_code}`.")
            return

        class_info = class_items[0]
        class_title = class_info.get("title", f"Class {class_code}")
        role_id = class_info.get("roleID", None)
        image_url = class_info.get("image_url", "").strip()

        # Query homework table
        response = HOMEWORK_TABLE.scan(
            FilterExpression=Attr("classCode").eq(class_code)
            & Attr("timestamp").between(start_ts, end_ts)
        )
        homeworks = response.get("Items", [])

        if not homeworks:
            await interaction.followup.send("❌ No homework submissions found in this time period.")
            return

        # Organize students by homework number
        students_by_hw = {}
        seen_students = set()

        for hw in sorted(homeworks, key=lambda x: x["timestamp"], reverse=True):
            student_id = hw["studentID"]
            hw_number = hw.get("assignmentNumber", "unknown")

            if not multiple_entries and student_id in seen_students:
                continue

            students_by_hw.setdefault(hw_number, []).append(student_id)
            seen_students.add(student_id)

        # Format Korean date
        now_kst = datetime.now(KST)
        weekday_korean = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        korean_date = f"{now_kst.year}년 {now_kst.month}월 {now_kst.day}일 {weekday_korean[now_kst.weekday()]}"

        # Role mention if available
        role_mention = f"<@&{role_id}>" if role_id else ""

        # Build log message
        lines = [
            f"📘 **LOGBOOK: {class_title}**",
            f"{role_mention}",
            f"{now_kst.strftime('%A, %d %B %Y')}",
            f"{korean_date}",
            "",
   
            ""
        ]

        for hw_num, student_ids in students_by_hw.items():
            mentions = " ".join(f"<@{sid}>" for sid in student_ids)
            lines.append(f"**Homework {hw_num}:** {mentions}")

        # Target channel
        server_id_str = str(interaction.guild_id)
        target_channel = None

        if server_id_str in LOG_CHANNELS:
            target_channel_id = int(LOG_CHANNELS[server_id_str])
            target_channel = self.bot.get_channel(target_channel_id)
            if target_channel is None:
                try:
                    guild = self.bot.get_guild(interaction.guild_id)
                    target_channel = await guild.fetch_channel(target_channel_id)
                except Exception:
                    target_channel = None

        if target_channel is None:
            target_channel = interaction.channel
            await interaction.followup.send("⚠️ Could not find mapped log channel, posting here instead.")

        # Send logbook text first
        await target_channel.send("\n".join(lines))

        # send image embed (if exists)
        if image_url and (image_url.startswith("http://") or image_url.startswith("https://")):
            embed = discord.Embed(color=0x2ecc71)
            embed.set_image(url=image_url)
            await target_channel.send(embed=embed)

        # Confirmation message
        await interaction.followup.send(f"✅ Homework log posted in {target_channel.mention}")


async def setup(bot: commands.Bot):
    await bot.add_cog(LogHomework(bot))

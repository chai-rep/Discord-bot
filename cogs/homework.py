from decimal import Decimal
import discord
from discord.ext import commands
from boto3.dynamodb.conditions import Attr
from datetime import datetime
from config import CLASSES_TABLE, HOMEWORK_TABLE, number_emojis

class HomeworkCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def get_name_of_emoji(emoji: str) -> str:
        mapping = {
            "1️⃣": "1", "2️⃣": "2", "3️⃣": "3", "4️⃣": "4", "5️⃣": "5",
            "6️⃣": "6", "7️⃣": "7", "8️⃣": "8", "9️⃣": "9", "🔟": "10",
        }
        return mapping.get(emoji)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return

        message = reaction.message

        # Check for number emoji added by user
        user_number_emoji = None
        for r in message.reactions:
            if str(r.emoji) in number_emojis:
                async for u in r.users():
                    if u.id == user.id:
                        user_number_emoji = str(r.emoji)
                        break
            if user_number_emoji:
                break

        # Check for purple check added by user
        user_has_purple_check = False
        for r in message.reactions:
            emoji_name = str(r.emoji).lower()
            if "purple" in emoji_name and "check" in emoji_name:
                async for u in r.users():
                    if u.id == user.id:
                        user_has_purple_check = True
                        break
            if user_has_purple_check:
                break

        # Only proceed if user added number + purple check
        if user_number_emoji and user_has_purple_check:
            # Map emoji to number
            assignment_number_str = self.get_name_of_emoji(user_number_emoji) or "manual"

            try:
                assignment_number = int(assignment_number_str)
            except ValueError:
                return  # invalid emoji, ignore

            # Lookup class
            channel_id = str(message.channel.id)
            response = CLASSES_TABLE.scan(
                FilterExpression=Attr('channelIDs').contains(channel_id)
            )
            items = response.get('Items', [])
            if not items:
                return

            class_info = items[0]
            class_code = class_info.get('classCode', 'unknown')

            # Get total assignments
            try:
                total_assignments = int(class_info.get('totalAssignments', 0))
            except (ValueError, TypeError):
                total_assignments = 0

            # Validate assignment number
            if total_assignments and assignment_number > total_assignments:
                # Do not save or react if invalid
                return

            # Convert timestamp to Decimal
            timestamp_unix = Decimal(str(int(datetime.utcnow().timestamp())))

            # Save to DynamoDB with poster's ID
            HOMEWORK_TABLE.put_item(
                Item={
                    "classCode": class_code,
                    "messageID": str(message.id),
                    "channelID": str(message.channel.id),
                    "studentID": str(message.author.id),
                    "timestamp": timestamp_unix,
                    "type": "homework",
                    "assignmentNumber": assignment_number
                }
            )

            # Add thumbs-up reaction
            await message.add_reaction("👍🏻")

async def setup(bot: commands.Bot):
    await bot.add_cog(HomeworkCog(bot))

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

        # Check for number emoji by this user
        user_number_emoji = None
        for r in message.reactions:
            if str(r.emoji) in number_emojis:
                async for u in r.users():
                    if u.id == user.id:
                        user_number_emoji = str(r.emoji)
                        break
            if user_number_emoji:
                break

        # Check for purple checkmark by this user
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

        # Only save if both are present
        if user_number_emoji and user_has_purple_check:
            assignment_number = self.get_name_of_emoji(user_number_emoji) or "manual"

            # Lookup class
            channel_id = str(message.channel.id)
            response = CLASSES_TABLE.scan(
                FilterExpression=Attr('channelIDs').contains(channel_id)
            )
            items = response.get('Items', [])
            if not items:
                print(f"❌ No class found for channel {channel_id}")
                return
            class_code = items[0]['classCode']

            # Save to DynamoDB
            item = {
                "classCode": class_code,
                "messageID": str(message.id),
                "channelID": str(message.channel.id),
                "studentID": str(user.id),
                "timestamp": datetime.utcnow().isoformat(),
                "type": "homework",
                "assignmentNumber": assignment_number
            }
            try:
                HOMEWORK_TABLE.put_item(Item=item)
                print(f"✅ Saved homework: {item}")
            except Exception as e:
                print(f"❌ Failed to save homework: {e}")
                return

            # React with thumbs up
            try:
                await message.add_reaction("👍🏻")
                print("✅ Added 👍🏻 reaction")
            except Exception as e:
                print(f"❌ Failed to add 👍🏻: {e}")

# Async setup
async def setup(bot: commands.Bot):
    await bot.add_cog(HomeworkCog(bot))

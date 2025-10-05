# homework_debug.py
import discord
from discord.ext import commands
from boto3.dynamodb.conditions import Attr
from config import CLASSES_TABLE, HOMEWORK_TABLE, number_emojis
from datetime import datetime

class HomeworkDebugCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- Helper ----------
    @staticmethod
    def get_name_of_emoji(emoji: str) -> str:
        mapping = {
            "1️⃣": "1", "2️⃣": "2", "3️⃣": "3", "4️⃣": "4", "5️⃣": "5",
            "6️⃣": "6", "7️⃣": "7", "8️⃣": "8", "9️⃣": "9", "🔟": "10",
        }
        return mapping.get(emoji)

    @staticmethod
    def save_homework_to_db(message: discord.Message, assignment_number: str, class_code: str):
        if not class_code or not message.id:
            print(f"❌ Missing keys: class_code={class_code}, messageID={message.id}")
            return

        item = {
            "classCode": class_code,
            "messageID": str(message.id),
            "channelID": str(message.channel.id),
            "studentID": str(message.author.id),
            "timestamp": datetime.utcnow().isoformat(),
            "type": "homework",
            "assignmentNumber": assignment_number
        }

        try:
            HOMEWORK_TABLE.put_item(Item=item)
            print(f"✅ Saved homework: {item}")
        except Exception as e:
            print(f"❌ Error saving homework: {e}")

    # ---------- Listener ----------
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        print(f"Reaction added: {reaction.emoji} by {user} in channel {reaction.message.channel.id}")

        # Ignore bot's own reactions
        if user.id == self.bot.user.id:
            print("Ignoring bot reaction")
            return

        # Fetch partial message if needed
        message = reaction.message
        if isinstance(message, discord.PartialMessage):
            try:
                message = await message.fetch()
                print(f"Fetched partial message {message.id}")
            except Exception as e:
                print(f"❌ Error fetching message: {e}")
                return

        channel_id = str(message.channel.id)
        emoji_name = str(reaction.emoji)
        clean_emoji_name = ''.join(c for c in emoji_name if not c.isdigit() and c != '_').lower()

        # Lookup class from BA-Class table
        try:
            response = CLASSES_TABLE.scan(
                FilterExpression=Attr('channelIDs').contains(channel_id)
            )
            items = response.get('Items', [])
            if not items:
                print(f"❌ No class found for channel {channel_id}")
                return
            class_code = items[0]['classCode']
            print(f"Class found: {class_code}")
        except Exception as e:
            print(f"❌ Error querying BA-Class: {e}")
            return

        # ---------- Purple checkmark ----------
        if clean_emoji_name == 'purplecheckmark':
            assignment_number = "manual"
            if message.reactions:
                first_emoji = str(next(iter(message.reactions)).emoji)
                num = self.get_name_of_emoji(first_emoji)
                if num:
                    assignment_number = num
            print(f"Purple checkmark detected. Assignment number: {assignment_number}")

            self.save_homework_to_db(message, assignment_number, class_code)

            # React with thumbs up
            try:
                await message.add_reaction('👍🏻')
                print("✅ Added 👍🏻 reaction")
            except Exception as e:
                print(f"❌ Failed to add 👍🏻: {e}")
            return

        # ---------- ⏭️ emoji ----------
        if emoji_name == '⏭️':
            print("⏭️ emoji detected, adding next batch of emojis")
            for e in number_emojis[10:30]:
                try:
                    await message.add_reaction(e)
                    print(f"Added emoji {e}")
                except Exception as e:
                    print(f"❌ Failed to add {e}: {e}")
            return

        # ---------- Number emoji ----------
        if emoji_name in number_emojis:
            print(f"Number emoji detected: {emoji_name}")
            try:
                await message.clear_reactions()
                await message.add_reaction(emoji_name)
                print(f"✅ Cleared and added {emoji_name}")
            except Exception as e:
                print(f"❌ Failed to react with {emoji_name}: {e}")

            assignment_number = self.get_name_of_emoji(emoji_name) or "manual"
            self.save_homework_to_db(message, assignment_number, class_code)
            return

        # ---------- Clear reactions ----------
        if emoji_name == '❗':
            print("❗ emoji detected, clearing reactions")
            try:
                await message.clear_reactions()
                print("✅ Cleared reactions")
            except Exception as e:
                print(f"❌ Failed to clear reactions: {e}")

# ---------- Async setup ----------
async def setup(bot: commands.Bot):
    await bot.add_cog(HomeworkDebugCog(bot))

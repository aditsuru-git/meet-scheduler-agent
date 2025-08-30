import discord
from discord.ext import commands
import os
import asyncio
import logging
from typing import Optional
from agent import chain

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
PREFIX = '!'
MAX_MESSAGE_LENGTH = 2000  # Discord's message limit

# Create bot instance with necessary intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(
    command_prefix=PREFIX, 
    intents=intents,
    case_insensitive=True,
    help_command=None  # Disable default help command
)

def process_schedule_request(messages_string: str) -> str:
    """
    Process the messages string using the AI chain
    
    Args:
        messages_string: Formatted chat history
    
    Returns:
        AI response for scheduling
    """
    try:
        response = chain.invoke({"chat_history": messages_string})
        
        # Ensure response isn't too long for Discord
        if len(response) > MAX_MESSAGE_LENGTH:
            response = response[:MAX_MESSAGE_LENGTH-50] + "\n\n*[Response truncated]*"
            
        return response
    except Exception as e:
        logger.error(f"Error in AI processing: {str(e)}")
        return "⚠️ Sorry, I encountered an error while analyzing the conversation. Please try again later."

@bot.event
async def on_ready():
    """Event triggered when bot is ready"""
    logger.info(f'Bot ready! Logged in as {bot.user.name} (ID: {bot.user.id})')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening, 
            name=f"{PREFIX}schedule meet"
        )
    )

@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler"""
    logger.error(f'An error occurred in event {event}', exc_info=True)

@bot.event 
async def on_command_error(ctx, error):
    """Global command error handler"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `!schedule meet`")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏰ Please wait {error.retry_after:.1f} seconds before using this command again.")
    else:
        logger.error(f'Command error in {ctx.command}: {str(error)}', exc_info=True)
        await ctx.send("❌ An unexpected error occurred. The issue has been logged.")

@bot.command(name='schedule')
@commands.cooldown(1, 10, commands.BucketType.channel)  # 1 use per 10 seconds per channel
async def schedule_meet(ctx, action: Optional[str] = None):
    """
    Handle the !schedule meet command with improved error handling
    """
    
    if action != 'meet':
        await ctx.send("❌ Usage: `!schedule meet`")
        return
    
    # Show typing indicator
    async with ctx.typing():
        try:
            channel = ctx.channel
            
            # Fetch messages with timeout (compatible with Python 3.8+)
            messages = []
            try:
                async def fetch_messages():
                    msgs = []
                    async for message in channel.history(limit=20):
                        msgs.append(message)
                    return msgs
                
                messages = await asyncio.wait_for(fetch_messages(), timeout=5.0)
            except asyncio.TimeoutError:
                await ctx.send("⏰ Timeout while fetching messages. Please try again.")
                return
            
            if not messages:
                await ctx.send("❌ No messages found in this channel.")
                return
            
            # Reverse to chronological order
            messages.reverse()
            
            # Convert to required format
            messages_string = ""
            for message in messages:
                username = message.author.display_name or message.author.name
                content = message.content.strip()
                
                # Skip empty messages and very long messages
                if content and len(content) <= 500:  # Limit individual message length
                    # Sanitize content (remove potential sensitive info)
                    content = content.replace('@everyone', '@\u200beveryone').replace('@here', '@\u200bhere')
                    messages_string += f"{username}: {content}\n"
            
            messages_string = messages_string.rstrip('\n')
            
            if not messages_string:
                await ctx.send("❌ No valid messages found to process.")
                return
            
            # Log for debugging (without sensitive content)
            logger.info(f"Processing schedule request from {ctx.author} in {ctx.guild.name}#{ctx.channel.name}")
            
            # Process with AI
            try:
                response = process_schedule_request(messages_string)
            except Exception as e:
                logger.error(f"AI processing failed: {str(e)}")
                await ctx.send("⚠️ I'm having trouble analyzing the conversation right now. Please try again in a moment.")
                return
            
            # Send response
            if response:
                await channel.send(response)
            else:
                await ctx.send("⚠️ I couldn't generate a response. Please try again.")
                
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to read message history in this channel.")
        except discord.HTTPException as e:
            logger.error(f"Discord API error: {str(e)}")
            await ctx.send("❌ There was an issue communicating with Discord. Please try again.")
        except Exception as e:
            logger.error(f"Unexpected error in schedule_meet: {str(e)}", exc_info=True)
            await ctx.send("❌ An unexpected error occurred. The issue has been logged.")

@bot.command(name='ping')
@commands.cooldown(1, 5, commands.BucketType.user)
async def ping(ctx):
    """Health check command"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: {latency}ms",
        color=0x00ff00 if latency < 100 else 0xff6600 if latency < 300 else 0xff0000
    )
    await ctx.send(embed=embed)

@bot.command(name='help')
async def help_command(ctx):
    """Custom help command"""
    embed = discord.Embed(
        title="📅 Schedule Bot Help",
        description="I help you schedule meetings by analyzing your conversation!",
        color=0x3498db
    )
    embed.add_field(
        name="Commands",
        value=f"`{PREFIX}schedule meet` - Analyze recent messages and suggest meeting times\n`{PREFIX}ping` - Check bot status",
        inline=False
    )
    embed.add_field(
        name="How it works",
        value="I read the last 20 messages in the channel and use AI to suggest the best meeting times based on your discussion.",
        inline=False
    )
    embed.set_footer(text="Tip: Mention specific dates, times, and timezones for better results!")
    await ctx.send(embed=embed)

def validate_environment():
    """Validate required environment variables"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        return False
    
    # Check if we can import the agent
    try:
        from agent import chain
        return True
    except ImportError as e:
        logger.error(f"Failed to import agent: {e}")
        return False

async def main():
    """Main async function to run the bot"""
    
    if not validate_environment():
        return
    
    try:
        logger.info("Starting bot...")
        await bot.start(BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid bot token!")
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
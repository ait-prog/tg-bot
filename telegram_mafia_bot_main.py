# telegram_mafia_bot_main.py
"""
Main entry point for the Telegram Mafia Game Bot.
Sets up Telegram bot, initializes modules, and starts the application.
"""

import logging
import asyncio
from telegram.ext import Application
from telegram.error import TelegramError

# Import all modules
from telegram_mafia_config import BOT_TOKEN, LOG_LEVEL, LOG_FORMAT
from telegram_mafia_data import game_data
from telegram_mafia_bot_ui import PanelUpdater
from telegram_mafia_bot_handlers import setup_handlers
from telegram_mafia_game_logic import game_engine


class MafiaBotApplication:
    """Main application class for the Mafia Bot."""
    
    def __init__(self):
        self.application = None
        self.panel_updater = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def setup_logging(self):
        """Configure logging for the application."""
        logging.basicConfig(
            format=LOG_FORMAT,
            level=LOG_LEVEL,
            handlers=[
                logging.FileHandler('mafia_bot.log'),
                logging.StreamHandler()
            ]
        )
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('telegram').setLevel(logging.WARNING)
        self.logger.info("Logging configured successfully")
    
    def validate_config(self) -> bool:
        """Validate configuration and requirements."""
        if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            self.logger.error("Bot token not configured! Please set BOT_TOKEN in telegram_mafia_config.py or TELEGRAM_BOT_TOKEN environment variable")
            return False
        self.logger.info("Configuration validation passed")
        return True
    
    async def post_initialization(self, application: Application):
        """Setup background tasks after the application is initialized."""
        async def phase_timer_task():
            """Background task to handle phase timers."""
            while True:
                try:
                    active_games = game_data.get_active_games()
                    for chat_id in active_games:
                        if game_data.is_phase_expired(chat_id):
                            self.logger.info(f"Phase expired for game {chat_id}, advancing...")
                        
                            # Store current phase for proper announcements
                            game = game_data.get_game(chat_id)
                            if not game:
                                continue
                            
                            old_phase = game.phase
                        
                            # Advance the phase
                            game_engine.force_phase_advance(chat_id)
                        
                            # Get updated game state
                            game = game_data.get_game(chat_id)
                            if not game:
                                continue
                        
                            # Send phase transition announcements FIRST
                            if self.panel_updater:
                                await self.panel_updater.announce_phase_transition(chat_id)
                            
                                # Then update panel 
                                await self.panel_updater.update_panel(chat_id)
                            
                                # Send night prompts if it's now night phase
                                if game.phase == GamePhase.NIGHT:
                                    await self.panel_updater.send_night_prompts(chat_id)
                
                    await asyncio.sleep(5)  # Check every 5 seconds
                
                except Exception as e:
                    self.logger.error(f"Error in phase timer task: {e}")
                    await asyncio.sleep(10)  # Wait longer on error
    
        # Start the background task
        application.create_task(phase_timer_task())
        self.logger.info("Background tasks setup completed")

    def setup_bot(self) -> bool:
        """Initialize the Telegram bot and handlers."""
        try:
            # Create application with post_init hook for background tasks
            self.application = Application.builder().token(BOT_TOKEN).post_init(self.post_initialization).build()
            
            # Initialize panel updater
            self.panel_updater = PanelUpdater(self.application)
            
            # Connect panel updater to data manager
            game_data.set_panel_updater(self.panel_updater.update_panel)
            
            # Setup handlers
            setup_handlers(self.application, self.panel_updater)
            
            self.logger.info("Bot setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup bot: {e}")
            return False
    
    def run(self):
        """Run the bot application."""
        self.logger.info("Starting Mafia Bot...")
        
        if not self.validate_config():
            return
        
        if not self.setup_bot():
            return
        
        try:
            self.logger.info("Bot is now running! Press Ctrl+C to stop.")
            self.application.run_polling(
                allowed_updates=['message', 'callback_query'],
                drop_pending_updates=True
            )
        except (KeyboardInterrupt, SystemExit):
            self.logger.info("Received stop signal, shutting down...")
        except Exception as e:
            self.logger.error(f"Error running bot: {e}")
        finally:
            # Run cleanup
            try:
                asyncio.run(self.cleanup())
            except Exception as cleanup_error:
                self.logger.error(f"Error during cleanup: {cleanup_error}")

    async def cleanup(self):
        """Clean up resources before shutdown."""
        if not self.application:
            return
            
        try:
            self.logger.info("Cleaning up...")
            
            # Notify active games about shutdown
            active_games = game_data.get_active_games()
            if active_games:
                shutdown_message = "🛑 **Bot is shutting down!** Current games will be lost."
                tasks = []
                for chat_id in active_games:
                    try:
                        task = self.application.bot.send_message(
                            chat_id=chat_id, 
                            text=shutdown_message,
                            parse_mode='Markdown'
                        )
                        tasks.append(task)
                    except Exception as e:
                        self.logger.warning(f"Failed to notify chat {chat_id} about shutdown: {e}")
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            
            # Shutdown the application
            await self.application.shutdown()
            self.logger.info("Cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    bot_app = MafiaBotApplication()
    bot_app.setup_logging()
    
    try:
        bot_app.run()
    except Exception as e:
        logging.critical(f"A fatal unhandled error occurred: {e}", exc_info=True)
    finally:
        logging.info("Mafia Bot has shut down.")


if __name__ == "__main__":
    main()
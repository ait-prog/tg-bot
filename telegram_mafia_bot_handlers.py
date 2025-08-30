# telegram_mafia_bot_handlers.py
"""
Telegram command and callback handlers for the Telegram Mafia Game Bot.
Handles all user interactions and command processing.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.error import TelegramError

from telegram_mafia_data import game_data, GamePhase
from telegram_mafia_game_logic import game_engine
from telegram_mafia_utils import create_player_dict, validate_player_count
from telegram_mafia_config import MIN_PLAYERS, MAX_PLAYERS

logger = logging.getLogger(__name__)


class MafiaHandlers:
    """Container for all Telegram handlers."""

    def __init__(self, panel_updater):
        self.panel_updater = panel_updater
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _send_normal_start_message(self, update: Update):
        """Send normal start message."""
        await update.message.reply_text(
            "🎭 **Welcome to Mafia Bot!** 🎭\n\n"
            "Commands:\n"
            "• `/newgame` - Create a new game lobby\n"
            "• `/join` - Join the current game\n"
            "• `/leave` - Leave the current game\n"
            "• `/startgame` - Start the game (needs 5+ players)\n"
            "• `/status` - Show current game status\n"
            "• `/endgame` - End the current game\n\n"
            "ℹ️ This bot works best in group chats!",
            parse_mode='Markdown'
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with deep linking support."""
        args = context.args

        # Deep link parameter check (e.g., join_123456)
        if args and len(args) > 0 and args[0].startswith('join_'):
            try:
                # Extract chat_id
                chat_id = int(args[0].replace('join_', ''))
                user = update.effective_user

                # Send welcome message
                welcome_msg = (
                    f"🎭 **Welcome, {user.first_name}!** 🎭\n\n"
                    "✅ **You're now connected to the Mafia Bot!**\n\n"
                    "I'll send you game notifications and your role "
                    "when the game starts.\n\n"
                )
                await update.message.reply_text(welcome_msg, parse_mode='Markdown')

                # Automatically joining game
                game = game_data.get_game(chat_id)
                if game and game.phase == GamePhase.LOBBY:
                    if len(game.players) < MAX_PLAYERS:
                        player_data = create_player_dict(user)
                        success = game_data.add_player(chat_id, player_data)

                        if success:
                            success_msg = (
                                f"🎉 **Successfully joined the game!**\n\n"
                                f"👥 Players in lobby: {len(game.players)}/{MAX_PLAYERS}\n"
                                f"🎮 **Return to the group chat to start playing!**\n\n"
                                "I'll send you your role and instructions when the game begins."
                            )
                            await update.message.reply_text(success_msg, parse_mode='Markdown')

                            # Update panel if available
                            if self.panel_updater:
                                await self.panel_updater.update_panel(chat_id)
                        else:
                            await update.message.reply_text("❌ You're already in this game!")
                    else:
                        await update.message.reply_text("❌ Game is full!")
                else:
                    await update.message.reply_text("❌ Game not found or already started!")

            except (ValueError, IndexError):
                # Fall back to normal /start if parameter is invalid
                await self._send_normal_start_message(update)
        else:
            # Normal /start command
            await self._send_normal_start_message(update)

    async def _send_normal_start_message(self, update: Update):
        """Send normal start message."""
        await update.message.reply_text(
        "🎭 **Welcome to Mafia Bot!** 🎭\n\n"
        "Commands:\n"
        "• `/newgame` - Create a new game lobby\n"
        "• `/join` - Join the current game\n"
        "• `/leave` - Leave the current game\n"
        "• `/startgame` - Start the game (needs 5+ players)\n"
        "• `/status` - Show current game status\n"
        "• `/endgame` - End the current game\n\n"
        "ℹ️ This bot works best in group chats!",
        parse_mode='Markdown'
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "🎭 **Mafia Game Rules** 🎭\n\n"
            "**Roles:**\n"
            "🔪 **Mafia** - Eliminate villagers at night\n"
            "🔍 **Detective** - Investigate players at night\n"
            "🏥 **Doctor** - Heal players at night\n"
            "👤 **Villagers** - Vote during the day\n\n"
            "**Game Flow:**\n"
            "1️⃣ **Night Phase:** Special roles act privately\n"
            "2️⃣ **Day Phase:** Discuss and vote to eliminate\n"
            "3️⃣ Repeat until one team wins\n\n"
            "**Win Conditions:**\n"
            "👥 Villagers win by eliminating all mafia\n"
            "🔪 Mafia wins by equaling villager count\n\n"
            "Use `/newgame` to start playing!"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def cmd_newgame(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /newgame command."""
        chat_id = update.effective_chat.id

        if update.effective_chat.type == 'private':
            await update.message.reply_text(
                "❌ Mafia games must be played in group chats!\n"
                "Add me to a group and use `/newgame` there."
            )
            return

        try:
            # Create new game
            game = game_data.create_game(chat_id)
            await update.message.reply_text(
                "🎭 **New Mafia Game Created!** 🎭\n\n"
                f"Players needed: {MIN_PLAYERS}-{MAX_PLAYERS}\n"
                "Use `/join` to join the game!",
                parse_mode='Markdown'
            )
            await self.panel_updater.update_panel(chat_id)
        except ValueError as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error creating game: {e}")
            await update.message.reply_text("❌ An error occurred creating the game.")

    async def cmd_join(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /join command."""
        chat_id = update.effective_chat.id
        user = update.effective_user

        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Use this command in the game group chat!")
            return

        if user.is_bot:
            await update.message.reply_text("❌ Bots cannot join the game!")
            return

        game = game_data.get_game(chat_id)
        if not game:
            await update.message.reply_text("❌ No game lobby found. Use `/newgame` first!")
            return

        if game.phase != GamePhase.LOBBY:
            await update.message.reply_text("❌ Cannot join - game is already in progress!")
            return

        if len(game.players) >= MAX_PLAYERS:
            await update.message.reply_text(f"❌ Game is full! Maximum {MAX_PLAYERS} players allowed.")
            return

        player_data = create_player_dict(user)
        success = game_data.add_player(chat_id, player_data)

        if success:
            await update.message.reply_text(
                f"✅ {user.first_name} joined the game! ({len(game.players)}/{MAX_PLAYERS})"
            )
            await self.panel_updater.update_panel(chat_id)
        else:
            await update.message.reply_text("❌ You're already in the game!")

    async def cmd_leave(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /leave command."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Use this command in the game group chat!")
            return

        game = game_data.get_game(chat_id)
        if not game:
            await update.message.reply_text("❌ No game found!")
            return

        if game.phase != GamePhase.LOBBY:
            await update.message.reply_text("❌ Cannot leave - game is already in progress!")
            return

        success = game_data.remove_player(chat_id, user_id)

        if success:
            await update.message.reply_text("✅ You left the game!")
            await self.panel_updater.update_panel(chat_id)
        else:
            await update.message.reply_text("❌ You're not in the game!")

    async def cmd_startgame(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /startgame command."""
        chat_id = update.effective_chat.id

        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Use this command in the game group chat!")
            return

        can_start, error_msg = game_engine.can_start_game(chat_id)
        if not can_start:
            await update.message.reply_text(f"❌ {error_msg}")
            return

        success = game_engine.start_game(chat_id)
        if success:
            from telegram_mafia_config import MESSAGES
            await update.message.reply_text(MESSAGES['game_started'], parse_mode='Markdown')

            # Send role assignments via DM
            await self.panel_updater.send_role_assignments(chat_id)

            # Send night action prompts
            await self.panel_updater.send_night_prompts(chat_id)
        else:
            await update.message.reply_text("❌ Failed to start game!")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        chat_id = update.effective_chat.id

        game = game_data.get_game(chat_id)
        if not game:
            await update.message.reply_text("❌ No game found!")
            return

        # Force panel update
        await self.panel_updater.update_panel(chat_id)
        await update.message.reply_text("📊 Game status updated!")

    async def cmd_endgame(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /endgame command."""
        chat_id = update.effective_chat.id

        game = game_data.get_game(chat_id)
        if not game:
            await update.message.reply_text("❌ No game found!")
            return

        # Only allow game creators or admins to end game
        user_id = update.effective_user.id
        chat_member = await context.bot.get_chat_member(chat_id, user_id)

        if chat_member.status not in ['creator', 'administrator']:
            # Check if user is in the game and it's in lobby phase
            if game.phase == GamePhase.LOBBY:
                player_in_game = any(p['id'] == user_id for p in game.players)
                if not player_in_game:
                    await update.message.reply_text("❌ Only players or admins can end the game!")
                    return
            else:
                await update.message.reply_text("❌ Only administrators can end an active game!")
                return

        game_data.delete_game(chat_id)
        await update.message.reply_text("🛑 Game ended!")

    async def cmd_vote(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /vote command for day voting."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Use this command in the game group chat!")
            return

        game = game_data.get_game(chat_id)
        if not game or not game.is_active():
            await update.message.reply_text("❌ No active game!")
            return

        if game.phase not in [GamePhase.DAY, GamePhase.VOTING]:
            await update.message.reply_text("❌ Not voting phase!")
            return

        if user_id not in game.alive_players:
            await update.message.reply_text("❌ You're not alive or not in the game!")
            return

        # Send voting keyboard
        keyboard = self.panel_updater.ui.create_action_keyboard(chat_id, user_id, 'vote')
        if keyboard:
            await update.message.reply_text(
                "🗳️ **Choose who to eliminate:**",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ No valid targets available!")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries from inline keyboards."""
        query = update.callback_query
        await query.answer()

        try:
            # Parse callback data
            data_parts = query.data.split('_')
            if len(data_parts) < 2:
                return

            action = data_parts[0]

            if action in ['join', 'leave', 'start', 'endgame', 'status']:
                await self._handle_game_control_callback(query, action, data_parts)
            elif action in ['kill', 'investigate', 'heal', 'vote']:
                await self._handle_action_callback(query, action, data_parts)
            elif action == 'cancel':
                await self._handle_cancel_callback(query, data_parts)

        except Exception as e:
            self.logger.error(f"Error handling callback query: {e}")
            await query.edit_message_text("❌ An error occurred processing your action.")

    async def _handle_game_control_callback(self, query, action: str, data_parts: list[str]):
        """Handle game control callback queries."""
        if len(data_parts) < 2:
            return

        chat_id = int(data_parts[1])
        user = query.from_user

        if action == 'join':
            if user.is_bot:
                await query.answer("❌ Bots cannot join the game!", show_alert=True)
                return

            # *** ЖАҢА КОД: join басқанда бірінші ботпен start жасау ***
            try:
                # Ботпен private чатта start болу үшін welcome message жіберу
                welcome_message = (
                    f"🎭 **Welcome to Mafia Bot, {user.first_name}!** 🎭\n\n"
                    "You've joined a Mafia game! When the game starts, "
                    "I'll send you your role and instructions here.\n\n"
                    "🎮 **Game Commands:**\n"
                    "• During night phase, special roles will get action buttons\n"
                    "• During day phase, use voting buttons\n"
                    "• All game actions happen through buttons - no typing needed!\n\n"
                    "✅ **You're now connected!** Return to the group chat to continue."
                )

                await self.panel_updater.send_private_message(user.id, welcome_message)
            except Exception as e:
                self.logger.warning(f"Could not send private message to user {user.id}: {e}")
                await query.answer(
                    "⚠️ Please start a private chat with me first by clicking @YourBotUsername then clicking 'START', "
                    "then try joining again!",
                    show_alert=True
                )
                return

            game = game_data.get_game(chat_id)
            if not game:
                await query.answer("❌ No game lobby found!", show_alert=True)
                return

            if game.phase != GamePhase.LOBBY:
                await query.answer("❌ Cannot join - game already in progress!", show_alert=True)
                return

            if len(game.players) >= MAX_PLAYERS:
                await query.answer(f"❌ Game is full! ({MAX_PLAYERS} players max)", show_alert=True)
                return

            player_data = create_player_dict(user)
            success = game_data.add_player(chat_id, player_data)

            if success:
                await query.answer(
                    f"✅ {user.first_name} joined the game! ({len(game.players)}/{MAX_PLAYERS}) Check your private messages!"
                )
                await self.panel_updater.update_panel(chat_id)
            else:
                await query.answer("❌ You're already in the game!", show_alert=True)

        elif action == 'leave':
            game = game_data.get_game(chat_id)
            if not game or game.phase != GamePhase.LOBBY:
                await query.answer("❌ Cannot leave at this time!", show_alert=True)
                return

            success = game_data.remove_player(chat_id, user.id)
            if success:
                await query.answer(f"✅ {user.first_name} left the game!")
                await self.panel_updater.update_panel(chat_id)
            else:
                await query.answer("❌ You're not in the game!", show_alert=True)

        elif action == 'start':
            can_start, error_msg = game_engine.can_start_game(chat_id)
            if not can_start:
                await query.answer(f"❌ {error_msg}", show_alert=True)
                return

            success = game_engine.start_game(chat_id)
            if success:
                await query.answer("🎭 Game Started! Check your DMs for your role!")
                await self.panel_updater.update_panel(chat_id)

                # Send role assignments and night prompts
                await self.panel_updater.send_role_assignments(chat_id)
                await self.panel_updater.send_night_prompts(chat_id)
            else:
                await query.answer("❌ Failed to start game!", show_alert=True)

        elif action == 'status':
            await self.panel_updater.update_panel(chat_id)
            await query.answer("📊 Status updated!")

        elif action == 'endgame':
            # Add permission check
            game = game_data.get_game(chat_id)
            if game and game.is_active():
                try:
                    chat_member = await query.bot.get_chat_member(chat_id, user.id)
                    if chat_member.status not in ['creator', 'administrator']:
                        await query.answer("❌ Only administrators can end an active game!", show_alert=True)
                        return
                except Exception:
                    pass

            game_data.delete_game(chat_id)
            await query.answer("🛑 Game ended!")
            try:
                await query.message.edit_text("🛑 **Game Ended**")
            except Exception as e:
                self.logger.error(f"Error editing message after ending game: {e}")

    async def _handle_action_callback(self, query, action: str, data_parts: list[str]):
        """Handle game action callback queries."""
        if len(data_parts) < 3:
            return

        target_id = int(data_parts[1])
        chat_id = int(data_parts[2])
        user_id = query.from_user.id

        # Process the action
        success = game_engine.process_player_action(chat_id, user_id, action, target_id)

        if success:
            # Get target name
            game = game_data.get_game(chat_id)
            target_name = "Unknown"
            if game:
                for player in game.players:
                    if player['id'] == target_id:
                        target_name = player.get('username', player.get('first_name', f"Player {target_id}"))
                        if player.get('username'):
                            target_name = f"@{target_name}"
                        break

            action_messages = {
                'kill': f"🔪 Target selected: {target_name}",
                'investigate': f"🔍 Investigating: {target_name}",
                'heal': f"🏥 Healing: {target_name}",
                'vote': f"🗳️ Voted to eliminate: {target_name}"
            }

            await query.edit_message_text(
                action_messages.get(action, f"✅ Action completed: {target_name}")
            )
            if action == 'vote':
                await self.panel_updater.update_panel(chat_id)
            elif action == 'investigate':
                # Investigation results are processed at end of night phase
                pass
            elif action == 'heal':
                await query.from_user.send_message(f"🏥 You will attempt to heal {target_name} tonight.")
        else:
            await query.edit_message_text("❌ Invalid action! You may not be able to perform this action.")

    async def _handle_cancel_callback(self, query, data_parts: list[str]):
        """Handle cancel callback queries."""
        try:
            await query.edit_message_text("❌ Action cancelled.")
        except Exception:
            pass

    async def _handle_action_callback(self, query, action: str, data_parts: list[str]):
        """Handle game action callback queries."""
        if len(data_parts) < 3:
            return

        target_id = int(data_parts[1])
        chat_id = int(data_parts[2])
        user_id = query.from_user.id

        # Process the action
        success = game_engine.process_player_action(chat_id, user_id, action, target_id)

        if success:
            # Get target name
            game = game_data.get_game(chat_id)
            target_name = "Unknown"
            if game:
                for player in game.players:
                    if player['id'] == target_id:
                        target_name = player.get('username', player.get('first_name', f"Player {target_id}"))
                        if player.get('username'):
                            target_name = f"@{target_name}"
                        break

            action_messages = {
                'kill': f"🔪 Target selected: {target_name}",
                'investigate': f"🔍 Investigating: {target_name}",
                'heal': f"🏥 Healing: {target_name}",
                'vote': f"🗳️ Voted to eliminate: {target_name}"
            }

            await query.edit_message_text(
                action_messages.get(action, f"✅ Action completed: {target_name}")
            )
            if action == 'vote':
                await self.panel_updater.update_panel(chat_id)
            # Send private results for detective/doctor actions
            elif action == 'investigate':
                # Investigation results are processed at end of night phase
                pass
            elif action == 'heal':
                await query.from_user.send_message(f"🏥 You will attempt to heal {target_name} tonight.")
        else:
            await query.edit_message_text("❌ Invalid action! You may not be able to perform this action.")

    async def _handle_cancel_callback(self, query, data_parts: list[str]):
        """Handle cancel callback queries."""
        await query.edit_message_text("❌ Action cancelled.")
    
    async def _handle_action_callback(self, query, action: str, data_parts: list[str]):
        """Handle game action callback queries."""
        if len(data_parts) < 3:
            return
        
        target_id = int(data_parts[1])
        chat_id = int(data_parts[2])
        user_id = query.from_user.id
        
        # Process the action
        success = game_engine.process_player_action(chat_id, user_id, action, target_id)
        
        if success:
            # Get target name
            game = game_data.get_game(chat_id)
            target_name = "Unknown"
            if game:
                for player in game.players:
                    if player['id'] == target_id:
                        target_name = player.get('username', player.get('first_name', f"Player {target_id}"))
                        if player.get('username'):
                            target_name = f"@{target_name}"
                        break
            
            action_messages = {
                'kill': f"🔪 Target selected: {target_name}",
                'investigate': f"🔍 Investigating: {target_name}",
                'heal': f"🏥 Healing: {target_name}",
                'vote': f"🗳️ Voted to eliminate: {target_name}"
            }
            
            await query.edit_message_text(
                action_messages.get(action, f"✅ Action completed: {target_name}")
            )
            if action == 'vote':
                await self.panel_updater.update_panel(chat_id)
            # Send private results for detective/doctor actions
            elif action == 'investigate':
                # Investigation results are processed at end of night phase
                pass
            elif action == 'heal':
                await query.from_user.send_message(f"🏥 You will attempt to heal {target_name} tonight.")
        else:
            await query.edit_message_text("❌ Invalid action! You may not be able to perform this action.")
    
    async def _handle_cancel_callback(self, query, data_parts: list[str]):
        """Handle cancel callback queries."""
        await query.edit_message_text("❌ Action cancelled.")


def setup_handlers(application, panel_updater):
    """Set up all command and callback handlers."""
    handlers_instance = MafiaHandlers(panel_updater)
    
    # Command handlers
    application.add_handler(CommandHandler("start", handlers_instance.cmd_start))
    application.add_handler(CommandHandler("help", handlers_instance.cmd_help))
    application.add_handler(CommandHandler("newgame", handlers_instance.cmd_newgame))
    application.add_handler(CommandHandler("join", handlers_instance.cmd_join))
    application.add_handler(CommandHandler("leave", handlers_instance.cmd_leave))
    application.add_handler(CommandHandler("startgame", handlers_instance.cmd_startgame))
    application.add_handler(CommandHandler("status", handlers_instance.cmd_status))
    application.add_handler(CommandHandler("endgame", handlers_instance.cmd_endgame))
    application.add_handler(CommandHandler("vote", handlers_instance.cmd_vote))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(handlers_instance.handle_callback_query))
    
    logger.info("All handlers registered successfully")
    return handlers_instance
# telegram_mafia_bot_ui.py
"""
UI and display formatting module for the Telegram Mafia Game Bot.
Handles panel updates, message formatting, and user interface elements.
"""

import logging
from typing import List, Dict, Any, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from telegram_mafia_data import game_data, GamePhase
from telegram_mafia_utils import format_player_list, get_display_name
from telegram_mafia_config import MESSAGES

logger = logging.getLogger(__name__)


class MafiaUI:
    """Handles all UI formatting and display logic."""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)
  
    def format_game_panel(self, chat_id: int) -> str:
        """
        Format the main game status panel.
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Formatted panel text
        """
        game = game_data.get_game(chat_id)
        if not game:
            return "❌ No active game"
        
        if game.phase == GamePhase.LOBBY:
            return self._format_lobby_panel(game)
        elif game.is_active():
            return self._format_active_game_panel(game)
        else:
            return self._format_ended_game_panel(game)
    
    def _format_lobby_panel(self, game) -> str:
        """Format lobby panel."""
        panel = "🎭 **MAFIA GAME LOBBY** 🎭\n\n"
        
        if game.players:
            panel += f"**Players ({len(game.players)}):**\n"
            panel += format_player_list(game.players, show_status=False)
            panel += f"\n\n💡 Need 5-20 players to start"
        else:
            panel += "🔍 **Waiting for players...**\n"
            panel += "Use /join to join the game!"
        
        return panel
    
    def _format_active_game_panel(self, game) -> str:
        """Format active game panel."""
        phase_icons = {
            GamePhase.NIGHT: "🌙",
            GamePhase.DAY: "☀️",
            GamePhase.VOTING: "🗳️"
        }
        
        icon = phase_icons.get(game.phase, "🎮")
        phase_name = game.phase.value.upper()
        
        panel = f"{icon} **{phase_name} PHASE** {icon}\n"
        
        if game.day_number > 0:
            panel += f"📅 **Day {game.day_number}**\n"
        
        # Time remaining
        time_remaining = game_data.get_phase_time_remaining(game.chat_id)
        if time_remaining is not None:
            minutes, seconds = divmod(time_remaining, 60)
            panel += f"⏰ Time: {minutes:02d}:{seconds:02d}\n"
        
        panel += "\n"
        
        # Player status
        panel += f"**Alive Players ({len(game.alive_players)}):**\n"
        panel += format_player_list(game.players, game.alive_players)
        
        if game.eliminated_players:
            panel += f"\n💀 **Eliminated:** {len(game.eliminated_players)}\n"
        
        # Phase-specific information
        if game.phase == GamePhase.NIGHT:
            panel += "\n🌙 **Special roles:** Check your DMs!"
        elif game.phase == GamePhase.DAY:
            panel += "\n💬 **Discuss and prepare to vote!**"
        elif game.phase == GamePhase.VOTING:
            panel += "\n🗳️ **Vote to eliminate someone!**"
            if game.vote_counts:
                panel += self._format_vote_counts(game)
        
        # Recent results
        if game.night_results:
            public_results = [r for r in game.night_results if not r.startswith(('detective_', 'doctor_'))]
            if public_results:
                panel += "\n📰 **Latest News:**\n"
                for result in public_results[-2:]:
                    panel += f"• {result}\n"
        
        return panel
    
    def _format_ended_game_panel(self, game) -> str:
        """Format ended game panel."""
        panel = "🎉 **GAME ENDED** 🎉\n\n"
        
        if game.night_results:
            # Show final result
            final_result = game.night_results[-1]
            panel += f"{final_result}\n\n"
        
        # Show final player status
        panel += "**Final Status:**\n"
        panel += format_player_list(game.players, game.alive_players)
        
        # Show roles
        panel += "\n**Roles:**\n"
        for player in game.players:
            name = get_display_name(player)
            role = game.role_assignments.get(player['id'], 'villager')
            role_emoji = self._get_role_emoji(role)
            status = "✅" if player['id'] in game.alive_players else "💀"
            panel += f"{status} {role_emoji} {name} - {role.title()}\n"
        
        return panel
    
    def _format_vote_counts(self, game) -> str:
        """Format current vote counts."""
        if not game.vote_counts:
            return ""
        
        vote_text = "\n**Current Votes:**\n"
        sorted_votes = sorted(game.vote_counts.items(), key=lambda x: x[1], reverse=True)
        
        for target_id, votes in sorted_votes:
            target_name = self._get_player_name_by_id(game, target_id)
            vote_text += f"• {target_name}: {votes} vote{'s' if votes != 1 else ''}\n"
        
        return vote_text
    
    def _get_role_emoji(self, role: str) -> str:
        """Get emoji for role."""
        emoji_map = {
            'mafia': '🔪',
            'detective': '🔍',
            'doctor': '🏥',
            'villager': '👤'
        }
        return emoji_map.get(role, '👤')
    
    def _get_player_name_by_id(self, game, user_id: int) -> str:
        """Get player display name by ID."""
        for player in game.players:
            if player['id'] == user_id:
                return get_display_name(player)
        return f"Player {user_id}"
    
    def create_action_keyboard(self, chat_id: int, user_id: int, action_type: str) -> Optional[InlineKeyboardMarkup]:
        """
        Create inline keyboard for player actions.
        
        Args:
            chat_id: Chat ID
            user_id: User ID
            action_type: Type of action ('kill', 'investigate', 'heal', 'vote')
            
        Returns:
            InlineKeyboardMarkup or None
        """
        game = game_data.get_game(chat_id)
        if not game:
            return None
        
        # Get valid targets
        valid_targets = []
        for player in game.players:
            if player['id'] in game.alive_players:
                # Skip self for kill/investigate, allow self-heal for doctor
                if action_type in ['kill', 'investigate', 'vote'] and player['id'] == user_id:
                    continue
                valid_targets.append(player)
        
        if not valid_targets:
            return None
        
        # Create keyboard buttons
        keyboard = []
        for i in range(0, len(valid_targets), 2):  # 2 buttons per row
            row = []
            for j in range(2):
                if i + j < len(valid_targets):
                    player = valid_targets[i + j]
                    name = get_display_name(player)
                    callback_data = f"{action_type}_{player['id']}_{chat_id}"
                    
                    # Truncate long names for button display
                    if len(name) > 15:
                        name = name[:12] + "..."
                    
                    row.append(InlineKeyboardButton(name, callback_data=callback_data))
            keyboard.append(row)
        
        # Add cancel button
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{action_type}_{chat_id}")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def create_game_control_keyboard(self, chat_id: int) -> InlineKeyboardMarkup:
        """Create keyboard for game control commands."""
        game = game_data.get_game(chat_id)
        
        keyboard = []
        
        if not game or game.phase == GamePhase.LOBBY:
            # Join батырмасын URL арқылы жасау - автоматты ботқа өтіп start болу үшін
            # ӨЗ БОТЫҢЫЗДЫҢ USERNAME-ЫН ҚОЙЫҢЫЗ! (@ белгісінсіз)
            bot_username = "sds_mafia_bot"  # Мұны өзгертіңіз!
            keyboard.append([
                InlineKeyboardButton("🎮 Join Game", url=f"https://t.me/{bot_username}?start=join_{chat_id}"),
                InlineKeyboardButton("🚪 Leave Game", callback_data=f"leave_{chat_id}")
            ])
            if game and len(game.players) >= 5:
                keyboard.append([InlineKeyboardButton("▶️ Start Game", callback_data=f"start_{chat_id}")])
        elif game.is_active():
            keyboard.append([InlineKeyboardButton("📊 Game Status", callback_data=f"status_{chat_id}")])
        
        keyboard.append([InlineKeyboardButton("❌ End Game", callback_data=f"endgame_{chat_id}")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def format_role_message(self, role: str, mafia_team: List[str] = None) -> str:
        """
        Format role assignment message for private DM.
        
        Args:
            role: Player's role
            mafia_team: List of mafia member names (for mafia players)
            
        Returns:
            Formatted role message
        """
        role_messages = {
            'mafia': MESSAGES['role_mafia'],
            'detective': MESSAGES['role_detective'],
            'doctor': MESSAGES['role_doctor'],
            'villager': MESSAGES['role_villager']
        }
        
        message = role_messages.get(role, MESSAGES['role_villager'])
        
        if role == 'mafia' and mafia_team:
            message += f"\n\n🤝 **Your team:** {', '.join(mafia_team)}"
        
        return message
    
    def format_night_action_prompt(self, role: str) -> str:
        """Format night action prompt message."""
        prompts = {
            'mafia': '🔪 **Choose a player to eliminate:**',
            'detective': '🔍 **Choose a player to investigate:**',
            'doctor': '🏥 **Choose a player to heal:**'
        }
        return prompts.get(role, '')
    
    def format_vote_prompt(self) -> str:
        """Format day voting prompt message."""
        return MESSAGES['vote_prompt']
    
    def format_private_result(self, result: str) -> str:
        """Format private result message (for detective/doctor)."""
        return f"🔒 **Private Result:**\n{result}"


class PanelUpdater:
    """Handles automatic panel updates."""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.ui = MafiaUI(bot)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def update_panel(self, chat_id: int):
        """Update the game panel in the specified chat."""
        # --- FIX START ---
        # The entire try...except block was incorrectly indented. It has now been
        # moved inside the update_panel method.
        try:
            game = game_data.get_game(chat_id)
            if not game:
                return
            
            # Format panel content
            panel_text = self.ui.format_game_panel(chat_id)
            keyboard = self.ui.create_game_control_keyboard(chat_id)
            
            # Update or send new panel
            if game.panel_message_id:
                try:
                    await self.bot.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=game.panel_message_id,
                        text=panel_text,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                except TelegramError as e:
                    if "message is not modified" not in str(e).lower():
                        self.logger.warning(f"Failed to edit panel message: {e}")
                        # Try sending new message
                        await self._send_new_panel(chat_id, panel_text, keyboard)
            else:
                await self._send_new_panel(chat_id, panel_text, keyboard)
                
        except Exception as e:
            self.logger.error(f"Error updating panel for chat {chat_id}: {e}")
        # --- FIX END ---

    async def _send_new_panel(self, chat_id: int, text: str, keyboard: InlineKeyboardMarkup):
        """Send a new panel message."""
        try:
            message = await self.bot.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        
            # Store message ID for future updates
            game = game_data.get_game(chat_id)
            if game:
                game.panel_message_id = message.message_id
            
        except Exception as e:
            self.logger.error(f"Failed to send new panel message: {e}")

    async def send_private_message(self, user_id: int, text: str, keyboard: InlineKeyboardMarkup = None):
        """Send a private message to a user."""
        try:
            await self.bot.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            self.logger.warning(f"Failed to send private message to user {user_id}: {e}")

    async def send_role_assignments(self, chat_id: int):
        """Send role assignments to all players via DM."""
        game = game_data.get_game(chat_id)
        if not game:
            return
    
        # Get mafia team for mafia role messages
        mafia_team = []
        for player in game.players:
            if game.role_assignments.get(player['id']) == 'mafia':
                mafia_team.append(get_display_name(player))
    
        # Send role messages
        for player in game.players:
            user_id = player['id']
            role = game.role_assignments.get(user_id, 'villager')
        
            role_message = self.ui.format_role_message(
                role, 
                mafia_team if role == 'mafia' else None
            )
        
            await self.send_private_message(user_id, role_message)

    async def send_night_prompts(self, chat_id: int):
        """Send night action prompts to special roles."""
        game = game_data.get_game(chat_id)
        if not game or game.phase != GamePhase.NIGHT:
            return
    
        for player in game.players:
            if player['id'] not in game.alive_players:
                continue
        
            user_id = player['id']
            role = game.role_assignments.get(user_id, 'villager')
        
            if role in ['mafia', 'detective', 'doctor']:
                action_type = {'mafia': 'kill', 'detective': 'investigate', 'doctor': 'heal'}[role]
                prompt = self.ui.format_night_action_prompt(role)
                if prompt:
                    keyboard = self.ui.create_action_keyboard(chat_id, user_id, action_type)
                    await self.send_private_message(user_id, prompt, keyboard)


# This will be set by the main module
panel_updater_instance = None
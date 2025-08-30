# telegram_mafia_data.py
"""
Data management module for the Telegram Mafia Game Bot.
Handles in-memory storage and management of game state.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    """Game phase enumeration."""
    LOBBY = "lobby"
    NIGHT = "night"
    DAY = "day"
    VOTING = "voting"
    ENDED = "ended"


class ActionType(Enum):
    """Night action types."""
    KILL = "kill"
    INVESTIGATE = "investigate"
    HEAL = "heal"
    VOTE = "vote"


@dataclass
class GameAction:
    """Represents a player action."""
    player_id: int
    action_type: ActionType
    target_id: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GameState:
    """Complete game state for a chat."""
    chat_id: int
    players: List[Dict[str, Any]] = field(default_factory=list)
    role_assignments: Dict[int, str] = field(default_factory=dict)
    alive_players: List[int] = field(default_factory=list)
    eliminated_players: List[int] = field(default_factory=list)
    phase: GamePhase = GamePhase.LOBBY
    phase_end_time: Optional[datetime] = None
    current_actions: Dict[int, GameAction] = field(default_factory=dict)
    vote_counts: Dict[int, int] = field(default_factory=dict)
    voters: Set[int] = field(default_factory=set)
    day_number: int = 0
    night_results: List[str] = field(default_factory=list)
    game_log: List[str] = field(default_factory=list)
    panel_message_id: Optional[int] = None
    
    def is_active(self) -> bool:
        """Check if game is currently active."""
        return self.phase not in [GamePhase.LOBBY, GamePhase.ENDED]
    
    def get_alive_count_by_role(self, role: str) -> int:
        """Get count of alive players with specific role."""
        count = 0
        for player_id in self.alive_players:
            if self.role_assignments.get(player_id) == role:
                count += 1
        return count
    
    def get_mafia_players(self) -> List[int]:
        """Get list of mafia player IDs."""
        return [pid for pid, role in self.role_assignments.items() 
                if role == 'mafia' and pid in self.alive_players]
    
    def add_log_entry(self, entry: str):
        """Add entry to game log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.game_log.append(f"[{timestamp}] {entry}")
        logger.info(f"Game {self.chat_id}: {entry}")


class GameDataManager:
    """Manages all game data in memory."""
    
    def __init__(self):
        self._games: Dict[int, GameState] = {}
        logger.info("GameDataManager initialized")
    
    def set_panel_updater(self, func):
        """Set the function used to update game panels."""
        self._panel_updater_func = func
        logger.info("Panel updater function set")

    async def update_panel(self, chat_id: int):
        """Update game panel if updater function is set."""
        if hasattr(self, '_panel_updater_func') and self._panel_updater_func:
            try:
                await self._panel_updater_func(chat_id)
            except Exception as e:
                logger.error(f"Error updating panel for chat {chat_id}: {e}")

    
    def create_game(self, chat_id: int) -> GameState:
        """Create a new game for the chat."""
        if chat_id in self._games and self._games[chat_id].is_active():
            raise ValueError(f"Game already active in chat {chat_id}")
        
        game = GameState(chat_id=chat_id)
        self._games[chat_id] = game
        game.add_log_entry("Game created")
        logger.info(f"Created new game for chat {chat_id}")
        return game
    
    def get_game(self, chat_id: int) -> Optional[GameState]:
        """Get game state for chat."""
        return self._games.get(chat_id)
    
    def delete_game(self, chat_id: int):
        """Delete game from memory."""
        if chat_id in self._games:
            del self._games[chat_id]
            logger.info(f"Deleted game for chat {chat_id}")
    
    def add_player(self, chat_id: int, player_data: Dict[str, Any]) -> bool:
        """Add player to game."""
        game = self.get_game(chat_id)
        if not game or game.phase != GamePhase.LOBBY:
            return False
        
        # Check if player already in game
        for existing_player in game.players:
            if existing_player['id'] == player_data['id']:
                return False
        
        game.players.append(player_data)
        game.add_log_entry(f"Player {player_data.get('username', player_data['id'])} joined")
        return True
    
    def remove_player(self, chat_id: int, user_id: int) -> bool:
        """Remove player from game."""
        game = self.get_game(chat_id)
        if not game or game.phase != GamePhase.LOBBY:
            return False
        
        game.players = [p for p in game.players if p['id'] != user_id]
        game.add_log_entry(f"Player {user_id} left")
        return True
    
    def start_game(self, chat_id: int, role_assignments: Dict[int, str]) -> bool:
        """Start the game with role assignments."""
        game = self.get_game(chat_id)
        if not game or game.phase != GamePhase.LOBBY:
            return False
        
        game.role_assignments = role_assignments
        game.alive_players = [p['id'] for p in game.players]
        game.phase = GamePhase.NIGHT
        game.day_number = 1
        game.add_log_entry("Game started - Night 1 begins")
        return True
    
    def set_phase(self, chat_id: int, phase: GamePhase, duration_seconds: int = None):
        """Set game phase with optional timer."""
        game = self.get_game(chat_id)
        if not game:
            return False
        
        game.phase = phase
        if duration_seconds:
            game.phase_end_time = datetime.now() + timedelta(seconds=duration_seconds)
        else:
            game.phase_end_time = None
        
        game.add_log_entry(f"Phase changed to {phase.value}")
        return True
    
    def add_action(self, chat_id: int, action: GameAction) -> bool:
        """Add player action for current phase."""
        game = self.get_game(chat_id)
        if not game or not game.is_active():
            return False
        
        # Validate action based on current phase
        if game.phase == GamePhase.NIGHT and action.action_type in [ActionType.KILL, ActionType.INVESTIGATE, ActionType.HEAL]:
            game.current_actions[action.player_id] = action
            game.add_log_entry(f"Night action recorded: {action.action_type.value} by {action.player_id}")
            return True
        elif game.phase in [GamePhase.DAY, GamePhase.VOTING] and action.action_type == ActionType.VOTE:
            # Handle voting
            if action.player_id in game.voters:
                # Remove previous vote
                old_target = None
                for pid, act in game.current_actions.items():
                    if pid == action.player_id and act.action_type == ActionType.VOTE:
                        old_target = act.target_id
                        break
                if old_target and old_target in game.vote_counts:
                    game.vote_counts[old_target] = max(0, game.vote_counts[old_target] - 1)
            
            game.current_actions[action.player_id] = action
            game.voters.add(action.player_id)
            game.vote_counts[action.target_id] = game.vote_counts.get(action.target_id, 0) + 1
            game.add_log_entry(f"Vote recorded: {action.player_id} -> {action.target_id}")
            return True
        
        return False
    
    def eliminate_player(self, chat_id: int, user_id: int, reason: str = "eliminated"):
        """Eliminate a player from the game."""
        game = self.get_game(chat_id)
        if not game or user_id not in game.alive_players:
            return False
        
        game.alive_players.remove(user_id)
        game.eliminated_players.append(user_id)
        
        # Find player name for logging
        player_name = str(user_id)
        for player in game.players:
            if player['id'] == user_id:
                player_name = player.get('username', player.get('first_name', str(user_id)))
                break
        
        game.add_log_entry(f"Player {player_name} {reason}")
        return True
    
    def clear_phase_actions(self, chat_id: int):
        """Clear all actions from current phase."""
        game = self.get_game(chat_id)
        if game:
            game.current_actions.clear()
            game.vote_counts.clear()
            game.voters.clear()
            game.night_results.clear()
    
    def get_phase_time_remaining(self, chat_id: int) -> Optional[int]:
        """Get remaining time for current phase in seconds."""
        game = self.get_game(chat_id)
        if not game or not game.phase_end_time:
            return None
        
        remaining = (game.phase_end_time - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def is_phase_expired(self, chat_id: int) -> bool:
        """Check if current phase has expired."""
        remaining = self.get_phase_time_remaining(chat_id)
        return remaining is not None and remaining <= 0
    
    def get_active_games(self) -> List[int]:
        """Get list of chat IDs with active games."""
        return [chat_id for chat_id, game in self._games.items() if game.is_active()]


# Global data manager instance
game_data = GameDataManager()
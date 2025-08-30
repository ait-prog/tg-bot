# telegram_mafia_game_logic.py
"""
Core game logic for the Telegram Mafia Game Bot.
Handles game flow, win conditions, and action processing.
"""
import random
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

from telegram_mafia_config import NIGHT_PHASE_TIME, DAY_PHASE_TIME, VOTING_TIME, MESSAGES, MIN_PLAYERS, MAX_PLAYERS

from telegram_mafia_data import game_data, GameState, GamePhase, ActionType, GameAction
from telegram_mafia_utils import (
    validate_player_count, 
    assign_roles_to_players,
    get_majority_threshold,
    calculate_game_stats
)

logger = logging.getLogger(__name__)


class MafiaGameEngine:
    """Core game engine handling all game logic."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def can_start_game(self, chat_id: int) -> Tuple[bool, str]:
        """
        Check if a game can be started in the chat.
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Tuple of (can_start, error_message)
        """
        game = game_data.get_game(chat_id)
        
        if not game:
            return False, "No game lobby found. Use /newgame to create one."
        
        if game.is_active():
            return False, "A game is already in progress."
        
        player_count = len(game.players)
        if not validate_player_count(player_count):
            return False, f"Need {MIN_PLAYERS}-{MAX_PLAYERS} players to start."
        return True, ""
    
    def start_game(self, chat_id: int) -> bool:
        """
        Start a new game in the specified chat.
        
        Args:
            chat_id: Chat ID
            
        Returns:
            bool: True if game started successfully
        """
        can_start, error = self.can_start_game(chat_id)
        if not can_start:
            self.logger.warning(f"Cannot start game in chat {chat_id}: {error}")
            return False
        
        game = game_data.get_game(chat_id)
        
        # Assign roles
        role_assignments = assign_roles_to_players(game.players)
        
        # Start the game
        success = game_data.start_game(chat_id, role_assignments)
        if success:
            self._start_night_phase(chat_id)
            self.logger.info(f"Game started in chat {chat_id} with {len(game.players)} players")
        
        return success
    
    def _start_night_phase(self, chat_id: int):
        """Start the night phase."""
        game = game_data.get_game(chat_id)
        if not game:
            return
        
        game_data.clear_phase_actions(chat_id)
        game_data.set_phase(chat_id, GamePhase.NIGHT, NIGHT_PHASE_TIME)
        self.logger.info(f"Night phase started in chat {chat_id}")
    
    def _start_day_phase(self, chat_id: int):
        """Start the day phase."""
        game = game_data.get_game(chat_id)
        if not game:
            return
        
        # Process night actions first
        self._process_night_actions(chat_id)
        
        # Check win condition
        if self._check_win_condition(chat_id):
            return
        
        game_data.clear_phase_actions(chat_id)
        game_data.set_phase(chat_id, GamePhase.DAY, DAY_PHASE_TIME)
        game.day_number += 1
        self.logger.info(f"Day phase {game.day_number} started in chat {chat_id}")
    
    def _start_voting_phase(self, chat_id: int):
        """Start the voting phase."""
        game_data.set_phase(chat_id, GamePhase.VOTING, VOTING_TIME)
        self.logger.info(f"Voting phase started in chat {chat_id}")
    
    def _process_night_actions(self, chat_id: int):
        """Process all night actions and resolve conflicts."""
        game = game_data.get_game(chat_id)
        if not game:
            return
        
        # Separate actions by type
        kill_actions = []
        heal_actions = []
        investigate_actions = []
        
        for action in game.current_actions.values():
            if action.action_type == ActionType.KILL:
                kill_actions.append(action)
            elif action.action_type == ActionType.HEAL:
                heal_actions.append(action)
            elif action.action_type == ActionType.INVESTIGATE:
                investigate_actions.append(action)
        
        # Process investigations (always succeed)
        for action in investigate_actions:
            target_role = game.role_assignments.get(action.target_id, 'villager')
            result_role = 'villager' if target_role != 'mafia' else 'mafia'
            
            # Store investigation result for the detective
            result_msg = MESSAGES['investigation_result'].format(
                player=self._get_player_name(game, action.target_id),
                role=result_role
            )
            game.night_results.append(f"detective_{action.player_id}:{result_msg}")
        
        # Determine kill target (mafia consensus or random if tie)
        kill_target = None
        if kill_actions:
            kill_votes = Counter(action.target_id for action in kill_actions)
            max_votes = max(kill_votes.values())
            candidates = [target for target, votes in kill_votes.items() if votes == max_votes]
        
            if len(candidates) == 1:
                kill_target = candidates[0]
            elif len(candidates) > 1:
                # Random selection from tied candidates
                kill_target = random.choice(candidates)
                game.night_results.append(f"Mafia had a tie vote - target selected randomly")
        
        # Determine heal target
        heal_target = None
        if heal_actions:
            heal_target = heal_actions[0].target_id  # Only one doctor
        
        # Resolve kill vs heal
        if kill_target and kill_target in game.alive_players:
            if heal_target == kill_target:
                # Kill was prevented
                game.night_results.append(MESSAGES['kill_prevented'].format(
                    player=self._get_player_name(game, kill_target)
                ))
                if heal_actions:
                    doctor_id = heal_actions[0].player_id
                    game.night_results.append(f"doctor_{doctor_id}:{MESSAGES['healing_success'].format(player=self._get_player_name(game, kill_target))}")
            else:
                # Kill succeeded
                game_data.eliminate_player(chat_id, kill_target, "killed by mafia")
                game.night_results.append(MESSAGES['kill_success'].format(
                    player=self._get_player_name(game, kill_target)
                ))
        elif heal_target and heal_actions:
            # Doctor healed but no kill attempt on that target
            doctor_id = heal_actions[0].player_id
            game.night_results.append(f"doctor_{doctor_id}:{MESSAGES['healing_success'].format(player=self._get_player_name(game, heal_target))}")
    
    def _process_day_vote(self, chat_id: int) -> bool:
        """
        Process day phase voting and eliminate player if majority reached.
        
        Returns:
            bool: True if someone was eliminated
        """
        game = game_data.get_game(chat_id)
        if not game:
            return False
        
        if not game.vote_counts:
            game.night_results.append(MESSAGES['no_elimination'])
            return False
        
        # Find player(s) with most votes
        max_votes = max(game.vote_counts.values())
        candidates = [pid for pid, votes in game.vote_counts.items() if votes == max_votes]
        
        if len(candidates) > 1:
            # Tie vote - no elimination
            game.night_results.append(MESSAGES['no_elimination'])
            return False
        
        eliminated_player = candidates[0]
        game_data.eliminate_player(chat_id, eliminated_player, "eliminated by vote")
        game.night_results.append(MESSAGES['elimination'].format(
            player=self._get_player_name(game, eliminated_player)
        ))
        return True
    
    def _check_win_condition(self, chat_id: int) -> bool:
        """
        Check if any team has won the game.
        
        Returns:
            bool: True if game has ended
        """
        game = game_data.get_game(chat_id)
        if not game:
            return False
        
        stats = calculate_game_stats(game.players, game.role_assignments, game.alive_players)
        
        # Mafia wins if they equal or outnumber villagers
        if stats['alive_mafia'] >= stats['alive_villagers'] + stats['alive_detective'] + stats['alive_doctor']:
            self._end_game(chat_id, 'mafia')
            return True
        
        # Villagers win if all mafia are eliminated
        if stats['alive_mafia'] == 0:
            self._end_game(chat_id, 'villagers')
            return True
        
        return False
    
    def _end_game(self, chat_id: int, winner: str):
        """End the game and announce winner."""
        game = game_data.get_game(chat_id)
        if not game:
            return
        
        game_data.set_phase(chat_id, GamePhase.ENDED)
        
        if winner == 'mafia':
            game.night_results.append(MESSAGES['mafia_wins'])
        else:
            game.night_results.append(MESSAGES['villagers_win'])
        
        game.add_log_entry(f"Game ended - {winner} won")
        self.logger.info(f"Game ended in chat {chat_id}: {winner} won")
    
    def force_phase_advance(self, chat_id: int):
        """Force advance to next phase (when timer expires)."""
        game = game_data.get_game(chat_id)
        if not game or not game.is_active():
            return
        
        if game.phase == GamePhase.NIGHT:
            self._start_day_phase(chat_id)
        elif game.phase == GamePhase.DAY:
            self._start_voting_phase(chat_id)
        elif game.phase == GamePhase.VOTING:
            self._process_day_vote(chat_id)
            if not self._check_win_condition(chat_id):
                self._start_night_phase(chat_id)
    
    def process_player_action(self, chat_id: int, user_id: int, action_type: str, target_id: int = None) -> bool:
        """
        Process a player action.
        
        Args:
            chat_id: Chat ID
            user_id: Player ID
            action_type: Type of action ('kill', 'investigate', 'heal', 'vote')
            target_id: Target player ID
            
        Returns:
            bool: True if action was processed successfully
        """
        game = game_data.get_game(chat_id)
        if not game or not game.is_active():
            return False
        
        # Validate player is alive
        if user_id not in game.alive_players:
            return False
        
        # Validate action based on role and phase
        player_role = game.role_assignments.get(user_id, 'villager')
        
        if action_type == 'kill':
            if player_role != 'mafia' or game.phase != GamePhase.NIGHT:
                return False
        elif action_type == 'investigate':
            if player_role != 'detective' or game.phase != GamePhase.NIGHT:
                return False
        elif action_type == 'heal':
            if player_role != 'doctor' or game.phase != GamePhase.NIGHT:
                return False
        elif action_type == 'vote':
            if game.phase not in [GamePhase.DAY, GamePhase.VOTING]:
                return False
        else:
            return False
        
        # Validate target
        if target_id and target_id not in game.alive_players:
            return False
        
        # Create and add action
        try:
            action_enum = ActionType(action_type)
        except ValueError:
            return False
        
        action = GameAction(
            player_id=user_id,
            action_type=action_enum,
            target_id=target_id
        )
        
        return game_data.add_action(chat_id, action)
    
    def get_valid_targets(self, chat_id: int, user_id: int, action_type: str) -> List[Dict[str, Any]]:
        """
        Get list of valid targets for a player's action.
        
        Returns:
            List of player dictionaries that can be targeted
        """
        game = game_data.get_game(chat_id)
        if not game or not game.is_active():
            return []
        
        if user_id not in game.alive_players:
            return []
        
        valid_targets = []
        for player in game.players:
            if player['id'] in game.alive_players:
                # For most actions, can't target yourself
                if action_type in ['kill', 'investigate'] and player['id'] == user_id:
                    continue
                # For voting, can't vote for yourself
                if action_type == 'vote' and player['id'] == user_id:
                    continue
                valid_targets.append(player)
        
        return valid_targets
    
    def get_mafia_team(self, chat_id: int) -> List[int]:
        """Get list of mafia player IDs."""
        game = game_data.get_game(chat_id)
        if not game:
            return []
        return game.get_mafia_players()
    
    def _get_player_name(self, game: GameState, user_id: int) -> str:
        """Get display name for a player."""
        for player in game.players:
            if player['id'] == user_id:
                if player.get('username'):
                    return f"@{player['username']}"
                elif player.get('first_name'):
                    return player['first_name']
        return f"Player {user_id}"
    
    def get_game_status(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Get current game status information."""
        game = game_data.get_game(chat_id)
        if not game:
            return None
        
        stats = calculate_game_stats(game.players, game.role_assignments, game.alive_players)
        time_remaining = game_data.get_phase_time_remaining(chat_id)
        
        return {
            'phase': game.phase.value,
            'day_number': game.day_number,
            'time_remaining': time_remaining,
            'stats': stats,
            'alive_players': len(game.alive_players),
            'total_players': len(game.players),
            'vote_counts': dict(game.vote_counts) if game.phase in [GamePhase.DAY, GamePhase.VOTING] else {},
            'night_results': list(game.night_results)
        }


# Global game engine instance
game_engine = MafiaGameEngine()
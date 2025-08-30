# telegram_mafia_utils.py
"""
Utility functions for the Telegram Mafia Game Bot.
Contains helper functions for validation, role assignment, and other common tasks.
"""

import random
import logging
from typing import List, Dict, Any, Optional
from telegram_mafia_config import ROLE_DISTRIBUTION, MIN_PLAYERS, MAX_PLAYERS

logger = logging.getLogger(__name__)


def validate_player_count(player_count: int) -> bool:
    """
    Validate if the player count is within acceptable limits.
    
    Args:
        player_count: Number of players
        
    Returns:
        bool: True if valid, False otherwise
    """
    return MIN_PLAYERS <= player_count <= MAX_PLAYERS


def get_role_distribution(player_count: int) -> Optional[Dict[str, int]]:
    """
    Get role distribution for given player count.
    
    Args:
        player_count: Number of players
        
    Returns:
        Dict with role counts or None if invalid player count
    """
    return ROLE_DISTRIBUTION.get(player_count)


def assign_roles_to_players(players: List[Dict[str, Any]]) -> Dict[int, str]:
    """
    Randomly assign roles to players based on player count.
    
    Args:
        players: List of player dictionaries with 'id', 'username', etc.
        
    Returns:
        Dict mapping user_id to role
    """
    player_count = len(players)
    role_dist = get_role_distribution(player_count)
    
    if not role_dist:
        raise ValueError(f"Invalid player count: {player_count}")
    
    # Create role list
    roles = []
    for role, count in role_dist.items():
        if role == 'villagers':
            roles.extend(['villager'] * count)
        else:
            roles.extend([role] * count)
    
    # Shuffle roles and assign to players
    random.shuffle(roles)
    
    role_assignments = {}
    for i, player in enumerate(players):
        role_assignments[player['id']] = roles[i]
    
    logger.info(f"Assigned roles to {len(players)} players: {role_assignments}")
    return role_assignments


def format_player_list(players: List[Dict[str, Any]], 
                      alive_players: List[int] = None,
                      show_status: bool = True) -> str:
    """
    Format a list of players for display.
    
    Args:
        players: List of player dictionaries
        alive_players: List of alive player IDs (None means all alive)
        show_status: Whether to show alive/dead status
        
    Returns:
        Formatted string of players
    """
    if not players:
        return "No players"
    
    if alive_players is None:
        alive_players = [p['id'] for p in players]
    
    formatted_players = []
    for player in players:
        name = get_display_name(player)
        if show_status:
            status = "✅" if player['id'] in alive_players else "💀"
            formatted_players.append(f"{status} {name}")
        else:
            formatted_players.append(name)
    
    return "\n".join(formatted_players)


def get_display_name(player: Dict[str, Any]) -> str:
    """
    Get display name for a player.
    
    Args:
        player: Player dictionary
        
    Returns:
        Display name string
    """
    if 'username' in player and player['username']:
        return f"@{player['username']}"
    elif 'first_name' in player:
        return player['first_name']
    else:
        return f"Player {player['id']}"


def sanitize_input(text: str) -> str:
    """
    Sanitize user input to prevent issues.
    
    Args:
        text: Input text
        
    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        return str(text)
    
    # Remove excessive whitespace and limit length
    text = text.strip()[:1000]
    
    # Basic HTML entity encoding for safety
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    return text


def get_majority_threshold(total_count: int) -> int:
    """
    Calculate majority threshold for voting.
    
    Args:
        total_count: Total number of voters
        
    Returns:
        Minimum votes needed for majority
    """
    return (total_count // 2) + 1


def create_player_dict(user) -> Dict[str, Any]:
    """
    Create a standardized player dictionary from Telegram User object.
    
    Args:
        user: Telegram User object
        
    Returns:
        Player dictionary
    """
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_bot': user.is_bot
    }


def validate_user_action(user_id: int, 
                        required_role: str, 
                        current_phase: str,
                        player_roles: Dict[int, str],
                        alive_players: List[int]) -> bool:
    """
    Validate if a user can perform a specific action.
    
    Args:
        user_id: User ID attempting action
        required_role: Role required for action
        current_phase: Current game phase
        player_roles: Role assignments
        alive_players: List of alive player IDs
        
    Returns:
        bool: True if action is valid
    """
    # Check if player is alive
    if user_id not in alive_players:
        return False
    
    # Check if player has required role
    if required_role and player_roles.get(user_id) != required_role:
        return False
    
    return True


def calculate_game_stats(players: List[Dict[str, Any]], 
                        roles: Dict[int, str],
                        alive_players: List[int]) -> Dict[str, int]:
    """
    Calculate current game statistics.
    
    Args:
        players: List of all players
        roles: Role assignments
        alive_players: List of alive player IDs
        
    Returns:
        Dictionary with game statistics
    """
    stats = {
        'total_players': len(players),
        'alive_players': len(alive_players),
        'dead_players': len(players) - len(alive_players),
        'alive_mafia': 0,
        'alive_villagers': 0,
        'alive_detective': 0,
        'alive_doctor': 0
    }
    
    for player_id in alive_players:
        role = roles.get(player_id, 'villager')
        if role == 'mafia':
            stats['alive_mafia'] += 1
        elif role == 'detective':
            stats['alive_detective'] += 1
        elif role == 'doctor':
            stats['alive_doctor'] += 1
        else:  # villager
            stats['alive_villagers'] += 1
    
    return stats
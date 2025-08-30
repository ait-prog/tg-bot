#telegram_mafia_config.py
"""
Configuration module for the Telegram Mafia Game Bot.
Contains all game settings, timers, and role distributions.
"""
import logging
# Logging configuration
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# Game settings
MIN_PLAYERS = 5
MAX_PLAYERS = 10
# Phase timers (in seconds)
NIGHT_PHASE_TIME = 120 # 2 minutes
DAY_PHASE_TIME = 180 # 3 minutes
VOTING_TIME = 60 # 1 minute for final voting
# Role distribution based on player count
ROLE_DISTRIBUTION = {
5: {'mafia': 1, 'detective': 1, 'doctor': 0, 'villagers': 3},
6: {'mafia': 1, 'detective': 1, 'doctor': 1, 'villagers': 3},
7: {'mafia': 2, 'detective': 1, 'doctor': 1, 'villagers': 3},
8: {'mafia': 2, 'detective': 1, 'doctor': 1, 'villagers': 4},
9: {'mafia': 2, 'detective': 1, 'doctor': 1, 'villagers': 5},
10: {'mafia': 3, 'detective': 1, 'doctor': 1, 'villagers': 5},
}
# UI Messages
MESSAGES = {
'game_started': '🎭 **MAFIA GAME STARTED!** 🎭\nCheck your private messages for your role!',
'night_phase': '🌙 **NIGHT PHASE** 🌙\nMafia, Detective, and Doctor: Check your DMs!',
'day_phase': '☀️ **DAY PHASE** ☀️\nDiscuss and vote to eliminate someone!',
'game_ended': '🎉 **GAME ENDED** 🎉',
'role_mafia': '🔪 You are **MAFIA**! Work with your team to eliminate villagers.',
'role_detective': '🔍 You are the **DETECTIVE**! Investigate players at night.',
'role_doctor': '🏥 You are the **DOCTOR**! Heal players at night.',
'role_villager': '👤 You are a **VILLAGER**! Find and eliminate the mafia.',
'vote_prompt': 'Vote to eliminate a player:',
'night_action_prompt': 'Choose your night action:',
'investigation_result': '🔍 Investigation result: {player} is {role}',
'healing_success': '🏥 You successfully healed {player}',
'kill_attempt': '🔪 The mafia attempted to kill {player}',
'kill_success': '💀 {player} was eliminated by the mafia',
'kill_prevented': '🏥 The doctor saved {player} from the mafia attack!',
'elimination': '⚰️ {player} was eliminated by vote',
'no_elimination': '🤝 No one was eliminated (tie vote)',
'villagers_win': '👥 **VILLAGERS WIN!** All mafia have been eliminated!',
'mafia_wins': '🔪 **MAFIA WINS!** They have taken control of the town!',
}
# Telegram Bot Token (set this to your actual bot token)
BOT_TOKEN = "8172833409:AAG3YW7YghViG0qbFDNZiybu8RkX54c4Z5o"
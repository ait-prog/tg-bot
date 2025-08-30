#telegram_mafia_bot_ui.py
# Неправильные отступы 
# Дублирование кода  callback

async def update_panel(self, chat_id: int):     # //починиил отступы
    """Update the game panel in the specified chat."""
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

# cursor починил дублирование но не везде 
# я б рефакторинг добавил что б дублирования не было 
async def _handle_action_callback(self, query, action: str, data_parts: list[str]):
    """Handle game action callback queries."""
    if len(data_parts) < 3:
        return
    
    target_id = int(data_parts[1])
    chat_id = int(data_parts[2])
    user_id = query.from_user.id
    
    # Process the action
    success = game_engine.process_player_action(chat_id, user_id, action, target_id)
    
    if not success:
        await query.edit_message_text("❌ Invalid action! You may not be able to perform this action.")
        return
    
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
    
    await query.edit_message_text(action_messages.get(action, f"✅ Action completed: {target_name}"))
    
    # Post-action processing
    if action == 'vote':
        await self.panel_updater.update_panel(chat_id)
    elif action == 'heal':
        await query.from_user.send_message(f"🏥 You will attempt to heal {target_name} tonight.")

async def _handle_cancel_callback(self, query, data_parts: list[str]):
    """Handle cancel callback queries."""
    try:
        await query.edit_message_text("❌ Action cancelled.")
    except Exception:
        pass
# Вынести токен
import os
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# В telegram_mafia_data.py убрать импорт PanelUpdater
# Использовать dependency injection вместо прямого импорта

# пока все надо чуть больше посидеть 

import json
from pathlib import Path
from datetime import datetime
import logging

from config.settings import DATA_FILE_PATH

logger = logging.getLogger(__name__)

DATA_FILE = Path(DATA_FILE_PATH)


def _json_serial(obj):
    """
    JSON serializer for objects not serializable by default json code
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    # Handle DiceGame objects specifically
    if obj.__class__.__name__ == 'DiceGame':
        return {
            '__type__': 'DiceGame',
            'match_id': obj.match_id,
            'chat_id': obj.chat_id,
            'state': obj.state,
            'bets': obj.bets,
            'participants': list(obj.participants),
            'result': obj.result,
            'created_at': obj.created_at.isoformat() if hasattr(obj, 'created_at') else datetime.now().isoformat()
        }
    # Handle objects with __dict__ attribute
    if isinstance(obj, object) and hasattr(obj, '__dict__'):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _json_deserial(obj):
    """
    JSON deserializer for objects that were serialized by _json_serial
    """
    if isinstance(obj, dict):
        # Handle DiceGame objects
        if obj.get('__type__') == 'DiceGame':
            from game.game_logic import DiceGame
            game = DiceGame(obj['match_id'], obj['chat_id'])
            game.state = obj['state']
            game.bets = obj['bets']
            game.participants = set(obj['participants'])
            game.result = obj['result']
            # Restore created_at timestamp
            if 'created_at' in obj:
                try:
                    game.created_at = datetime.fromisoformat(obj['created_at'])
                except ValueError:
                    game.created_at = datetime.now()
            else:
                game.created_at = datetime.now()
            return game
        
        # Handle datetime strings
        for key, value in obj.items():
            if isinstance(value, str):
                try:
                    # Attempt to deserialize ISO formatted datetime strings
                    obj[key] = datetime.fromisoformat(value)
                except ValueError:
                    pass
    return obj


def load_data(global_data_ref: dict) -> dict:
    """
    Loads data from the JSON file into the global_data_ref dictionary.
    Initializes a basic structure if the file doesn't exist.
    """
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                # Use object_hook for deserialization to handle datetime objects
                loaded_data = json.load(f, object_hook=_json_deserial)
                
                # DiceGame objects are now properly serializable
                
                # Update global_data_ref with loaded data
                global_data_ref.clear()
                global_data_ref.update(loaded_data)
                logger.info(f"Data loaded successfully from {DATA_FILE}")
                return global_data_ref
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from {DATA_FILE}: {e}")
                # Continue with empty global_data_ref
    else:
        logger.info(f"Data file {DATA_FILE} not found. Starting with empty data.")
    
    return global_data_ref


def save_data(global_data_ref: dict) -> bool:
    """
    Saves the global_data_ref dictionary to the JSON file.
    Returns True on success, False on failure.
    """
    try:
        # Create a copy of the data to avoid modifying the original
        data_to_save = {}
        data_to_save.update(global_data_ref)
        
        # DiceGame objects are now properly serializable
        
        # Ensure the directory exists
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the data to the file
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, default=_json_serial, indent=2, ensure_ascii=False)
        
        logger.info(f"Data saved successfully to {DATA_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error saving data to {DATA_FILE}: {e}", exc_info=True)
        return False
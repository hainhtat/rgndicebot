# file_manager.py
import json
from pathlib import Path
from datetime import datetime

DATA_FILE = Path("data.json")

def _json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    # Handle the DiceGame object if it appears directly in data
    # This assumes DiceGame has a to_dict method or is otherwise convertible
    # For simplicity, we'll convert it to None or an empty dict if not handled
    if isinstance(obj, object) and hasattr(obj, '__dict__'):
        # If it's a DiceGame object, we might want to store its essential attributes
        # For now, if current_game isn't designed for direct JSON serialization, it's safer
        # to ensure it's removed or converted before saving.
        # However, the current game_logic removes it from global_data when a game is over.
        # If it's still present, we need a robust way to serialize it or skip it.
        # Given the previous context, it's typically transient or explicitly handled.
        # For now, let's allow basic serialization of its __dict__.
        return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def _json_deserial(obj):
    """JSON deserializer for objects that were serialized by _json_serial"""
    if isinstance(obj, dict):
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
                # Manually restore DiceGame instances if necessary
                # This part needs careful consideration if DiceGame objects
                # are truly meant to be persisted. For now, they are treated as transient
                # and explicitly removed from 'current_game' on game over/stop.
                # If a game was active and the bot restarted, current_game would be None,
                # requiring a new game to be started.
                for chat_id, chat_data in loaded_data.get("all_chat_data", {}).items():
                    if "current_game" in chat_data:
                        # Clear any 'current_game' instances from previous runs as they are not serializable
                        # and need to be re-initialized by /newgame command.
                        del chat_data["current_game"]
                        print(f"Removed non-serializable 'current_game' from chat {chat_id} during load.")

                return loaded_data
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from '{DATA_FILE}': {e}")
                # Fallback to empty data on decode error
                return {}
    # If the file does not exist, return an empty dictionary.
    # The `constants.py` module will ensure initial structure is present.
    return {}

def save_data(data: dict):
    """
    Saves the provided data dictionary to the JSON file.
    Uses the custom serializer for datetime objects.
    """
    # Ensure current_game objects are not saved, as they are not JSON serializable
    # and should be transient.
    data_to_save = data.copy() # Work on a copy to avoid modifying the live global_data during iteration
    for chat_id, chat_data in data_to_save.get("all_chat_data", {}).items():
        if "current_game" in chat_data:
            # Create a temporary copy of chat_data without current_game for serialization
            temp_chat_data = chat_data.copy()
            del temp_chat_data["current_game"]
            data_to_save["all_chat_data"][chat_id] = temp_chat_data
            
    DATA_FILE.write_text(json.dumps(data_to_save, indent=2, ensure_ascii=False, default=_json_serial), encoding="utf-8")

def ensure_key(data: dict, key: str, default: dict):
    """
    Ensures a given key exists in the dictionary with a default value if not present.
    Returns the value associated with the key.
    """
    if key not in data:
        data[key] = default
    return data[key]

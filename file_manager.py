import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Define the path for the data file.
# Using 'data.json' in the current working directory.
DATA_FILE = "data.json"

def _json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    # This function converts datetime objects to ISO format strings
    # before they are saved to JSON.
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def _json_deserial(obj):
    """JSON deserializer for objects that were serialized by _json_serial"""
    # This function attempts to convert ISO format strings back to datetime objects
    # after loading from JSON.
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                try:
                    # Attempt to parse as datetime (handles various ISO formats)
                    obj[key] = datetime.fromisoformat(value)
                except ValueError:
                    pass # Not a datetime string, keep as is
    return obj

def load_data(global_data_ref: dict):
    """
    Loads all bot data (admin_data and all_chat_data) from the JSON file
    into the provided global_data_ref dictionary.
    Handles potential duplicate admin IDs by consolidating them.
    """
    # --- NEW: Ensure base structure exists before loading ---
    global_data_ref.setdefault("all_chat_data", {})
    global_data_ref.setdefault("admin_data", {})
    global_data_ref.setdefault("global_user_data", {})
    
    if not os.path.exists(DATA_FILE):
        logger.info(f"Data file '{DATA_FILE}' not found. Initializing with empty data.")
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            # Load the data first without immediate deserialization of complex types,
            # so we can process potential duplicates in admin_data as raw dicts.
            loaded_raw_data = json.load(f)
            
            # --- Handle admin_data consolidation and deserialization ---
            # Create a temporary dictionary to store the consolidated admin data.
            # This ensures only one entry per admin_id is kept, prioritizing the last one if duplicates exist in file.
            consolidated_admin_data = {}
            for admin_id_str, admin_entry_raw in loaded_raw_data.get("admin_data", {}).items():
                try:
                    admin_id = int(admin_id_str) # Ensure admin_id is an integer key
                    processed_admin_entry = _json_deserial(admin_entry_raw) # Deserialize datetime if present
                    
                    # Ensure basic fields exist or are defaulted
                    processed_admin_entry.setdefault("username", f"User {admin_id_str}") # Use string for fallback
                    if "last_refill" in processed_admin_entry and isinstance(processed_admin_entry["last_refill"], str):
                        try:
                            processed_admin_entry["last_refill"] = datetime.fromisoformat(processed_admin_entry["last_refill"])
                        except ValueError:
                            processed_admin_entry["last_refill"] = None # Fallback if parsing fails
                    
                    # Ensure chat_points keys (chat_id) are integers
                    if "chat_points" in processed_admin_entry:
                        new_chat_points = {}
                        for c_id_str, c_points_raw in processed_admin_entry["chat_points"].items():
                            try:
                                c_id = int(c_id_str)
                                processed_c_points = _json_deserial(c_points_raw)
                                if "last_refill" in processed_c_points and isinstance(processed_c_points["last_refill"], str):
                                    try:
                                        processed_c_points["last_refill"] = datetime.fromisoformat(processed_c_points["last_refill"])
                                    except ValueError:
                                        processed_c_points["last_refill"] = None
                                new_chat_points[c_id] = processed_c_points
                            except ValueError:
                                logger.warning(f"Skipping non-integer chat_id_str in admin_data for admin {admin_id_str}: {c_id_str}")
                        processed_admin_entry["chat_points"] = new_chat_points

                    consolidated_admin_data[admin_id] = processed_admin_entry
                except ValueError:
                    logger.warning(f"Skipping non-integer admin_id_str found in data.json: {admin_id_str}")
                except Exception as e:
                    logger.error(f"Error processing admin data for ID {admin_id_str}: {e}", exc_info=True)
            
            global_data_ref["admin_data"] = consolidated_admin_data
            # --- End admin_data consolidation ---

            # --- Process all_chat_data separately for player_stats and match_history ---
            consolidated_all_chat_data = {}
            for chat_id_str, chat_entry_raw in loaded_raw_data.get("all_chat_data", {}).items():
                try:
                    chat_id = int(chat_id_str) # Ensure chat_id is an integer key
                    processed_chat_entry = _json_deserial(chat_entry_raw) # Deserialize datetime if present in top level
                    
                    # Process player_stats within this chat entry
                    # Create a new dictionary to populate and then replace
                    new_player_stats = {}
                    for user_id_str, player_stats_raw in list(processed_chat_entry.get("player_stats", {}).items()): # Iterate over a copy
                        try:
                            # User IDs in player_stats are stored as STRINGS for consistency
                            user_id_key = user_id_str 
                            processed_player_stats = _json_deserial(player_stats_raw)
                            processed_player_stats.setdefault("username", f"User {user_id_str}") # Use string for fallback
                            if isinstance(processed_player_stats.get('last_active'), str):
                                try:
                                    processed_player_stats['last_active'] = datetime.fromisoformat(processed_player_stats['last_active'])
                                except ValueError:
                                    logger.warning(f"Failed to parse last_active datetime for user {user_id_str} in chat {chat_id}: {processed_player_stats['last_active']}")
                                    processed_player_stats['last_active'] = datetime.now() # Fallback
                            
                            new_player_stats[user_id_key] = processed_player_stats # Add to new dict with string key
                        except Exception as e: # Catch any other potential errors during processing
                            logger.error(f"Error processing player stats for user {user_id_str} in chat {chat_id}: {e}", exc_info=True)
                    processed_chat_entry["player_stats"] = new_player_stats # Replace the old dict with the new one

                    # Process match_history within this chat entry
                    processed_match_history = []
                    for match_entry_raw in processed_chat_entry.get("match_history", []):
                        processed_match_entry = _json_deserial(match_entry_raw)
                        if isinstance(processed_match_entry.get('timestamp'), str):
                            try:
                                processed_match_entry['timestamp'] = datetime.fromisoformat(processed_match_entry['timestamp'])
                            except ValueError:
                                logger.warning(f"Failed to parse timestamp for match {processed_match_entry.get('match_id')} in chat {chat_id}: {processed_match_entry['timestamp']}")
                                processed_match_entry['timestamp'] = datetime.now() # Fallback
                        processed_match_history.append(processed_match_entry)
                    processed_chat_entry["match_history"] = processed_match_history

                    consolidated_all_chat_data[chat_id] = processed_chat_entry
                except ValueError:
                    logger.warning(f"Skipping non-integer chat_id_str found in data.json: {chat_id_str}")
                except Exception as e:
                    logger.error(f"Error processing chat data for ID {chat_id_str}: {e}", exc_info=True)

            global_data_ref["all_chat_data"] = consolidated_all_chat_data
            # --- End all_chat_data processing ---

            # --- NEW: Process global_user_data ---
            processed_global_user_data = {}
            for user_id_str, user_entry_raw in loaded_raw_data.get("global_user_data", {}).items():
                try:
                    # User IDs in global_user_data are stored as STRINGS
                    user_id_key = user_id_str 
                    user_entry_raw.setdefault("full_name", f"User {user_id_str}") # Use string for fallback
                    user_entry_raw.setdefault("username", None)
                    user_entry_raw.setdefault("referral_points", 0)
                    user_entry_raw.setdefault("referred_by", None)
                    user_entry_raw.setdefault("pending_referrer_id", None)
                    processed_global_user_data[user_id_key] = user_entry_raw # Store with string key
                except Exception as e: # Catch any other potential errors during processing
                    logger.error(f"Error processing global_user_data for ID {user_id_str}: {e}", exc_info=True)
            global_data_ref["global_user_data"] = processed_global_user_data
            # --- END NEW ---\n
        logger.info(f"Successfully loaded and consolidated data from '{DATA_FILE}'.")

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from '{DATA_FILE}': {e}. Initializing with empty data.", exc_info=True)
        global_data_ref["all_chat_data"] = {}
        global_data_ref["admin_data"] = {}
        global_data_ref["global_user_data"] = {}
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading data from '{DATA_FILE}': {e}. Initializing with empty data.", exc_info=True)
        global_data_ref["all_chat_data"] = {}
        global_data_ref["admin_data"] = {}
        global_data_ref["global_user_data"] = {}


def save_data(global_data_to_save: dict):
    """
    Saves all bot data (admin_data and all_chat_data) to the JSON file.
    """
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            # Use the custom serializer to handle datetime objects
            json.dump(global_data_to_save, f, ensure_ascii=False, indent=4, default=_json_serial)
        logger.debug(f"Successfully saved data to '{DATA_FILE}'.")
    except IOError as e:
        logger.error(f"Error writing data to '{DATA_FILE}': {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred while saving data to '{DATA_FILE}': {e}", exc_info=True)


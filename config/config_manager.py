import os
import json
import logging
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    # Bot settings
    "bot": {
        "name": "Dice Game Bot",
        "version": "1.0.0",
        "description": "A Telegram bot for playing dice games"
    },
    
    # Game settings
    "game": {
        "initial_player_score": 0,
        "admin_initial_points": 10000,
        "referral_bonus_points": 500,
        "auto_roll_interval_seconds": 5,
        "betting_time_seconds": 60,
        "payout_multipliers": {
            "big": 2.0,
            "small": 2.0,
            "lucky": 5.0
        }
    },
    
    # Data settings
    "data": {
        "data_file_path": "data.json",
        "backup_directory": "backups",
        "max_history_entries": 50,
        "save_interval_minutes": 5
    },
    
    # Timezone settings
    "timezone": "Asia/Yangon",
    
    # Logging settings
    "logging": {
        "level": "INFO",
        "file": "logs/bot.log",
        "max_file_size_mb": 10,
        "backup_count": 5,
        "json_format": False
    }
}


class ConfigManager:
    """Manages configuration settings for the application"""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize the configuration manager
        
        Args:
            config_file: Path to the configuration file. If None, uses default values.
        """
        # Load environment variables
        load_dotenv()
        
        # Initialize with default configuration
        self.config = DEFAULT_CONFIG.copy()
        
        # Load configuration from file if provided
        if config_file:
            self.config_file = Path(config_file)
            self._load_from_file()
        else:
            self.config_file = None
            
        # Override with environment variables
        self._load_from_env()
        
        logger.info(f"Configuration initialized from {config_file if config_file else 'defaults'}")
    
    def _load_from_file(self) -> None:
        """Load configuration from a JSON file"""
        if self.config_file and self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                    # Update config with file values (deep merge)
                    self._deep_update(self.config, file_config)
                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.error(f"Error loading configuration from {self.config_file}: {e}")
        else:
            logger.warning(f"Configuration file {self.config_file} not found, using defaults")
    
    def _load_from_env(self) -> None:
        """Override configuration with environment variables
        
        Environment variables should be in the format:
        DICEBOT_SECTION_KEY=value
        
        For example:
        DICEBOT_GAME_INITIAL_PLAYER_SCORE=2000
        """
        prefix = "DICEBOT_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Remove prefix and split into parts
                parts = key[len(prefix):].lower().split('_')
                
                # Need at least section and key
                if len(parts) < 2:
                    continue
                
                # First part is the section, rest is the key (with underscores)
                section = parts[0]
                config_key = '_'.join(parts[1:])
                
                # Skip if section doesn't exist in config
                if section not in self.config:
                    continue
                
                # Convert value to appropriate type
                typed_value = self._convert_value_type(value)
                
                # Update config
                self.config[section][config_key] = typed_value
                logger.debug(f"Overrode config {section}.{config_key} with environment value: {typed_value}")
    
    def _convert_value_type(self, value: str) -> Union[str, int, float, bool, List, Dict]:
        """Convert string value to appropriate type"""
        # Try to convert to boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        
        # Try to convert to number
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Try to convert to JSON (for lists and dicts)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
        
        # Default to string
        return value
    
    def _deep_update(self, target: Dict, source: Dict) -> None:
        """Recursively update a dictionary"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value
        
        Args:
            section: The configuration section
            key: The configuration key
            default: Default value if not found
            
        Returns:
            The configuration value or default
        """
        try:
            return self.config[section][key]
        except KeyError:
            return default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section
        
        Args:
            section: The configuration section
            
        Returns:
            The configuration section as a dictionary
        """
        return self.config.get(section, {})
    
    def set(self, section: str, key: str, value: Any) -> None:
        """Set a configuration value
        
        Args:
            section: The configuration section
            key: The configuration key
            value: The value to set
        """
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
    
    def save(self, config_file: Optional[str] = None) -> bool:
        """Save the configuration to a file
        
        Args:
            config_file: Path to save the configuration to. If None, uses the original file.
            
        Returns:
            True if successful, False otherwise
        """
        file_path = Path(config_file) if config_file else self.config_file
        
        if not file_path:
            logger.error("No configuration file specified for saving")
            return False
        
        try:
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write config to file
            with open(file_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            logger.info(f"Configuration saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration to {file_path}: {e}")
            return False


# Global configuration instance
_config_instance = None


def get_config(config_file: Optional[str] = None) -> ConfigManager:
    """Get the global configuration instance
    
    Args:
        config_file: Path to the configuration file. Only used on first call.
        
    Returns:
        The global ConfigManager instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager(config_file)
    return _config_instance
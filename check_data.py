import json
import sys
from data.file_manager import load_data
from config.constants import global_data

# Load data into global_data
load_data(global_data)

# Print the global_data
print(json.dumps(global_data, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o), indent=2))
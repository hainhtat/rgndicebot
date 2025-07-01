#!/usr/bin/env python3
"""
Simple test to check if the function can be called
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Disable database mode for testing
os.environ['USE_DATABASE'] = 'False'
os.environ['LOG_LEVEL'] = 'CRITICAL'

def simple_test():
    print("Simple test function called successfully!")
    return True

if __name__ == "__main__":
    print("=== Function Call Test ===")
    print("About to call simple_test()")
    result = simple_test()
    print(f"simple_test() returned: {result}")
    print("Test completed.")
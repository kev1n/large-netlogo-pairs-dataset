#!/usr/bin/env python3

"""
Test script for demonstrating the refactored NetLogo parser with LLM pseudocode generation.
"""

import os
import sys
import json
from pathlib import Path
from parsers.models_library import ModelsLibraryParser

def main():
    """Main entry point for the test script."""
    # Get the base directory from command line or use the current directory
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Create a parser instance
    parser = ModelsLibraryParser(base_dir)
    
    # Find and print the number of NetLogo files
    netlogo_files = parser.find_netlogo_files()
    print(f"Found {len(netlogo_files)} NetLogo files in {base_dir}")
    
    # Process the first file for demonstration
    if netlogo_files:
        first_file = netlogo_files[0]
        print(f"\nProcessing {first_file}...")
        
        # Process the file
        model_data = parser.process_file(first_file)
        
        # Save the result to a JSON file
        output_file = "test_output.json"
        parser.save_to_json(output_file)
        
        # Print a summary
        num_procedures = len(model_data["procedures"])
        print(f"\nSuccessfully processed {first_file}")
        print(f"  - Model ID: {model_data['modelId']}")
        print(f"  - Title: {model_data['title']}")
        print(f"  - Procedures: {num_procedures}")
        print(f"\nOutput saved to {output_file}")
    else:
        print("No NetLogo files found.")

if __name__ == "__main__":
    main() 
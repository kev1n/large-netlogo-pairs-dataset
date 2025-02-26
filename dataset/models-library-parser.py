#!/usr/bin/env python3

from parsers import ModelsLibraryParser
import os
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Process NetLogo model files and generate pseudocode')
    parser.add_argument('--base-dir', default='dataset/models-library',
                        help='Directory containing NetLogo model files (default: dataset/models-library)')
    parser.add_argument('--output', default='dataset/netlogo_models.json',
                        help='Output JSON file path (default: dataset/netlogo_models.json)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume processing from the existing output file')
    args = parser.parse_args()
    
    # Create the NetLogo models parser
    netlogo_parser = ModelsLibraryParser(args.base_dir)
    
    # Set the output file for incremental saves
    output_file = args.output
    netlogo_parser.output_file = output_file
    
    # Attempt to resume from existing output if requested
    if args.resume and os.path.exists(output_file):
        print(f"Attempting to resume from {output_file}...")
        if netlogo_parser.load_from_json(output_file):
            print(f"Successfully loaded {len(netlogo_parser.models)} models from {output_file}")
        else:
            print(f"Could not resume from {output_file}, starting from scratch")
    
    print(f"Processing NetLogo files from {args.base_dir}...")
    print(f"Results will be incrementally saved to {output_file}")
    
    # Process all files (this will perform incremental saves)
    netlogo_parser.process_all_files()
    
    # Final save
    print(f"Performing final save to {output_file}...")
    netlogo_parser.save_to_json(output_file)
    print("Done!")

if __name__ == "__main__":
    main() 
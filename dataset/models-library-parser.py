#!/usr/bin/env python3

from parsers import ModelsLibraryParser

def main():
    # Example usage with Models Library
    base_dir = "dataset/models-library"
    parser = ModelsLibraryParser(base_dir)
    
    print("Processing NetLogo files...")
    parser.process_all_files()
    
    output_file = "dataset/netlogo_models.json"
    print(f"Saving results to {output_file}...")
    parser.save_to_json(output_file)
    print("Done!")

if __name__ == "__main__":
    main() 
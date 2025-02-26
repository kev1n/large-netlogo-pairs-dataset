#!/usr/bin/env python3

import json
import argparse
import re
import random
from pathlib import Path
from typing import List, Dict, Any, Tuple

def strip_netlogo_comments(code: str) -> str:
    """
    Remove comments from NetLogo code.
    Comments in NetLogo start with semicolons (;).
    
    Args:
        code: Original NetLogo code with comments
        
    Returns:
        Code with comments removed
    """
    # Split the code into lines
    lines = code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove everything after a semicolon (;)
        comment_pos = line.find(';')
        if comment_pos >= 0:
            line = line[:comment_pos]
        
        # Only include non-empty lines
        if line.strip():
            cleaned_lines.append(line)
    
    # Join the lines back together
    return '\n'.join(cleaned_lines)

def strip_line_numbers_and_comments_from_pseudocode(pseudocode: List[str]) -> str:
    """
    Remove line numbers and comments from pseudocode while preserving spacing.
    
    Args:
        pseudocode: List of pseudocode lines with line numbers
    
    Returns:
        Pseudocode as a string without line numbers or comments but with preserved spacing
    """
    # Process each line
    processed_lines = []
    for line in pseudocode:
        # Skip entirely comment-only lines
        if line.strip().startswith(";;") or line.strip().startswith(";"):
            continue
            
        # Match the line number pattern (digits followed by |)
        match = re.match(r'^\s*\d+\s*\|\s?(.*)', line)
        if match:
            # Extract the content after the line number
            content = match.group(1)
            
            # Skip if the line is just a comment
            if content.strip().startswith(";;") or content.strip().startswith(";"):
                continue
                
            # Remove any comments from the middle or end of the line
            comment_pos = content.find(';')
            if comment_pos >= 0:
                content = content[:comment_pos]
            
            # Check for "Comment:" text and remove it
            comment_text_pos = content.lower().find('comment:')
            if comment_text_pos >= 0:
                content = content[:comment_text_pos]
            
            # Add the line if it's not empty after processing
            if content.strip():
                processed_lines.append(content)
    
    # Join the processed lines
    return '\n'.join(processed_lines)

def create_training_pair(procedure: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a training pair for fine-tuning from a procedure.
    
    Args:
        procedure: Dictionary containing procedure data
        
    Returns:
        Dictionary formatted for fine-tuning with messages
    """
    # Check if required fields exist
    if not all(key in procedure for key in ['originalCode', 'pseudoCode', 'variables']):
        return None
    
    # Skip if pseudoCode is empty
    if not procedure['pseudoCode']:
        return None
    
    # Clean the original code by removing comments
    clean_code = strip_netlogo_comments(procedure['originalCode'])
    
    # If after removing comments the code is empty, skip this procedure
    if not clean_code.strip():
        return None
    
    # Convert pseudoCode list to string without line numbers and comments
    pseudocode_text = strip_line_numbers_and_comments_from_pseudocode(procedure['pseudoCode'])
    
    # If after removing comments the pseudocode is empty, skip this procedure
    if not pseudocode_text.strip():
        return None
    
    # Format variables as XML-style tag for better recognition by the model
    variables_text = ""
    if procedure['variables'] and len(procedure['variables']) > 0:
        variables_text = f"<variables>{', '.join(procedure['variables'])}</variables>"
    
    # Create messages array with user input (pseudocode) and assistant output (code)
    messages = [
        {
            "role": "user",
            "content": f"Generate NetLogo code based on the following pseudocode:\n\n{pseudocode_text}\n\n{variables_text}"
        },
        {
            "role": "assistant",
            "content": f"```netlogo\n{clean_code}\n```"
        }
    ]
    
    return {"messages": messages}

def process_netlogo_models(input_file: str, output_file: str, validation_file: str = None, validation_pct: float = 0.05) -> Tuple[int, int]:
    """
    Process NetLogo models JSON file and create a JSONL file for fine-tuning.
    
    Args:
        input_file: Path to input JSON file
        output_file: Path to output JSONL file
        validation_file: Path to validation JSONL file
        validation_pct: Percentage of data to use for validation (0.0 to 1.0)
        
    Returns:
        Tuple of (training_count, validation_count) - number of examples in each set
    """
    print(f"Reading NetLogo models from {input_file}...")
    
    # Load input JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    models = data.get('models', [])
    print(f"Found {len(models)} models")
    
    # Count total procedures
    total_procedures = sum(len(model.get('procedures', [])) for model in models)
    print(f"Found {total_procedures} total procedures")
    
    # Create output directories if they don't exist
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if validation_file:
        validation_path = Path(validation_file)
        validation_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Process procedures and collect valid training pairs
    all_pairs = []
    for model in models:
        model_id = model.get('modelId', 'unknown')
        procedures = model.get('procedures', [])
        
        for procedure in procedures:
            # Skip procedures without code or pseudocode
            if not procedure.get('originalCode') or not procedure.get('pseudoCode'):
                continue
            
            # Create training pair
            training_pair = create_training_pair(procedure)
            if training_pair:
                all_pairs.append(training_pair)
    
    # Shuffle the pairs for randomization
    random.shuffle(all_pairs)
    
    # Calculate validation split if validation file is specified
    train_pairs = all_pairs
    valid_pairs = []
    
    if validation_file and validation_pct > 0:
        # Calculate number of validation examples
        valid_count = max(1, int(len(all_pairs) * validation_pct))
        
        # Split the data
        valid_pairs = all_pairs[:valid_count]
        train_pairs = all_pairs[valid_count:]
        
        print(f"Creating {len(valid_pairs)} validation pairs ({validation_pct*100:.1f}%) and {len(train_pairs)} training pairs")
    else:
        print(f"Creating {len(train_pairs)} training pairs (no validation set)")
    
    # Write training pairs to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        for pair in train_pairs:
            f.write(json.dumps(pair) + '\n')
    
    # Write validation pairs if validation file is specified
    if validation_file and valid_pairs:
        with open(validation_file, 'w', encoding='utf-8') as f:
            for pair in valid_pairs:
                f.write(json.dumps(pair) + '\n')
        print(f"Created {len(valid_pairs)} validation pairs in {validation_file}")
    
    print(f"Created {len(train_pairs)} training pairs in {output_file}")
    return len(train_pairs), len(valid_pairs)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert NetLogo models to fine-tuning JSONL format using pseudocode')
    parser.add_argument('--input', type=str, default='dataset/netlogo_models.json',
                        help='Path to input NetLogo models JSON file')
    parser.add_argument('--output', type=str, default='dataset/netlogo_finetune_from_pseudocode.jsonl',
                        help='Path to output JSONL file for fine-tuning')
    parser.add_argument('--validation', type=str, default='dataset/netlogo_finetune_from_pseudocode_validation.jsonl',
                        help='Path to validation JSONL file (set to empty string to disable)')
    parser.add_argument('--validation-pct', type=float, default=0.05,
                        help='Percentage of data to use for validation (default: 0.05 or 5%%)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')
    args = parser.parse_args()
    
    # Set random seed for reproducibility
    random.seed(args.seed)
    
    # Process the models
    validation_file = args.validation if args.validation else None
    process_netlogo_models(args.input, args.output, validation_file, args.validation_pct)

if __name__ == "__main__":
    main() 
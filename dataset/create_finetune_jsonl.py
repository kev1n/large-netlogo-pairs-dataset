#!/usr/bin/env python3

import json
import argparse
import re
from pathlib import Path
from typing import List, Dict, Any

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

def clean_summary(summary: str) -> str:
    """
    Clean summary text by removing any comment markers.
    
    Args:
        summary: Original summary text
        
    Returns:
        Cleaned summary text without comment markers
    """
    # Split the summary into lines
    lines = summary.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Skip entirely comment-only lines
        if line.strip().startswith(";;") or line.strip().startswith(";"):
            continue
        
        # Remove any comments from the middle or end of the line
        comment_pos = line.find(';')
        if comment_pos >= 0:
            line = line[:comment_pos]
        
        # Check for "Comment:" text and remove it
        comment_text_pos = line.lower().find('comment:')
        if comment_text_pos >= 0:
            line = line[:comment_text_pos]
        
        # Only include non-empty lines
        if line.strip():
            cleaned_lines.append(line)
    
    # Join the lines back together
    return '\n'.join(cleaned_lines)

def create_training_pair(procedure: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a training pair for fine-tuning from a procedure.
    
    Args:
        procedure: Dictionary containing procedure data
        
    Returns:
        Dictionary formatted for fine-tuning with messages
    """
    # Check if required fields exist
    if not all(key in procedure for key in ['originalCode', 'summary', 'variables']):
        return None
    
    # Clean the code by removing comments
    clean_code = strip_netlogo_comments(procedure['originalCode'])
    
    # If after removing comments the code is empty, skip this procedure
    if not clean_code.strip():
        return None
    
    # Clean the summary by removing any comment markers
    clean_summary_text = clean_summary(procedure['summary'])
    
    # If after cleaning the summary is empty, skip this procedure
    if not clean_summary_text.strip():
        return None
    
    # Format variables as XML-style tag for better recognition by the model
    variables_text = ""
    if procedure['variables'] and len(procedure['variables']) > 0:
        variables_text = f"<variables>{', '.join(procedure['variables'])}</variables>"
    
    # Create messages array with user input (summary) and assistant output (code)
    messages = [
        {
            "role": "user",
            "content": f"Generate NetLogo code that implements the following summary:\n\n{clean_summary_text}\n\n{variables_text}"
        },
        {
            "role": "assistant",
            "content": f"```netlogo\n{clean_code}\n```"
        }
    ]
    
    return {"messages": messages}

def process_netlogo_models(input_file: str, output_file: str) -> None:
    """
    Process NetLogo models JSON file and create a JSONL file for fine-tuning.
    
    Args:
        input_file: Path to input JSON file
        output_file: Path to output JSONL file
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
    
    # Create output directory if it doesn't exist
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Process procedures and write to JSONL file
    valid_pairs = 0
    with open(output_file, 'w', encoding='utf-8') as f:
        for model in models:
            model_id = model.get('modelId', 'unknown')
            procedures = model.get('procedures', [])
            
            for procedure in procedures:
                # Skip procedures without code or summary
                if not procedure.get('originalCode') or not procedure.get('summary'):
                    continue
                
                # Create training pair
                training_pair = create_training_pair(procedure)
                if training_pair:
                    # Write as JSON line
                    f.write(json.dumps(training_pair) + '\n')
                    valid_pairs += 1
    
    print(f"Created {valid_pairs} training pairs in {output_file}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert NetLogo models to fine-tuning JSONL format')
    parser.add_argument('--input', type=str, default='dataset/netlogo_models.json',
                        help='Path to input NetLogo models JSON file')
    parser.add_argument('--output', type=str, default='dataset/netlogo_finetune.jsonl',
                        help='Path to output JSONL file for fine-tuning')
    args = parser.parse_args()
    
    # Process the models
    process_netlogo_models(args.input, args.output)

if __name__ == "__main__":
    main() 
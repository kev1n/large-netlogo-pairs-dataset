#!/usr/bin/env python3

import json
import re
import os
import requests
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from utils.llm_pseudocode_generator import LLMPseudocodeGenerator

class NetLogoModelParser(ABC):
    """Abstract base class for NetLogo model parsers."""
    
    def __init__(self, base_dir: str, model_name: str = "mistral/codestral-2501"):
        self.base_dir = Path(base_dir)
        self.models = []
        # Get the formatter URL from environment variable or use default
        self.formatter_url = os.environ.get('NETLOGO_FORMATTER_URL', 'http://localhost:3000/prettify')
        # Initialize the pseudocode generator
        self.pseudocode_generator = LLMPseudocodeGenerator(model_name)
        # Output file path for incremental saves
        self.output_file = None
    
    def format_netlogo_code(self, content: str) -> str:
        """Format NetLogo code using the API formatter."""
        try:
            print("  Formatting code using API...")
            response = requests.post(
                self.formatter_url,
                json={
                    "code": content,
                    "lineWidth": 80
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                formatted_code = response.json().get("formatted", content)
                print("  Formatting complete")
                return formatted_code
            else:
                print(f"  Warning: Formatting API returned status {response.status_code}")
                return content
                
        except Exception as e:
            print(f"  Warning: Code formatting failed: {str(e)}")
            return content  # Return original content if formatting fails
    
    def extract_procedures(self, content: str) -> List[Dict]:
        """Extract procedures from NetLogo file content."""
        # Format the code first
        # DISABLED FOR NOW, MEMORY LEAK INSIDE OF THE API
        #content = self.format_netlogo_code(content)
        
        procedures = []
        # Split content into lines for easier processing
        lines = content.split('\n')
        
        # Pattern to match procedure start
        proc_start_pattern = re.compile(r'^(to(?:-report)?)\s+([^\s\[]+)')
        
        # Pattern to match comments
        comment_pattern = re.compile(r'^\s*;(.+)$')
        
        i = 0
        while i < len(lines):
            # Collect preceding comments
            preceding_comments = []
            while i < len(lines) and (comment_match := comment_pattern.match(lines[i])):
                preceding_comments.append(comment_match.group(1).strip())
                i += 1
            
            # Check if next line is a procedure
            if i < len(lines) and (proc_match := proc_start_pattern.match(lines[i])):
                proc_name = proc_match.group(2)
                
                # Get the full procedure content
                proc_lines = []
                proc_start = i
                
                # Find the matching 'end'
                while i < len(lines):
                    proc_lines.append(lines[i])
                    if lines[i].strip() == 'end':
                        break
                    i += 1
                
                if i < len(lines):  # Only if we found the 'end'
                    proc_content = '\n'.join(proc_lines)
                    
                    # Check for inline comment on procedure definition line
                    inline_comment = ''
                    inline_match = re.search(r';(.+)$', lines[proc_start])
                    if inline_match:
                        inline_comment = inline_match.group(1).strip()
                    
                    # Combine documentation
                    doc_lines = preceding_comments
                    if inline_comment:
                        doc_lines.append(inline_comment)
                    
                    # Create the procedure object with numbered original code as a list
                    numbered_code = self.pseudocode_generator.format_code_with_line_numbers(proc_content.strip())
                    
                    procedure = {
                        "name": proc_name,
                        "documentation": '\n'.join(doc_lines) if doc_lines else "",
                        "originalCode": proc_content.strip(),
                        "numberedOriginalCode": numbered_code,
                        "pseudoCode": [],
                        "codeToPseudoCodeMap": [],  # Will store the 1:1 mapping
                        "summary": "",              # Will store the procedure summary
                        "variables": []             # Will store the non-primitive variables
                    }
                    procedures.append(procedure)
            
            i += 1
        
        return procedures

    def generate_pseudocode_for_procedure(self, procedure: Dict) -> Dict:
        """Generate pseudocode for a NetLogo procedure using LLM.
        
        This is a wrapper around the pseudocode generator's method that handles
        incremental saving.
        """
        # Call the generator to create pseudocode
        procedure = self.pseudocode_generator.generate_pseudocode(procedure)
        
        # Save incremental progress if output_file is set
        if self.output_file:
            self._save_incremental_progress()
        
        return procedure
    
    def _save_incremental_progress(self):
        """Save the current state of models to the output file."""
        if not self.output_file:
            return
            
        try:
            print(f"Saving incremental progress to {self.output_file}...")
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "models": self.models,
                    "totalModels": len(self.models),
                    "generatedAt": datetime.now().isoformat(),
                    "_incremental": True
                }, f, indent=2)
            print("Incremental save completed")
        except Exception as e:
            print(f"Warning: Failed to save incremental progress: {str(e)}")
    
    @abstractmethod
    def extract_documentation(self, content: str) -> str:
        """Extract documentation from model content."""
        pass

    @abstractmethod
    def construct_source_link(self, relative_path: Path) -> str:
        """Construct source link for the model."""
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """Return the source type for this parser."""
        pass

    @abstractmethod
    def get_license(self) -> str:
        """Return the license for models from this source."""
        pass

    def find_netlogo_files(self) -> List[Path]:
        """Recursively find all .nlogo files in the base directory."""
        netlogo_files = []
        for path in self.base_dir.rglob('*.nlogo'):
            netlogo_files.append(path)
        return netlogo_files

    def process_file(self, file_path: Path) -> Dict:
        """Process a single NetLogo file and return its metadata."""
        relative_path = file_path.relative_to(self.base_dir)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Generate a unique model ID based on the file path
        model_id = str(relative_path).replace('/', '_').replace('.nlogo', '')
        
        # Extract title from filename or first line of documentation
        title = file_path.stem.replace('-', ' ')
        
        model_data = {
            "modelId": model_id,
            "title": title,
            "documentation": self.extract_documentation(content),
            "sourceLink": self.construct_source_link(relative_path),
            "license": self.get_license(),
            "sourceType": self.get_source_type(),
            "collectedAt": datetime.now().isoformat(),
            "procedures": self.extract_procedures(content)
        }
        
        # Add the model to the models list first so it's included in incremental saves
        self.models.append(model_data)
        
        # Save incremental progress when we've added a new model
        if self.output_file:
            self._save_incremental_progress()
        
        # Generate pseudocode for each procedure
        print(f"Generating pseudocode for {len(model_data['procedures'])} procedures...")
        for i, procedure in enumerate(model_data['procedures']):
            print(f"  Processing procedure {i+1}/{len(model_data['procedures'])}: {procedure['name']}")
            model_data['procedures'][i] = self.generate_pseudocode_for_procedure(procedure)
        
        return model_data

    def process_all_files(self) -> List[Dict]:
        """Process all NetLogo files in the directory."""
        netlogo_files = self.find_netlogo_files()
        total_files = len(netlogo_files)
        print(f"Found {total_files} NetLogo files to process")
        
        for i, file_path in enumerate(netlogo_files, 1):
            try:
                print(f"\nProcessing file {i}/{total_files}: {file_path}")
                model_data = self.process_file(file_path)
                # Note: model is already added to self.models in process_file
                print(f"Successfully processed {file_path}")
                
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                # Save progress even if we encounter an error
                if self.output_file:
                    self._save_incremental_progress()
        
        return self.models

    def save_to_json(self, output_file: str):
        """Save the processed models to a JSON file.
        Also sets this as the output file for incremental saves."""
        self.output_file = output_file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "models": self.models,
                "totalModels": len(self.models),
                "generatedAt": datetime.now().isoformat()
            }, f, indent=2)

    def load_from_json(self, input_file: str):
        """Load previously processed models from a JSON file.
        This allows resuming processing from a previous incremental save."""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.models = data.get("models", [])
                print(f"Loaded {len(self.models)} models from {input_file}")
                return True
        except Exception as e:
            print(f"Error loading from {input_file}: {str(e)}")
            return False
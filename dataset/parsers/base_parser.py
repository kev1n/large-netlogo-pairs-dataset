#!/usr/bin/env python3

import json
import re
import os
import requests
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from env import MISTRAL_API_KEY

class NetLogoModelParser(ABC):
    """Abstract base class for NetLogo model parsers."""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.models = []
        # Get the formatter URL from environment variable or use default
        self.formatter_url = os.environ.get('NETLOGO_FORMATTER_URL', 'http://localhost:3000/prettify')
    
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

    @abstractmethod
    def extract_documentation(self, content: str) -> str:
        """Extract documentation from model content."""
        pass

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
                    
                    procedure = {
                        "name": proc_name,
                        "documentation": '\n'.join(doc_lines) if doc_lines else "",
                        "originalCode": proc_content.strip(),
                        "pseudoCode": []
                    }
                    procedures.append(procedure)
            
            i += 1
        
        return procedures

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
                self.models.append(model_data)
                print(f"Successfully processed {file_path}")
                
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
        
        return self.models

    def save_to_json(self, output_file: str):
        """Save the processed models to a JSON file."""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "models": self.models,
                "totalModels": len(self.models),
                "generatedAt": datetime.now().isoformat()
            }, f, indent=2) 
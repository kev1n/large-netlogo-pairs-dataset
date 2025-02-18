#!/usr/bin/env python3

import json
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class NetLogoModelParser(ABC):
    """Abstract base class for NetLogo model parsers."""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.models = []
        self.formats_since_reload = 0
        self._setup_webdriver()
    # TODO: Not use a browser for this at all, but may be too much effort
    def _setup_webdriver(self):
        """Setup the Selenium webdriver for code formatting."""
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')  # Run in headless mode
        self.driver = webdriver.Chrome(options=options)
        # Load the formatter page once
        self.driver.get('https://netlogo-mobile.github.io/CodeMirror-NetLogo/')
        # Wait for the editor to be ready
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "Container"))
        )
        # Wait a bit for the editor to fully initialize
        time.sleep(2)

    def __del__(self):
        """Cleanup webdriver when parser is destroyed."""
        if hasattr(self, 'driver'):
            self.driver.quit()

    def _reload_page(self):
        """Reinitialize the editor instance."""
        print("  Reinitializing editor...")
        # Clear and reinitialize the editor
        self.driver.refresh()
        
        # Wait for editor to be ready
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "Container"))
        )
        time.sleep(1)  # Give it a moment to fully initialize

    def format_netlogo_code(self, content: str) -> str:
        """Format NetLogo code using the CodeMirror-NetLogo web formatter."""
        # Check if we need to reload the page
        if self.formats_since_reload >= 1:
            print("\nPerforming periodic page reload...")
            self._reload_page()
            self.formats_since_reload = 0

        max_retries = 3
        for attempt in range(max_retries):
            try:
                print("  Formatting code...")
                # Set the code using the editor's API
                self.driver.execute_script("Editor.SetCode(arguments[0]);", content)

                time.sleep(0.5)
                
                # Force parsing and linting
                print("  Running parser and linter...")
                self.driver.execute_script("Editor.Semantics.PrettifyAll();")
                
                # Give it a moment to format
                time.sleep(0.5)
                
                # Get the formatted code using the editor's API
                print("  Getting formatted code...")
                formatted_code = self.driver.execute_script("return Editor.GetCode();")
                
                print("  Formatting complete")
                self.formats_since_reload += 1
                return formatted_code
            except Exception as e:
                print(f"Warning: Code formatting failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    print("  Attempting recovery...")
                    self._reload_page()
                    self.formats_since_reload = 0
                else:
                    return content  # Return original content if all retries fail

    @abstractmethod
    def extract_documentation(self, content: str) -> str:
        """Extract documentation from model content."""
        pass

    def extract_procedures(self, content: str) -> List[Dict]:
        """Extract procedures from NetLogo file content."""
        # Format the code first
        formatted_content = self.format_netlogo_code(content)
        
        procedures = []
        # Split content into lines for easier processing
        lines = formatted_content.split('\n')
        
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
        
        files_since_reload = 0
        max_files_before_reload = 5  # Reload page every 5 files to prevent memory issues
        
        for i, file_path in enumerate(netlogo_files, 1):
            try:
                print(f"\nProcessing file {i}/{total_files}: {file_path}")
                model_data = self.process_file(file_path)
                self.models.append(model_data)
                print(f"Successfully processed {file_path}")
                
                # Periodically reload the page to prevent memory buildup
                files_since_reload += 1
                if files_since_reload >= max_files_before_reload:
                    print("\nPerforming periodic page reload...")
                    self._reload_page()
                    files_since_reload = 0
                
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
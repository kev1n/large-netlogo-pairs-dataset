#!/usr/bin/env python3

import re
from typing import Dict, List
from textwrap import dedent
import litellm
from .env import MISTRAL_API_KEY

class LLMPseudocodeGenerator:
    """Class for generating pseudocode from NetLogo code using LLM.
    
    This class encapsulates all the functionality related to generating pseudocode
    from NetLogo code using a large language model. It handles formatting code with
    line numbers, generating prompts for the LLM, and creating mappings between
    original code and generated pseudocode.
    """
    
    def __init__(self, model_name: str = "mistral/codestral-2501"):
        """Initialize the pseudocode generator with the specified LLM model.
        
        Args:
            model_name: The name of the LLM model to use for pseudocode generation.
                       Defaults to "mistral/codestral-2501".
        """
        self.model_name = model_name
        # Set up LiteLLM with Mistral API key
        litellm.api_key = MISTRAL_API_KEY

    def format_code_with_line_numbers(self, code: str) -> List[str]:
        """Format NetLogo code with line numbers while preserving indentation.
        
        Args:
            code: The NetLogo code to format.
            
        Returns:
            A list of formatted lines with line numbers.
        """
        lines = code.split('\n')
        formatted_lines = []
        
        # Calculate the width needed for line numbers (depends on number of lines)
        line_number_width = len(str(len(lines)))
        
        for i, line in enumerate(lines, 1):
            if line.strip():  # Skip empty lines
                # Format: {line_number} | {code with preserved indentation}
                formatted_lines.append(f"{i:>{line_number_width}} | {line}")
            else:
                formatted_lines.append(f"{i:>{line_number_width}} |")
        
        return formatted_lines
    
    def _generate_pseudocode_prompt(self, code_with_line_numbers: List[str]) -> str:
        """Generate a prompt for LLM to create pseudocode.
        
        Args:
            code_with_line_numbers: A list of code lines with line numbers.
            
        Returns:
            A prompt string for the LLM.
        """
        # Join the list of numbered code lines for the prompt
        joined_code = '\n'.join(code_with_line_numbers)
        
        prompt = dedent(f"""
        You are a NetLogo expert. Your task is to translate NetLogo code into clear, concise pseudocode.
        
        For each numbered line of NetLogo code below, provide a corresponding line of pseudocode that explains what that line does.
        Use the same line numbers in your response to maintain the alignment between code and pseudocode. It must be a 1:1 mapping.
        
        For example:
        
        NetLogo code:
        1 | to setup
        2 |   clear-all
        3 |   setup-turtles
        4 |   reset-ticks
        5 | end
        
        Your pseudocode response should be:
        1 | ENGLISH PSEUDOCODE HERE
        2 |   ENGLISH PSEUDOCODE HERE
        3 |   ENGLISH PSEUDOCODE HERE
        4 |   ENGLISH PSEUDOCODE HERE
        5 | ENGLISH PSEUDOCODE HERE
                        
        Speak plainly in English. Reference variable names sparingly, only when necessary.
                        
        When a line of netlogo code spans multiple lines, your psuedocode MUST match those multiple lines.
        For example, if a line of netlogo code is:
        10 |   set colors      [ white blue
        11 |                     cyan orange]",

        Your psuedocode should be:
        10 |   set the colors to white and blue...
        11 |                     ...and cyan and orange

        Conversely, do not split a single line of netlogo code into multiple lines of psuedocode.
                        
        If there are 35 lines of netlogo code, there should be 35 lines of psuedocode.
                        
        Here is the NetLogo code to translate:
        <netlogo-code>
{joined_code}
        </netlogo-code>
        
        Please provide pseudocode for each numbered line, maintaining the line numbers and indentation structure.
        """)
        return prompt
    
    def create_code_to_pseudocode_mapping(self, 
                                          numbered_original_code: List[str], 
                                          pseudocode_lines: List[str]) -> List[Dict]:
        """Create a 1:1 mapping between original code lines and pseudocode lines.
        
        Args:
            numbered_original_code: A list of code lines with line numbers.
            pseudocode_lines: A list of pseudocode lines with matching line numbers.
            
        Returns:
            A list of dictionaries mapping line numbers, original code, and pseudocode.
        """
        mapping = []
        
        # Extract the original code lines with their numbers (already in a list format)
        original_lines = [line.strip() for line in numbered_original_code if re.match(r'^\s*\d+\s*\|', line)]
        
        # Create the mapping
        for orig_line in original_lines:
            # Extract the line number from the original code
            line_num_match = re.match(r'^\s*(\d+)\s*\|', orig_line)
            if line_num_match:
                line_num = line_num_match.group(1)
                
                # Find the corresponding pseudocode line with the same number
                pseudo_line = ""
                for p_line in pseudocode_lines:
                    if p_line.startswith(f"{line_num} |"):
                        pseudo_line = p_line
                        break
                
                # Remove the line numbers and pipe formatting from both code and pseudocode
                orig_code_without_num = re.sub(r'^\s*\d+\s*\|\s*', '', orig_line)
                pseudo_without_num = re.sub(r'^\s*\d+\s*\|\s*', '', pseudo_line)
                
                mapping.append({
                    "lineNumber": int(line_num),
                    "originalCode": orig_code_without_num,
                    "pseudoCode": pseudo_without_num
                })
        
        return mapping

    def generate_pseudocode(self, procedure: Dict) -> Dict:
        """Generate pseudocode for a NetLogo procedure using LLM.
        
        Args:
            procedure: A dictionary containing procedure information, including 'name' and
                      'originalCode' or 'numberedOriginalCode'.
        
        Returns:
            Updated procedure dict with 'pseudoCode' and 'codeToPseudoCodeMap' fields.
        """
        try:
            # Use the already stored numbered original code or generate it if needed
            if "numberedOriginalCode" not in procedure or not procedure["numberedOriginalCode"]:
                procedure["numberedOriginalCode"] = self.format_code_with_line_numbers(procedure["originalCode"])
            
            code_with_line_numbers = procedure["numberedOriginalCode"]
            
            # Generate the prompt
            prompt = self._generate_pseudocode_prompt(code_with_line_numbers)

            print(prompt)
            
            print(f"  Generating pseudocode for procedure '{procedure['name']}'...")
            
            # Call LiteLLM with the configured model
            response = litellm.completion(
                model=self.model_name,
                messages=[{
                    "role": "system",
                    "content": "You are a NetLogo expert who translates NetLogo code into clear pseudocode."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=4096,
                temperature=0.0
            )
            
            # Extract pseudocode from response
            pseudocode_text = response.choices[0].message.content.strip()
            
            # Process pseudocode text to extract just the numbered lines
            numbered_pseudocode_lines = []
            for line in pseudocode_text.split('\n'):
                # Use regex to match lines that start with a number followed by |
                if re.match(r'^\s*\d+\s*\|', line):
                    numbered_pseudocode_lines.append(line.strip())
            
            # Store the pseudocode WITH line numbers
            procedure["pseudoCode"] = numbered_pseudocode_lines
            
            # Create and store the 1:1 mapping
            procedure["codeToPseudoCodeMap"] = self.create_code_to_pseudocode_mapping(
                procedure["numberedOriginalCode"], 
                numbered_pseudocode_lines
            )
            
            print(f"  Pseudocode generated successfully for '{procedure['name']}'")
            
            return procedure
        except Exception as e:
            print(f"  Error generating pseudocode: {str(e)}")
            procedure["pseudoCode"] = []
            procedure["codeToPseudoCodeMap"] = []
            return procedure 
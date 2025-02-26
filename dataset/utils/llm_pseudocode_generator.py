#!/usr/bin/env python3

import re
import json
from typing import Dict, List
from textwrap import dedent
import litellm
from pydantic import BaseModel, Field, RootModel
from .env import MISTRAL_API_KEY

class PseudocodeLine(BaseModel):
    """Pydantic model for a single line of pseudocode mapping."""
    line: int = Field(description="The line number from the original code")
    orig: str = Field(description="A repeat of the original NetLogo code at this line to observe the spacing and indentation")
    psuedo: str = Field(description="English pseudocode translation of the NetLogo code at this line")

class PseudocodeResponse(BaseModel):
    """Pydantic model that combines pseudocode lines with a summary."""
    variables: List[str] = Field(
        description="List of important non-primitive variable names used in this procedure",
    )
    lines: List[PseudocodeLine] = Field(description="Array of line-by-line pseudocode mappings")
    summary: str = Field(description="EXAMPLE SUMMARY: First, setup the globals and patches. Then, clear the output and all plots.")
    

class PseudocodeMapping(RootModel):
    """Pydantic model for the entire pseudocode response."""
    root: PseudocodeResponse

class LLMPseudocodeGenerator:
    """Class for generating pseudocode from NetLogo code using LLM.
    
    This class encapsulates all the functionality related to generating pseudocode
    from NetLogo code using a large language model. It handles formatting code with
    line numbers, generating prompts for the LLM, and creating mappings between
    original code and generated pseudocode.
    """
    
    # Class variable to track total tokens used
    total_tokens_used = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    processed_procedures_count = 0
    
    @classmethod
    def reset_token_counter(cls):
        """Reset all token counters to zero."""
        cls.total_tokens_used = 0
        cls.total_prompt_tokens = 0
        cls.total_completion_tokens = 0
        cls.processed_procedures_count = 0
        print("Token counters have been reset to zero.")
    
    @classmethod
    def print_token_usage_summary(cls):
        """Print a summary of token usage."""
        if cls.processed_procedures_count == 0:
            print("No procedures have been processed yet.")
            return
            
        avg_tokens = cls.total_tokens_used / cls.processed_procedures_count
        print("\n===== TOKEN USAGE SUMMARY =====")
        print(f"Total procedures processed: {cls.processed_procedures_count}")
        print(f"Total prompt tokens: {cls.total_prompt_tokens}")
        print(f"Total completion tokens: {cls.total_completion_tokens}")
        print(f"Total tokens used: {cls.total_tokens_used}")
        print(f"Average tokens per procedure: {avg_tokens:.2f}")
        print("===============================\n")
    
    def __init__(self, model_name: str = "mistral/codestral-2501"):
        """Initialize the pseudocode generator with the specified LLM model.
        
        Args:
            model_name: The name of the LLM model to use for pseudocode generation.
                       Defaults to "mistral/codestral-2501".
        """
        self.model_name = model_name
        # Set up LiteLLM with Mistral API key
        litellm.api_key = MISTRAL_API_KEY
        # Enable JSON schema validation
        litellm.enable_json_schema_validation = True
        #litellm.set_verbose = True

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
    
    def _prepare_structured_input(self, code_with_line_numbers: List[str]) -> List[Dict[str, any]]:
        """Prepare structured input for the LLM from code with line numbers.
        
        Args:
            code_with_line_numbers: A list of code lines with line numbers.
            
        Returns:
            A list of dictionaries with line numbers and code.
        """
        structured_input = []
        
        for line in code_with_line_numbers:
            line_match = re.match(r'^\s*(\d+)\s*\|\s*(.*)', line)
            if line_match:
                line_num = int(line_match.group(1))
                code = line_match.group(2)
                structured_input.append({
                    "lineNumber": line_num,
                    "code": code
                })
        
        return structured_input
    
    def _generate_structured_prompt(self, code_with_line_numbers: List[str]) -> str:
        """Generate a prompt for LLM to create pseudocode with structured output.
        
        Args:
            code_with_line_numbers: A list of code lines with line numbers.
            
        Returns:
            A prompt string for the LLM.
        """
        # Join the list of numbered code lines for the prompt
        joined_code = '\n'.join(code_with_line_numbers)
        #print(f"Joined code: {joined_code}")
        
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
                        
        Pseudocode:
        1 | ENGLISH PSEUDOCODE
        2 |   ENGLISH PSEUDOCODE
        3 |   ENGLISH PSEUDOCODE
        4 |   ENGLISH PSEUDOCODE
        5 | ENGLISH PSEUDOCODE
                        
        Observe how the pseudocode is formatted and preserve spacing and indentation from the original code. You MUST do this.
                        
        Here is the NetLogo code to translate:
        <netlogo-code>
{joined_code}
        </netlogo-code>
        
        In your response, please provide:
        1. A JSON object with the following fields:
           - lines: An array where each object contains line, orig, and psuedo fields for each line
           - summary: A concise, step by step, detailed summary of the intent of the code. Maximum 1 paragraph
           - variables: An array of strings, each representing a non-primitive variable or custom defined function name used in this procedure

        <summary-example>
        <input>
        to setup
          setup-globals
          setup-patches
          clear-output
          clear-all-plots
        end
        </input>
        <output>
        First, setup the globals and patches. Then, clear the output and all plots.
        </output>
        </summary-example>

        <variables-example>
        <input>
        to go
          ask turtles [
            set energy energy - 1
            if energy > reproduce-threshold [
              reproduce
            ]
            if energy <= 0 [ die ]
          ]
          tick
        end
        </input>
        <output>
        ["energy", "reproduce-threshold"]
        </output>
        </variables-example>

        For the variables list, only include the names of custom variables (globals, turtle/patch/link variables, breed-specific variables, functions) that are used in the code. 
        DO NOT include standard NetLogo primitives or commands. Return just a simple array of strings.

        DO NOT MENTION THE PROCEDURE ITSELF OR ANY SPECIFIC VARIABLES IN THE SUMMARY. THE SUMMARY IS HIGH LEVEL.
        
        WE CARE MORE ABOUT MOTIVATION THAN THE IMPLEMENTATION DETAILS.
        """)
        return prompt
    
    def generate_pseudocode(self, procedure: Dict) -> Dict:
        """Generate pseudocode for a NetLogo procedure using LLM with structured output.
        
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
            
            # Generate the prompt for structured output
            prompt = self._generate_structured_prompt(code_with_line_numbers)
            
            print(f"  Generating pseudocode for procedure '{procedure['name']}'...")
            
            # Call LiteLLM with the configured model and Pydantic model for response format
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
                temperature=0.0,
                response_format=PseudocodeMapping
            )
            
            # Track and print token usage
            if hasattr(response, 'usage') and response.usage:
                prompt_tokens = response.usage.prompt_tokens or 0
                completion_tokens = response.usage.completion_tokens or 0
                total_tokens = response.usage.total_tokens or 0
                
                # Update the class-level counters
                LLMPseudocodeGenerator.total_prompt_tokens += prompt_tokens
                LLMPseudocodeGenerator.total_completion_tokens += completion_tokens
                LLMPseudocodeGenerator.total_tokens_used += total_tokens
                LLMPseudocodeGenerator.processed_procedures_count += 1
                
                print(f"  Token usage for '{procedure['name']}': {prompt_tokens} prompt + {completion_tokens} completion = {total_tokens} total")
                print(f"  Running total tokens used: {LLMPseudocodeGenerator.total_tokens_used}")
            
            # Extract pseudocode, summary and variables from response
            pseudocode_mapping = None
            procedure_summary = ""
            procedure_variables = []
            
            if hasattr(response.choices[0].message, 'parsed'):
                # Using the parsed response directly if available
                parsed_response = response.choices[0].message.parsed
                # Access the root attribute if it's a PseudocodeMapping
                if isinstance(parsed_response, PseudocodeMapping):
                    response_data = parsed_response.root
                    pseudocode_mapping = response_data.lines
                    procedure_summary = response_data.summary
                    procedure_variables = response_data.variables
                else:
                    # Handle other possible parsed response formats
                    if hasattr(parsed_response, 'lines'):
                        pseudocode_mapping = parsed_response.lines
                        procedure_summary = getattr(parsed_response, 'summary', "")
                        procedure_variables = getattr(parsed_response, 'variables', [])
                    else:
                        # Fallback if the structure is different
                        pseudocode_mapping = parsed_response
            else:
                # Fallback to parsing the content manually
                response_content = response.choices[0].message.content.strip()
                try:
                    parsed_json = json.loads(response_content)
                    if isinstance(parsed_json, dict):
                        if 'lines' in parsed_json:
                            pseudocode_mapping = parsed_json['lines']
                        procedure_summary = parsed_json.get('summary', "")
                        procedure_variables = parsed_json.get('variables', [])
                    else:
                        # If it's a direct array without the expected structure
                        pseudocode_mapping = parsed_json
                except:
                    # If JSON parsing fails, use an empty list
                    pseudocode_mapping = []
            
            # Create a mapping between code and pseudocode from the structured response
            code_to_pseudo_map = []
            
            # Also keep track of the numbered pseudocode lines for the old format
            numbered_pseudocode_lines = []
            
            # Get line number width for formatting
            line_number_width = len(str(len(code_with_line_numbers)))
            
            # Process each line from the structured response
            if pseudocode_mapping:
                for line_data in pseudocode_mapping:
                    # Extract data based on whether we have a Pydantic model or dict
                    if isinstance(line_data, PseudocodeLine):
                        line_num = line_data.line
                        pseudo_text = line_data.psuedo
                    else:
                        # Treat as dictionary
                        line_num = line_data["line"]
                        pseudo_text = line_data["psuedo"]
                    
                    # Find the original code line
                    original_line = ""
                    for line in code_with_line_numbers:
                        if line.startswith(f"{line_num:>{line_number_width}} |"):
                            original_line = line
                            break
                    
                    if original_line:
                        # Extract original code without line number but preserving indentation
                        orig_code_without_num = re.sub(r'^\s*\d+\s*\|\s?', '', original_line)
                        
                        # Format the pseudocode with the same line number format
                        formatted_pseudo = f"{line_num:>{line_number_width}} | {pseudo_text}"
                        numbered_pseudocode_lines.append(formatted_pseudo)
                        
                        # Add to the mapping
                        code_to_pseudo_map.append({
                            "lineNumber": line_num,
                            "originalCode": orig_code_without_num,
                            "pseudoCode": pseudo_text
                        })
            
            # Sort mappings and pseudocode lines by line number
            code_to_pseudo_map.sort(key=lambda x: x["lineNumber"])
            numbered_pseudocode_lines.sort(key=lambda x: int(re.match(r'^\s*(\d+)\s*\|', x).group(1)))
            
            # Store the results
            procedure["pseudoCode"] = numbered_pseudocode_lines
            procedure["codeToPseudoCodeMap"] = code_to_pseudo_map
            procedure["summary"] = procedure_summary
            procedure["variables"] = procedure_variables
            
            print(f"  Pseudocode generated successfully for '{procedure['name']}'")
            print(f"  Summary: {procedure_summary[:100]}..." if len(procedure_summary) > 100 else f"  Summary: {procedure_summary}")
            
            # Print the number of variables identified
            var_count = len(procedure_variables)
            if var_count > 0:
                print(f"  Identified {var_count} important variables: {', '.join(procedure_variables[:5])}")
                if var_count > 5:
                    print(f"    - ... and {var_count - 5} more")
            else:
                print("  No custom variables identified")
                
            print("----------------------------------------------------------\n")
            
            return procedure
        except Exception as e:
            print(f"  Error generating pseudocode: {str(e)}")
            procedure["pseudoCode"] = []
            procedure["codeToPseudoCodeMap"] = []
            procedure["summary"] = ""
            procedure["variables"] = []
            return procedure 
#!/usr/bin/env python3

import re
from pathlib import Path
from typing import Dict, List

from .base_parser import NetLogoModelParser

class ModelsLibraryParser(NetLogoModelParser):
    """Parser for the official NetLogo Models Library."""

    def extract_documentation(self, content: str) -> str:
        """Extract documentation from NetLogo file content."""
        doc_match = re.search(r'@#\s*(.*?)\s*#@', content, re.DOTALL)
        if doc_match:
            return doc_match.group(1).strip()
        return ""

    def construct_source_link(self, relative_path: Path) -> str:
        """Construct CCL source link for Models Library."""
        web_path = str(relative_path).replace('\\', '/').replace(' ', '%20')
        return f"https://ccl.northwestern.edu/netlogo/models/models/{web_path}"

    def get_source_type(self) -> str:
        return "Models Library"

    def get_license(self) -> str:
        return "CC BY-NC-SA 3.0" 
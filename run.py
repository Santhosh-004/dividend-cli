#!/usr/bin/env python3
"""Entry point for PyInstaller."""

import sys
import os

# Add the parent directory to path so we can import the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dividend_calculator import cli

if __name__ == "__main__":
    cli.main()

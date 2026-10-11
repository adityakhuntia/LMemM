#!/usr/bin/env python3
"""Absolute-path entrypoint for MCP hosts launched outside the repository."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from semantic_memory.mcp_server import main
if __name__=='__main__':main()

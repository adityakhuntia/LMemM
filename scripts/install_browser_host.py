#!/usr/bin/env python3
"""Explicit CLI alternative to Memory Settings → Connect Chrome."""
import argparse
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'src')]
import config
from semantic_memory.browser_install import install_browser_host
from semantic_memory.ipc import request
from semantic_memory.live_bridge import read_private_json

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser',default='Chrome',choices=['Chrome','Chromium','ChromeForTesting'])
    args=parser.parse_args();directory=Path(config.paths().semantic_dir)
    capability=read_private_json(directory/'capabilities.json')['owner']
    result=install_browser_host(Path.home(),directory,browser=args.browser)
    request(directory/'service.json',capability,'pair_browser',{'extension_id':result['extension_id']})
    print('Browser paired. Load extensions/lmemm-browser as an unpacked extension, pin it, then choose a project on first save.')

"""Development native-host entry; standalone entry uses the app's worker mode."""
import argparse
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'src')]
from semantic_memory.browser_host import main

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('origin')
    args=parser.parse_args();main(args.config,args.origin)

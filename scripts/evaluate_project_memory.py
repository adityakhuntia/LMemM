#!/usr/bin/env python3
"""Run synthetic local-model evaluation; does not capture desktop content."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from semantic_memory.evaluation import load_fixture_manifest,evaluate
from semantic_memory.local_runtime import RuntimeConfig,LocalRuntime
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--runtime-config',type=Path,required=True)
    p.add_argument('--split',choices=['development','heldout'],required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--timing-repeats',type=int,default=1)
    args=p.parse_args()
    raw=json.loads(args.runtime_config.read_text())
    if set(raw)-{'executable','model_path','context_limit'}:raise ValueError('Unsupported runtime configuration')
    runtime=LocalRuntime(RuntimeConfig(Path(raw['executable']),Path(raw['model_path']),context_limit=raw.get('context_limit',8192)))
    try:
        if not 1<=args.timing_repeats<=4:raise ValueError('Invalid repetition bound')
        report=evaluate(load_fixture_manifest(args.manifest),runtime,args.split,args.output/(runtime.model.replace(':','-')+'-'+args.split+'.json'),args.timing_repeats)
        print(json.dumps({k:report[k] for k in ('model','split','metrics','quality_pass','resource_pass','selection_pass')},indent=2))
    finally:runtime.unload()
if __name__=='__main__':main()

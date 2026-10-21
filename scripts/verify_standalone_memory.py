#!/usr/bin/env python3
"""Qualify a copied standalone app using isolated, synthetic evidence only."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'src')]
from semantic_memory.ipc import request
from semantic_memory.live_bridge import read_private_json


async def check_mcp(binary,connection,pid,env):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    params=StdioServerParameters(command=str(binary),args=['--lmemm-worker','mcp','--config',connection['config_path']],env=env,cwd='/private/tmp')
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            tools=await session.list_tools()
            assert len(tools.tools)==3
            result=await session.call_tool('get_project_context',{'project_id':pid,'start':'1970-01-01T00:00:00+00:00'})
            assert not result.is_error
            assert 'SQLite' in str(result)
    return {'tools':3,'supported_context':True}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--app',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--model-cache',type=Path)
    args=parser.parse_args();report={'synthetic_only':True}
    with tempfile.TemporaryDirectory(prefix='LMemM Installed Test ') as tmp:
        base=Path(tmp);installed=base/'LMemM.app';shutil.copytree(args.app,installed,symlinks=True)
        binary=installed/'Contents/MacOS/LMemM'
        env={k:v for k,v in os.environ.items() if k not in {'PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','EXECUTABLEPATH','RESOURCEPATH'}}
        env['PATH']='/usr/bin:/bin:/usr/sbin:/sbin'
        diagnostics=subprocess.run([str(binary),'--lmemm-worker','diagnostics'],env=env,cwd=base,capture_output=True,text=True,timeout=30)
        assert diagnostics.returncode==0,diagnostics.stderr
        info=json.loads(diagnostics.stdout.strip());assert Path(info['resources']).resolve().is_relative_to(base.resolve())
        report['copied_app_diagnostics']=info
        directory=base/'data/semantic';r,w=os.pipe()
        log=base/'service.log'
        with log.open('w') as stream:
            child=subprocess.Popen([str(binary),'--lmemm-worker','memory-service','--data-dir',str(directory),'--control-fd',str(r),'--headless'],env=env,cwd=base,pass_fds=(r,),stdout=stream,stderr=stream)
        os.close(r)
        try:
            deadline=time.monotonic()+45
            while not (directory/'service.json').exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.05)
            assert (directory/'service.json').exists(),log.read_text()[-4000:]
            owner=read_private_json(directory/'capabilities.json')['owner']
            def call(method,params):return request(directory/'service.json',owner,method,params)
            pid=call('enroll',{'ui_project_id':'synthetic'})['project_id']
            saved=call('save_excerpt',{'project_id':pid,'payload':dict(request_id='standalone-excerpt',kind='pasted_excerpt',title='Standalone fixture',text='SQLite keeps this project local.',url='https://example.org/research')})
            packet=call('resume_project',{'project_id':pid});assert packet['saved_activity']
            citation=next(iter(packet['citations']));detail=call('resolve_citation',{'project_id':pid,'citation_id':citation})
            assert detail['text']=='SQLite keeps this project local.'
            report['service_and_citations']=True
            call('pair_browser',{'extension_id':'a'*32})
            message=dict(version=1,request_id='standalone-browser',method='save',params=dict(project_id=pid,payload=dict(request_id='standalone-browser-source',kind='browser_selection',title='Browser fixture',url='https://example.org',text='Browser context survives a packaged worker.')))
            from semantic_memory.browser_host import write_message,read_message
            import io
            encoded=io.BytesIO();write_message(encoded,message)
            host=subprocess.run([str(binary),'--lmemm-worker','browser-host','--config',str(directory/'browser-host.json'),'chrome-extension://'+'a'*32+'/'],input=encoded.getvalue(),capture_output=True,env=env,cwd=base,timeout=30)
            assert host.returncode==0,host.stderr.decode(errors='replace')
            response=read_message(io.BytesIO(host.stdout));assert response['ok'],response
            report['bundled_browser_host']=True
            if args.model_cache:
                weights=base/'data/embedding-models';shutil.copytree(args.model_cache,weights)
                from semantic_memory.model_setup import OwnedEmbeddingRuntime
                import dataclasses
                manifest=OwnedEmbeddingRuntime(weights).manifest()
                call('configure_model',{'manifest':dataclasses.asdict(manifest)})
                deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    state=call('status',{})
                    if not state['pending'] and state['indexed_at']:break
                    time.sleep(.2)
                result=call('search_project_memory',{'project_id':pid,'query':'database privacy','start':'1970-01-01T00:00:00+00:00'})
                assert result['mode']=='hybrid',result
                report['bundled_semantic_runtime']=True
            from semantic_memory.intentional_sources import NATIVE_APP,BROWSER_APP,BROWSER_SCOPE
            connection=call('connect_agent',dict(client_id='synthetic-mcp',project_ids=[pid],app_ids=[NATIVE_APP,BROWSER_APP],origins=[BROWSER_SCOPE],disclosure_approved=True))
            report['bundled_mcp']=asyncio.run(check_mcp(binary,connection,pid,env))
            report['permission_probe']=subprocess.run([str(binary),'--lmemm-worker','permission-probe'],env=env,cwd=base,capture_output=True,text=True,timeout=10).returncode==0
        finally:
            os.close(w)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5)
        report['owned_service_shutdown']=child.returncode==0
    report['passed']=all(report.get(k) for k in ['service_and_citations','bundled_browser_host','bundled_mcp','permission_probe','owned_service_shutdown'])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()

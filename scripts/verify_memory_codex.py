#!/usr/bin/env python3
"""Explicit hosted-agent resume test using only newly created synthetic evidence."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'src')]
from semantic_memory.service import MemoryService
from semantic_memory.ipc import PrivateServer
from semantic_memory.contracts import SourceEnvelope,TextSpan
from semantic_memory.chunks import index_source
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--allow-agent-disclosure',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if not a.allow_agent_disclosure:p.error('Explicit approval to send synthetic snippets to Codex is required')
with tempfile.TemporaryDirectory(prefix='lmemm-codex-synthetic-') as tmp:
    root=Path(tmp)/'synthetic-project';root.mkdir();root=root.resolve()
    service=MemoryService(Path(tmp)/'memory',focus_provider=lambda:None,clock=lambda:1790812800)
    server=None
    try:
        b=service.enroll('synthetic',str(root));pid=b['project_id']
        texts=['We decided to use SQLite because all project data must stay on this Mac.','TODO: Verify rollback before the beta.']
        for i,text in enumerate(texts):
            sid='codex-synthetic-'+str(i)
            service.store.ingest(SourceEnvelope(sid,'2026-10-10T10:00:00Z','codex-synthetic','com.microsoft.VSCode',str(root/('note'+str(i)+'.md')),str(root),True,'user_note',(TextSpan('note',text),),service.policy.revision),service.policy)
            index_source(service.store,sid)
        packet=service.serve_request(service.owner_capability,'get_project_context',{'project_id':pid,'start':'2026-10-01T00:00:00Z','end':'2026-11-01T00:00:00Z'})
        assert packet['decisions'] and packet['open_tasks'],'Synthetic enrollment/authority mismatch'
        grant=service.connect_agent('Codex',[pid],['com.microsoft.VSCode'],True);server=PrivateServer(service)
        adapter=str(Path(__file__).resolve().parent/'project_memory_mcp.py')
        from memory_controller import codex_exec_args,codex_question,codex_server_name
        prompt=codex_question(pid,'Explain the recorded decision and next task in two sentences; cite their exact citation IDs and distinguish evidence from assumptions.',
            server_name=codex_server_name(grant['config_path']),bounds={'start':'2026-10-01T00:00:00Z','end':'2026-11-01T00:00:00Z'})
        prompt+=' Synthetic acceptance test: do not use filesystem, shell, or other connectors.'
        cmd=codex_exec_args('codex',grant['config_path'],prompt,root)
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        events=[]
        for line in result.stdout.splitlines():
            try:events.append(json.loads(line))
            except ValueError:pass
        responses=[e['item']['text'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
        tools=[e.get('item',{}) for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='mcp_tool_call']
        citations=[r[0] for r in service.store.connection.execute('SELECT id FROM occurrences')]
        response=responses[-1] if responses else ''
        report={'synthetic_only':True,'returncode':result.returncode,'mcp_calls':len(tools),'response':response,
                'all_expected_citations_present':all(cid in response for cid in citations),'passed':result.returncode==0 and bool(tools) and all(cid in response for cid in citations)}
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
        if not report['passed']:raise SystemExit(1)
    finally:
        if server:server.close()
        service.close()

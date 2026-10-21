"""Entry point of LMemM.app: the same as `python3 lmemm.py start`, with no terminal menu."""
import locale
import os
import sys

# An app starts with the "C" locale, so open() would read memory.json as ASCII (and the launcher
# ignores PYTHONUTF8). Switching the character locale makes the default encoding UTF-8 again.
for _loc in ("en_US.UTF-8", "UTF-8", "C.UTF-8"):
    try:
        locale.setlocale(locale.LC_CTYPE, _loc)
        break
    except locale.Error:
        continue

HERE = os.path.dirname(os.path.abspath(__file__))
RESOURCES=os.environ.get('RESOURCEPATH',HERE)
# alias build: the app points back at this repo (…/LMemM/packaging); a standalone build keeps lmemm.py beside it
for root in (RESOURCES,os.path.dirname(HERE), HERE):
    if os.path.exists(os.path.join(root, "lmemm.py")):
        sys.path.insert(0, root)
        os.chdir(root)
        break
sys.path.insert(0,os.path.join(os.getcwd(),'src'))

# py2app's bootstrap puts the base interpreter's site-packages first; an older PyObjC there
# (e.g. Anaconda's) shadows the one in .venv and fails with "no attribute registerNewKeywordsFromSelector"
import glob  # noqa: E402

for site in glob.glob(os.path.join(os.getcwd(), ".venv", "lib", "python*", "site-packages")):
    sys.path.insert(0, site)

if __name__ == "__main__":
    if len(sys.argv)>2 and sys.argv[1]=='--lmemm-worker':
        import runpy
        mode=sys.argv[2];sys.argv=sys.argv[2:]
        scripts={'memory-service':'scripts/project_memory_service.py','embedding-service':'scripts/local_embedding_server.py',
                 'mcp':'scripts/project_memory_mcp.py','permission-probe':'scripts/probe_permissions.py','browser-host':'packaging/browser_host_main.py'}
        if mode in scripts:runpy.run_path(os.path.join(os.getcwd(),scripts[mode]),run_name='__main__')
        elif mode=='diagnostics':
            import json,config,numpy,PIL,mcp,AppKit,Quartz,ApplicationServices
            print(json.dumps({'standalone':True,'data_dir':config.paths().data_dir,'resources':os.getcwd(),'workers':list(scripts)}))
        elif mode=='import-data':
            from semantic_memory.data_import import import_legacy_data
            import json
            print(json.dumps(import_legacy_data(sys.argv[1],sys.argv[2])))
        else:raise SystemExit('Unknown LMemM worker')
        raise SystemExit(0)
    import lmemm  # noqa: E402
    if len(sys.argv) == 1:
        sys.argv.append("start")
    lmemm.main()

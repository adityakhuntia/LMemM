"""Explicit local model installation and an owned cloud-disabled runtime."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from semantic_memory.runtime_environment import python_executable
import threading
import time
import urllib.request
import zipfile
from .api_contracts import ModelManifest
from .embedding_runtime import validate_manifest

SELECTED_DIGEST='1b226e2802dbb772b5fc32a58f103ca1804ef7501331012de126ab22f67475ef'
MODEL='all-minilm:22m'
DOWNLOAD_BYTES=45_960_589   # layers of the selected model, from the development selection record

class OwnedEmbeddingRuntime:
    def __init__(self,weights):
        self.weights=Path(weights).resolve();self.process=None;self.control=None;self.lock=threading.RLock();self.stopped=False;self.progress=None
    def manifest(self):
        # The digest pin is the same for both layouts: newer Ollama writes the identical manifest under manifests-v2.
        newer=self.weights/'manifests-v2/ollama.com/library/all-minilm/22m'
        older=self.weights/'manifests/registry.ollama.ai/library/all-minilm/22m'
        return ModelManifest(MODEL,SELECTED_DIGEST,384,512,1,'ollama-local',str(newer if newer.is_file() else older))
    def ensure(self):
        with self.lock:
            if self.stopped:raise ValueError('Runtime stopped')
            if self.process and self.process.poll() is None:return
            self._stop_owned_process()
            executable=shutil.which('ollama')
            if not executable:raise ValueError('Install the local Ollama runtime, then retry model setup')
            self._reap_orphan()
            # Never attach source-bearing requests to an unowned server.
            with socket.socket() as probe:
                try:probe.bind(('127.0.0.1',11455))
                except OSError:raise ValueError('Local model port 11455 is occupied. Close other LMemM sessions and retry; if it persists, restart your Mac. Existing processes were left running.')
            self.weights.mkdir(parents=True,mode=0o700,exist_ok=True)
            r,w=os.pipe();self.control=w
            script=Path(__file__).resolve().parents[1]/'scripts/local_embedding_server.py'
            try:self.process=subprocess.Popen([python_executable(),str(script),'--control-fd',str(r),'--models',str(self.weights),'--ollama',executable],pass_fds=(r,),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            except BaseException:
                os.close(w);self.control=None;raise
            finally:os.close(r)
            try:
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(200):
                    if self.process.poll() is not None:raise ValueError('Local model runtime unavailable')
                    try:
                        with opener.open('http://127.0.0.1:11455/api/version',timeout=.2) as response:
                            if response.status==200:return
                    except OSError:time.sleep(.05)
                raise ValueError('Local model startup timed out')
            except BaseException:
                self._stop_owned_process();raise
    def _reap_orphan(self):
        # A saved PID cannot prove ownership after a crash/PID reuse. Never
        # signal an existing process; the control-pipe supervisor reaps our child.
        # The port probe below reports a recoverable conflict if one remains.
        return
    def install(self):
        self.ensure()
        env={**os.environ,'OLLAMA_NO_CLOUD':'1','OLLAMA_HOST':'127.0.0.1:11455','OLLAMA_MODELS':str(self.weights)}
        self.progress=0;pull=subprocess.Popen([shutil.which('ollama'),'pull',MODEL],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+600
        threading.Thread(target=self._read_progress,args=(pull,),daemon=True).start()
        while pull.poll() is None:
            self._measure_download()
            if time.monotonic()>deadline or self.stopped:
                pull.kill();pull.wait();raise ValueError('Local model download timed out; check your connection and retry')
            time.sleep(.2)
        if pull.returncode:raise ValueError('Local model download failed; check your connection and retry')
        self.progress=100
        manifest=self.manifest();validate_manifest(manifest);return manifest
    def _measure_download(self):
        # Bytes actually written so far (sparse, pre-sized partial files count only what is on disk), against the known download size.
        try:
            written=sum(f.stat().st_blocks*512 for f in (self.weights/'blobs').glob('*') if f.is_file())
        except OSError:return
        self.progress=max(self.progress or 0,min(99,int(100*written/DOWNLOAD_BYTES)))
    def _read_progress(self,pull):
        # Ollama prints 'pulling ... 45% ...' with carriage returns; keep the latest percentage.
        import re
        try:
            for chunk in iter(lambda:pull.stdout.read1(512),b''):
                found=re.findall(rb'(\d{1,3})%',chunk)
                if found:self.progress=max(self.progress or 0,min(int(found[-1]),99))
        except (OSError,ValueError):pass
    def _stop_owned_process(self):
        if self.control is not None:
            os.close(self.control);self.control=None
        process,self.process=self.process,None
        if process:
            try:process.wait(5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:process.wait(5)
                except subprocess.TimeoutExpired:process.kill();process.wait(5)
    def close(self):
        with self.lock:
            self.stopped=True
            self._stop_owned_process()

def build_extension(output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]/'extensions/lmemm-source'
    manifest='''<?xml version="1.0" encoding="utf-8"?><PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011"><Metadata><Identity Language="en-US" Id="lmemm-source" Version="0.1.1" Publisher="lmemm"/><DisplayName>LMemM Project Memory</DisplayName><Description xml:space="preserve">Approved visible local evidence for LMemM</Description><Tags>memory</Tags><Categories>Other</Categories><GalleryFlags>Public</GalleryFlags><Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.85.0"/><Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value=""/><Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value=""/></Properties></Metadata><Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/><Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets></PackageManifest>'''
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('extension.vsixmanifest',manifest)
        z.writestr('[Content_Types].xml','''<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="json" ContentType="application/json"/><Default Extension="js" ContentType="application/javascript"/><Default Extension="md" ContentType="text/markdown"/><Default Extension="vsixmanifest" ContentType="text/xml"/></Types>''')
        for name in ['package.json','extension.js','bridge.js','README.md']:
            if (root/name).exists():z.write(root/name,'extension/'+name)
    return output

def _vscode_cli():
    # The shell command first, then the app in the usual folders, then wherever Spotlight says it lives.
    home=Path.home();found=[shutil.which('code')]
    for folder in ('/Applications',str(home/'Applications')):
        for app in ('Visual Studio Code.app',):found.append(folder+'/'+app+'/Contents/Resources/app/bin/code')
    for bundle in ('com.microsoft.VSCode',):
        try:
            listing=subprocess.run(['mdfind','kMDItemCFBundleIdentifier == "'+bundle+'"'],capture_output=True,text=True,timeout=5,stdin=subprocess.DEVNULL).stdout
        except (OSError,subprocess.TimeoutExpired):continue
        found+=[line.strip()+'/Contents/Resources/app/bin/code' for line in listing.splitlines() if line.strip().endswith('.app')]
    for candidate in found:
        if not candidate:continue
        try:
            resolved=Path(candidate).resolve(strict=True)
            if 'Visual Studio Code - Insiders.app' in resolved.parts:continue
            # A renamed application must still identify as standard VS Code.
            app=next((p for p in resolved.parents if p.suffix=='.app'),None)
            if app and (app/'Contents/Info.plist').is_file():
                import plistlib
                with (app/'Contents/Info.plist').open('rb') as stream:
                    if plistlib.load(stream).get('CFBundleIdentifier')!='com.microsoft.VSCode':continue
            if resolved.is_file():return candidate
        except (OSError,RuntimeError,ValueError):continue
    return None

def install_extension(directory):
    path=build_extension(Path(directory)/'lmemm-source.vsix')
    manual='Open VS Code, press Cmd+Shift+X, choose ... > Install from VSIX, and pick '+str(path)
    executable=_vscode_cli()
    if not executable:raise ValueError('Standard Visual Studio Code was not found (Insiders is not supported yet). '+manual)
    try:
        result=subprocess.run([executable,'--install-extension',str(path),'--force'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired) as error:
        raise ValueError('VS Code did not finish installing the extension ('+type(error).__name__+'). '+manual)
    if result.returncode:
        detail=(result.stderr or result.stdout or '').strip().splitlines()[-1:] or ['no details']
        raise ValueError('VS Code could not install the extension: '+detail[0][:160]+'. '+manual)
    return {'installed':True,'vsix':str(path)}


EXTENSION_VERSION='0.1.1'

def extension_installed():
    home=Path.home()
    # Only the current version counts: an older copy has no connect link, so it must be reinstalled.
    return any(next(home.glob(folder+'/lmemm.lmemm-source-'+EXTENSION_VERSION),None) for folder in ('.vscode/extensions',))

def vscode_running():
    try:
        out=subprocess.run(['osascript','-e','application id "com.microsoft.VSCode" is running'],capture_output=True,text=True,timeout=5,stdin=subprocess.DEVNULL).stdout
    except (OSError,subprocess.TimeoutExpired):return False
    return out.strip()=='true'

def quit_vscode(wait=15):
    """Ask VS Code to quit the normal way (it keeps its windows for next time); True once it has."""
    try:subprocess.run(['osascript','-e','tell application id "com.microsoft.VSCode" to quit'],capture_output=True,timeout=10,stdin=subprocess.DEVNULL)
    except (OSError,subprocess.TimeoutExpired):return False
    end=time.monotonic()+wait
    while time.monotonic()<end:
        if not vscode_running():return True
        time.sleep(.3)
    return False

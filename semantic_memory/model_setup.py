"""Explicit local model installation and an owned cloud-disabled runtime."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from .api_contracts import ModelManifest
from .embedding_runtime import validate_manifest

SELECTED_DIGEST='1b226e2802dbb772b5fc32a58f103ca1804ef7501331012de126ab22f67475ef'
MODEL='all-minilm:22m'

class OwnedEmbeddingRuntime:
    def __init__(self,weights):
        self.weights=Path(weights).resolve();self.process=None;self.control=None;self.lock=threading.RLock();self.stopped=False
    def manifest(self):
        return ModelManifest(MODEL,SELECTED_DIGEST,384,512,1,'ollama-local',str(self.weights/'manifests/registry.ollama.ai/library/all-minilm/22m'))
    def ensure(self):
        with self.lock:
            if self.stopped:raise ValueError('Runtime stopped')
            if self.process and self.process.poll() is None:return
            executable=shutil.which('ollama')
            if not executable:raise ValueError('Install the local Ollama runtime, then retry model setup')
            # Never attach source-bearing requests to an unowned server.
            with socket.socket() as probe:
                try:probe.bind(('127.0.0.1',11455))
                except OSError:raise ValueError('Local model port is occupied; stop the previous LMemM test runtime')
            self.weights.mkdir(parents=True,mode=0o700,exist_ok=True)
            r,w=os.pipe();self.control=w
            script=Path(__file__).resolve().parents[1]/'scripts/local_embedding_server.py'
            try:self.process=subprocess.Popen([sys.executable,str(script),'--control-fd',str(r),'--models',str(self.weights),'--ollama',executable],pass_fds=(r,),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            finally:os.close(r)
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(200):
                if self.process.poll() is not None:raise ValueError('Local model runtime unavailable')
                try:
                    with opener.open('http://127.0.0.1:11455/api/version',timeout=.2) as response:
                        if response.status==200:return
                except OSError:time.sleep(.05)
            raise ValueError('Local model startup timed out')
    def install(self):
        self.ensure()
        env={**os.environ,'OLLAMA_NO_CLOUD':'1','OLLAMA_HOST':'127.0.0.1:11455','OLLAMA_MODELS':str(self.weights)}
        result=subprocess.run([shutil.which('ollama'),'pull',MODEL],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=600)
        if result.returncode:raise ValueError('Local model download failed; retry setup')
        manifest=self.manifest();validate_manifest(manifest);return manifest
    def close(self):
        with self.lock:
            self.stopped=True
            if self.control is not None:
                os.close(self.control);self.control=None
            if self.process:
                try:self.process.wait(5)
                except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(5)

def build_extension(output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]/'extensions/lmemm-source'
    manifest='''<?xml version="1.0" encoding="utf-8"?><PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011"><Metadata><Identity Language="en-US" Id="lmemm-source" Version="0.1.0" Publisher="lmemm"/><DisplayName>LMemM Project Memory</DisplayName><Description xml:space="preserve">Approved visible local evidence for LMemM</Description><Tags>memory</Tags><Categories>Other</Categories><GalleryFlags>Public</GalleryFlags><Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.85.0"/><Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value=""/><Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value=""/></Properties></Metadata><Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/><Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets></PackageManifest>'''
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('extension.vsixmanifest',manifest)
        z.writestr('[Content_Types].xml','''<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="json" ContentType="application/json"/><Default Extension="js" ContentType="application/javascript"/><Default Extension="md" ContentType="text/markdown"/><Default Extension="vsixmanifest" ContentType="text/xml"/></Types>''')
        for name in ['package.json','extension.js','bridge.js','README.md']:
            if (root/name).exists():z.write(root/name,'extension/'+name)
    return output

def _vscode_cli():
    home=Path.home()
    names=['/Applications/Visual Studio Code.app','/Applications/Visual Studio Code - Insiders.app',str(home/'Applications/Visual Studio Code.app')]
    for found in [shutil.which('code')]+[n+'/Contents/Resources/app/bin/code' for n in names]:
        if found and Path(found).is_file():return found

def install_extension(directory):
    path=build_extension(Path(directory)/'lmemm-source.vsix')
    manual='Open VS Code, press Cmd+Shift+X, choose ... > Install from VSIX, and pick '+str(path)
    executable=_vscode_cli()
    if not executable:raise ValueError('VS Code was not found. '+manual)
    try:
        result=subprocess.run([executable,'--install-extension',str(path),'--force'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired) as error:
        raise ValueError('VS Code did not finish installing the extension ('+type(error).__name__+'). '+manual)
    if result.returncode:
        detail=(result.stderr or result.stdout or '').strip().splitlines()[-1:] or ['no details']
        raise ValueError('VS Code could not install the extension: '+detail[0][:160]+'. '+manual)
    return {'installed':True,'vsix':str(path)}

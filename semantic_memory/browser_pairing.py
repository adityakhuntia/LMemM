"""User-approved ingestion capability, separate from owner and AI credentials."""
import re
import secrets
import json
from .live_bridge import write_private_json
from .api_contracts import valid_id
from .intentional_sources import save_intentional, move_saved_source, delete_saved_source


def pair_browser(service,extension_id):
    if not isinstance(extension_id,str) or not re.fullmatch('[a-p]{32}',extension_id):
        raise ValueError('Invalid Chrome extension ID')
    with service.store.lock:
        token=secrets.token_hex(32);pairing_id='browser-'+secrets.token_hex(16)
        service.capabilities['browsers']={token:dict(id=pairing_id,extension_id=extension_id)}
        write_private_json(service.directory/'capabilities.json',service.capabilities)
        write_private_json(service.directory/'browser-host.json',dict(version=1,
            service_file=str(service.directory/'service.json'),capability=token,extension_id=extension_id))
        return dict(paired=True,extension_id=extension_id)


def revoke_browser(service):
    with service.store.lock:
        service.capabilities['browsers']={}
        write_private_json(service.directory/'capabilities.json',service.capabilities)
        (service.directory/'browser-host.json').unlink(missing_ok=True)
    return {'paired':False}


def browser_request(service,token,request):
    with service.store.lock:
        pairing=service.capabilities.get('browsers',{}).get(token)
        if not pairing:raise ValueError('Browser is disconnected')
        if not isinstance(request,dict) or set(request)!={'version','request_id','method','params'} or type(request['version']) is not int or request['version']!=1:
            raise ValueError('Invalid browser request')
        valid_id(request['request_id']);method=request['method'];params=request['params']
        if not isinstance(params,dict):raise ValueError('Invalid browser arguments')
        if method=='status' and not params:
            return dict(paired=True,paused=bool(service.system_flags) or service.status()['state']=='Paused')
        if method=='list_projects' and not params:
            # Native registry is the display authority. A URL/title never chooses ownership.
            path=service.directory.parent/'memory'/'projects.json'
            registry=json.loads(path.read_text()).get('projects',{}) if path.is_file() and not path.is_symlink() else {}
            return {'projects':[dict(project_id=b['project_id'],name=registry.get(b['ui_project_id'],{}).get('name') or b['ui_project_id']) for b in service.bindings() if b['active']]}
        if service.system_flags:raise ValueError('Unlock or wake the Mac before saving')
        from .index_worker import paused
        if paused(service.store):raise ValueError('Memory is paused; resume it before saving')
        if method=='save' and set(params)=={'project_id','payload'}:
            payload=params['payload']
            if not isinstance(payload,dict) or payload.get('kind') not in {'browser_page','browser_selection'}:
                raise ValueError('Browser source required')
            return save_intentional(service.store,params['project_id'],payload,owner=pairing['id'])
        if method in {'move','undo'} and set(params)==({'source_id','project_id'} if method=='move' else {'source_id'}):
            row=service.store.connection.execute('SELECT owner FROM source_details WHERE source_id=?',(params['source_id'],)).fetchone()
            if not row or row[0]!=pairing['id']:raise ValueError('Saved source unavailable')
            return move_saved_source(service.store,params['source_id'],params['project_id']) if method=='move' else delete_saved_source(service.store,params['source_id'])
        raise ValueError('Browser operation not permitted')

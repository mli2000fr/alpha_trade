"""Metadata-only disk audit. No delete, move, SQL, supplier request or secret read."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime,timezone
import heapq
import json
import os
from pathlib import Path
import shutil
import time


def save(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str),encoding='utf-8')


def scan(root,output):
    root=Path(root).resolve();output=Path(output).resolve()
    if not output.is_relative_to(root):raise ValueError('Report must stay inside workspace')
    output.mkdir(parents=True,exist_ok=False)
    started=datetime.now(timezone.utc);now=started.timestamp();tick=time.monotonic()
    stats={};links=[];errors=[];large=[];extensions=defaultdict(Counter);pending=[root]
    while pending:
        folder=pending.pop();rel=folder.relative_to(root).as_posix()
        row=dict(path=rel,direct_bytes=0,direct_files=0,children=0,newest_mtime=0,oldest_mtime=None,
                 files_modified_1d=0,bytes_modified_1d=0,files_modified_7d=0,bytes_modified_7d=0)
        stats[rel]=row
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    path=folder/entry.name;r=path.relative_to(root).as_posix()
                    try:
                        if entry.is_symlink() or entry.is_junction():
                            links.append(r);continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(path);row['children']+=1;continue
                        if not entry.is_file(follow_symlinks=False):continue
                        st=entry.stat(follow_symlinks=False);size=st.st_size;mtime=st.st_mtime
                        row['direct_bytes']+=size;row['direct_files']+=1
                        row['newest_mtime']=max(row['newest_mtime'],mtime)
                        row['oldest_mtime']=min(row['oldest_mtime'],mtime) if row['oldest_mtime'] else mtime
                        if mtime>=now-86400:row['files_modified_1d']+=1;row['bytes_modified_1d']+=size
                        if mtime>=now-7*86400:row['files_modified_7d']+=1;row['bytes_modified_7d']+=size
                        scope='/'.join(r.split('/')[:2]) if '/' in r else '.'
                        extension=Path(entry.name).suffix.lower() or '(none)'
                        extensions[scope][extension]+=size
                        item=(size,r,mtime)
                        if len(large)<200:heapq.heappush(large,item)
                        elif size>large[0][0]:heapq.heapreplace(large,item)
                    except OSError as exc:errors.append(dict(path=r,error=type(exc).__name__))
        except OSError as exc:errors.append(dict(path=rel,error=type(exc).__name__))
        if time.monotonic()-tick>15:
            print('Scanned '+str(len(stats))+' directories; current '+rel,flush=True);tick=time.monotonic()
    for rel,row in stats.items():
        row['bytes']=row['direct_bytes'];row['files']=row['direct_files'];row['directories']=0
    for rel in sorted(stats,key=lambda r:len(Path(r).parts),reverse=True):
        if rel=='.':continue
        parent=Path(rel).parent.as_posix();r=stats[rel];p=stats.get(parent)
        if p is None:continue
        for key in ('bytes','files','files_modified_1d','bytes_modified_1d','files_modified_7d','bytes_modified_7d'):
            p[key]+=r[key]
        p['directories']+=r['directories']+1
        p['newest_mtime']=max(p['newest_mtime'],r['newest_mtime'])
        if r['oldest_mtime']:p['oldest_mtime']=min(p['oldest_mtime'],r['oldest_mtime']) if p['oldest_mtime'] else r['oldest_mtime']
    # Safe process summary: no full command lines, credentials or environment values.
    active=[]
    import psutil
    for proc in psutil.process_iter(['pid','name','cmdline','cwd','create_time']):
        try:
            if proc.pid==os.getpid():continue
            info=proc.info;args=info.get('cmdline') or [];cwd=info.get('cwd')
            inside=bool(cwd) and Path(cwd).resolve().is_relative_to(root)
            paths=[arg for arg in args if str(root).casefold() in arg.casefold()]
            if not inside and not paths:continue
            modules=[args[i+1] for i,arg in enumerate(args[:-1]) if arg=='-m']
            scripts=[Path(arg).name for arg in args if arg.endswith(('.py','.ps1'))]
            active.append(dict(pid=info['pid'],name=info['name'],modules=modules,scripts=scripts,
                cwd_in_project=inside,started_at=datetime.fromtimestamp(info['create_time'],timezone.utc)))
        except (OSError,psutil.Error):continue
    disk=shutil.disk_usage(root)
    report=dict(root=str(root),started_at=started,finished_at=datetime.now(timezone.utc),
        mode='METADATA_ONLY_NO_DELETION',logical_size_bytes=stats['.']['bytes'],files=stats['.']['files'],
        directories=stats['.']['directories'],disk_total=disk.total,disk_free=disk.free,
        skipped_links=links,errors=errors,active_processes=active,
        directories_inventory=sorted(stats.values(),key=lambda r:(-r['bytes'],r['path'])),
        largest_files=[dict(bytes=s,path=p,mtime=t) for s,p,t in sorted(large,reverse=True)],
        extension_bytes={k:dict(v.most_common()) for k,v in extensions.items()})
    save(output/'inventory.json',report)
    print(json.dumps({k:report[k] for k in ('root','logical_size_bytes','files','directories','disk_free','errors','active_processes')},default=str),flush=True)
    print('REPORT '+str(output/'inventory.json'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('F:/projets'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();scan(args.root,args.output)

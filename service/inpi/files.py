"""Atomic local evidence writes with bounded Windows sharing-lock retries."""
import json
from pathlib import Path
import time
import uuid


def atomic(path: Path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str),encoding='utf-8')
        for attempt in range(7):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt==6: raise
                time.sleep(min(.1*2**attempt,1))
    finally:
        temporary.unlink(missing_ok=True)

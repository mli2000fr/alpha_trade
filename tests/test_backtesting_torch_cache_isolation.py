"""Fresh-process coverage for inherited Torch caches and partial-import errors."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from backtesting.isolation import ReadOnlyReplay


CACHES=('TORCHINDUCTOR_CACHE_DIR','TRITON_CACHE_DIR','TORCH_EXTENSIONS_DIR','CUDA_CACHE_PATH')


@pytest.mark.parametrize('fail',[False,True])
def test_compiler_cache_paths_are_local_and_inherited_values_restored(tmp_path,monkeypatch,fail):
    inherited={name:str(tmp_path/'inherited'/name) for name in CACHES}
    for name,value in inherited.items():
        monkeypatch.setenv(name,value)
    root=tmp_path/'run'
    def body():
        with ReadOnlyReplay(root).install():
            for name in CACHES:
                path=Path(os.environ[name])
                assert path.is_relative_to(root)
                assert path.is_dir()
                (path/'probe').write_text('local cache')
            if fail:
                raise ValueError('synthetic failure')
    if fail:
        with pytest.raises(ValueError,match='synthetic failure'):
            body()
    else:
        body()
    assert {name:os.environ.get(name) for name in CACHES}==inherited
    assert not (tmp_path/'inherited').exists()
    assert json.loads((root/'isolation.json').read_text())['violations']==[]


def test_resilience_and_lightning_import_in_fresh_guarded_child_with_inherited_global_caches(tmp_path):
    root=tmp_path/'fresh-run'
    inherited=tmp_path/'shared-caches'
    env=dict(os.environ)
    env.update({name:str(inherited/name) for name in CACHES})
    code='''
import importlib,json,os,sys
from pathlib import Path
from backtesting.isolation import ReadOnlyReplay
root=Path(sys.argv[1])
names=('TORCHINDUCTOR_CACHE_DIR','TRITON_CACHE_DIR','TORCH_EXTENSIONS_DIR','CUDA_CACHE_PATH')
old={name:os.environ[name] for name in names}
with ReadOnlyReplay(root).install():
    # Same import chain as the real non-Winner CLI, not preloaded by pytest.
    import backtesting.resilience
    import lightning
    import torch._dynamo
    from torch._inductor.runtime.cache_dir_utils import cache_dir,triton_cache_dir
    from torch.compiler._cache import CacheArtifactFactory
    assert Path(cache_dir()).is_relative_to(root)
    assert Path(triton_cache_dir(0)).is_relative_to(root)
    artifact=CacheArtifactFactory._artifact_types['precompile']
    importlib.import_module('backtesting.resilience')
    importlib.import_module('torch._dynamo')
    assert CacheArtifactFactory._artifact_types['precompile'] is artifact
    assert all(Path(os.environ[name]).is_relative_to(root) for name in names)
assert all(os.environ[name]==old[name] for name in names)
print('FRESH_GUARDED_IMPORT_OK')
'''
    result=subprocess.run([sys.executable,'-B','-c',code,str(root)],env=env,
        cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'FRESH_GUARDED_IMPORT_OK' in result.stdout
    assert not inherited.exists()
    receipt=json.loads((root/'isolation.json').read_text())
    assert receipt['status']=='COMPLETED' and receipt['violations']==[]

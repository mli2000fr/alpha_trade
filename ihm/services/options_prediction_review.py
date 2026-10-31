"""Read-only options review. File aliases never relax trading qualification."""
import json
from pathlib import Path

from common.universe_files import is_universe_file_source, load_universe_file_symbols
from service.options_directional import store

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_options_prediction_review(run_id, *, symbol_source, project_root=None,shared_selection=False, **context):
    """Accept a display alias only when both files match the sealed universe.

    The exact stored source is still used for all normal date/account/model,
    hash, age and session checks. No result is recomputed or republished.
    """
    folder = store.directory(run_id, context.get('root'))
    report = json.loads((folder/'report.json').read_text(encoding='utf-8'))
    saved_source = report.get('symbol_source')
    if saved_source != symbol_source:
        if not all(is_universe_file_source(s) for s in (saved_source, symbol_source)):
            raise ValueError('Filtre options incompatible : symbol_source')
        root = Path(project_root or PROJECT_ROOT)
        def symbols(source):
            return set(load_universe_file_symbols(source,directory=root/'config/univers',root=root))
        inputs = json.loads((folder/'inputs.json').read_text(encoding='utf-8'))
        frozen = inputs.get('universe')
        if not isinstance(frozen,list) or not frozen or symbols(saved_source) != set(frozen) or symbols(symbol_source) != set(frozen):
            raise ValueError('Filtre options incompatible : le contenu des univers diffère du snapshot')
    if shared_selection:
        from service.options_directional.accounts import shared_qualified
        return shared_qualified(run_id,symbol_source=saved_source,**context)
    return store.qualified(run_id,symbol_source=saved_source,**context)

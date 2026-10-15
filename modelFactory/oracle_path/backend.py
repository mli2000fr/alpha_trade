"""Explicit training/serving backend policy; legacy flags stay compatible."""
CHOICES=('lightgbm','catboost','auto')
NAMES={'lightgbm':'path_model.txt','catboost':'catboost_model.cbm'}
DECLARATIONS={'lightgbm':'lightgbm_cpu','catboost':'catboost_cpu','auto':'lightgbm_catboost_cpu'}
AUTO_SELECTION='validation_auc; exact_tie_lightgbm'


def resolve_backend(requested=None, *, enable_catboost=False):
    if requested is None:
        return 'auto' if enable_catboost else 'lightgbm'
    if requested not in CHOICES:
        raise ValueError('Oracle parcours : backend doit être lightgbm, catboost ou auto')
    return requested


def candidates_for(backend):
    backend=resolve_backend(backend)
    return ('lightgbm','catboost') if backend=='auto' else (backend,)


def selection_policy(requested):
    return AUTO_SELECTION if requested in (None,'auto') else 'explicit_backend'

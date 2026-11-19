"""Refresh stale UI imports after a directional YAML schema upgrade.

Only the interface's imported Python module is refreshed. Existing training
processes and their frozen contracts are untouched.
"""
from importlib import import_module, reload


def load_directional_settings(*, horizon=None, feature_mode=None, universe_size=None):
    module = import_module('modelFactory.oracle_path.directional')
    if getattr(module, 'CONFIG_READER_VERSION', 0) < 2:
        # A long-running Streamlit process can retain a reader predating the
        # YAML change. Do not feed new configuration fields to that old reader.
        module = reload(module)
    return module.settings(horizon=horizon, feature_mode=feature_mode, universe_size=universe_size)

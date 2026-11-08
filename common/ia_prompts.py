"""Local, versioned text catalog, with separate cloud/local model runtimes."""
import json
from pathlib import Path
import re


PROMPT_ROOT = Path(__file__).resolve().parents[1] / 'config' / 'ia' / 'prompt'
_VARIABLE = re.compile(r'\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}')


class PromptConfigurationError(ValueError):
    pass


def load_prompt(prompt_id: str, *, runtime: str = 'cloud') -> str:
    if runtime not in ('cloud', 'local'):
        raise PromptConfigurationError(f'Runtime de prompt inconnu : {runtime}')
    root = PROMPT_ROOT.resolve()
    catalog_path = root / 'catalog.json'
    try:
        catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise PromptConfigurationError(f'Catalogue de prompts illisible : {catalog_path}') from exc
    if not isinstance(catalog, dict) or catalog.get('schema_version') != 1 or not isinstance(catalog.get('prompts'), dict):
        raise PromptConfigurationError(f'Format du catalogue de prompts invalide : {catalog_path}')
    entry = catalog['prompts'].get(prompt_id)
    if not isinstance(entry, dict) or entry.get('runtime') != runtime:
        raise PromptConfigurationError(f'Prompt {prompt_id!r} absent ou incompatible avec le runtime {runtime}')
    relative = entry.get('path')
    if not isinstance(relative, str) or not relative:
        raise PromptConfigurationError(f'Chemin de prompt invalide : {prompt_id}')
    path = (root / relative).resolve()
    if not path.is_relative_to(root / runtime):
        raise PromptConfigurationError(f'Prompt hors du répertoire {runtime} : {prompt_id}')
    try:
        value = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        raise PromptConfigurationError(f'Prompt illisible : {path}') from exc
    if not value.strip():
        raise PromptConfigurationError(f'Prompt vide : {path}')
    # Keep whitespace and newlines: archived request hashes must stay identical.
    # No cache: editing a file applies to the next newly built request.
    return value


def render_prompt(prompt_id: str, *, variables: dict[str, str], runtime: str = 'cloud') -> str:
    template = load_prompt(prompt_id, runtime=runtime)
    expected = set(_VARIABLE.findall(template))
    if set(variables) != expected or any(not isinstance(v, str) for v in variables.values()):
        raise PromptConfigurationError(f'Variables de prompt incompatibles : {prompt_id}; attendues={sorted(expected)}')
    # Single substitution pass; data containing braces is never interpreted.
    return _VARIABLE.sub(lambda match: variables[match.group(1)], template)

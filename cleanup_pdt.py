#!/usr/bin/env python3
"""Script to completely remove all PDT references from code files"""

import re
from pathlib import Path

def clean_pdt_from_yaml():
    """Remove all execution_pdt_rule lines from YAML"""
    yaml_path = Path('config/capital_presets.yaml')
    with open(yaml_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Keep lines that don't contain execution_pdt_rule
    cleaned_lines = [l for l in lines if 'execution_pdt_rule' not in l]

    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.writelines(cleaned_lines)

    removed = len(lines) - len(cleaned_lines)
    print(f"✓ YAML: Removed {removed} execution_pdt_rule lines")

def clean_pdt_from_common_presets():
    """Remove PDT-related code from common/capital_presets.py"""
    py_path = Path('common/capital_presets.py')
    with open(py_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_len = len(content)

    # Remove lines mentioning pdt_rule
    lines = content.split('\n')
    cleaned_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip lines with pdt_rule mapping
        if 'pdt_rule' in line and ('endswith' in line or '(' in line or ':' in line):
            i += 1
            continue
        cleaned_lines.append(line)
        i += 1

    cleaned_content = '\n'.join(cleaned_lines)

    with open(py_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)

    print(f"✓ common/capital_presets.py: Cleaned PDT references")

def clean_pdt_from_cli():
    """Remove PDT-related CLI arguments"""
    cli_path = Path('backtesting/cli/_impl.py')
    with open(cli_path, 'r', encoding='utf-8') as f:
        content = f.read()

    #  Remove --pdt-rule argument and related code
    lines = content.split('\n')
    cleaned_lines = []
    skip_until_next_add_argument = False

    for i, line in enumerate(lines):
        # Skip lines that add --pdt-rule argument
        if '"--pdt-rule"' in line or "'--pdt-rule'" in line:
            skip_until_next_add_argument = True
            continue
        if skip_until_next_add_argument:
            if 'add_argument' in line:
                skip_until_next_add_argument = False
                cleaned_lines.append(line)
            continue

        # Skip pdt_rule mappings
        if '"--pdt-rule":' in line or "'--pdt-rule':" in line:
            continue
        if 'pdt_rule' in line and '--pdt-rule' in line:
            continue

        # Skip pdt_rule from explicit_flags
        if '"pdt_rule"' in line and 'explicit_flags' in lines[max(0, i-5):i+5]:
            continue

        # Skip lines that set pdt_rule from args
        if 'pdt_rule=args.pdt_rule' in line:
            continue

        cleaned_lines.append(line)

    cleaned_content = '\n'.join(cleaned_lines)

    with open(cli_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)

    print(f"✓ backtesting/cli/_impl.py: Removed --pdt-rule arguments")

if __name__ == '__main__':
    print("\n🧹 Cleaning up PDT references...\n")
    clean_pdt_from_yaml()
    clean_pdt_from_common_presets()
    clean_pdt_from_cli()
    print("\n✅ PDT cleanup complete!\n")


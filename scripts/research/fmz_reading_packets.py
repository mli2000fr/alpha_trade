"""Read-only packets for sequential FMZ review; displaying a file never marks it reviewed."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


def reading_text(body):
    """Prefer the English prose when supplied as a duplicate translation.

    All code and source details are retained; only empty lines are elided.
    Does not execute, import or compile any downloaded source.
    """
    at = body.find('> Source')
    description, source = (body[:at], body[at:]) if at >= 0 else (body, '')
    trans = re.search(r'\[trans\]([\s\S]*?)\[/trans\]', description)
    if trans and '||' in trans.group(1):
        english = trans.group(1).split('||', 1)[1].strip()
        description = description[:trans.start()] + english + description[trans.end():]
    return '\n'.join(line for line in (description + '\n' + source).splitlines() if line.strip())


def focused_reading_text(body):
    """Keep logic and risk prose and ALL source; omit repetitive promotion/inputs.

    This is a display aid, never a review-status writer. Full originals remain
    immutable. Argument tables duplicate input declarations in the source.
    """
    text = reading_text(body)
    at = text.find('> Source')
    if at < 0:
        return text
    prose, source = text[:at], text[at:]
    kept = []
    skip = False
    for line in prose.splitlines():
        if line.startswith('> Strategy Arguments'):
            break
        if line.startswith('#'):
            title = line.lstrip('# ').lower()
            skip = bool(re.search(r'advantage|benefit|optimi|enhance|improve|summary|conclusion|优势|优化|总结', title))
        if not skip:
            kept.append(line)
    return '\n'.join(kept) + '\n' + re.sub(r'(?<=\S)[ \t]{8,}', ' ', source)


def dense_reading_text(text):
    """Elide blank lines and standalone slash comments for compact display."""
    return '\n'.join(line for line in text.splitlines()
                     if line.strip() and not line.lstrip().startswith('//'))


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('artifacts/research/fmz_strategy_review/20261021-v1'))
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--end', type=int, required=True)
    parser.add_argument('--focus', action='store_true', help='Keep logic/risk prose and all code; omit promotional repetition and duplicate input tables')
    parser.add_argument('--dense', action='store_true', help='With focus: elide standalone // comments and blank lines, never executable statements')
    args = parser.parse_args()
    rows = json.loads((args.root / 'screening.json').read_text(encoding='utf-8'))
    if not 1 <= args.start <= args.end <= len(rows):
        parser.error('Range outside the complete source inventory')
    for index in range(args.start - 1, args.end):
        row = rows[index]
        body = (args.root / row['local_raw']).read_bytes()
        if hashlib.sha256(body).hexdigest() != row['sha256']:
            raise ValueError('Source differs from archived manifest')
        print(f'\nDOCUMENT {index+1}/1000: {row["path"]}\nSHA256 {row["sha256"]}\n')
        render = focused_reading_text if args.focus else reading_text
        rendered = render(body.decode('utf-8-sig'))
        if args.dense:
            rendered = dense_reading_text(rendered)
        print(rendered)
        print(f'END DOCUMENT {index+1}')


if __name__ == '__main__':
    main()

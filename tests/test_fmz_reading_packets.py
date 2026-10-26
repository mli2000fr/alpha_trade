from scripts.research.fmz_reading_packets import (
    dense_reading_text, focused_reading_text, reading_text,
)


def test_translation_on_same_line_is_not_repeated():
    body = '> Name\nN\n[trans]\n中文描述。 || \n## Overview\nEnglish.\n[/trans]\n> Source\n```pine\nx=1\n```'
    packet = reading_text(body)
    assert '中文' not in packet
    assert 'English.' in packet
    assert 'x=1' in packet


def test_translation_on_new_line_is_not_repeated():
    body = '[trans]\n中文\n||\nEnglish\n[/trans]\n> Source\ncode'
    assert reading_text(body) == 'English\n> Source\ncode'


def test_single_language_preserves_all_nonempty_lines():
    body = '> Name\n\n测试\n> Source\n```js\nvar buy=true;\n// comment\n```'
    packet = reading_text(body)
    assert '测试' in packet
    assert 'var buy=true;' in packet
    assert '// comment' in packet


def test_code_boolean_operator_not_mistaken_for_translation():
    body = '> Name\nN\n> Source\n```js\nif(a || b) buy();\n```'
    assert 'if(a || b) buy();' in reading_text(body)


def test_focus_keeps_logic_risk_and_source_not_promotional_sections():
    body = ('## Overview\nIdea\n## Advantages\nPromotion\n'
            '## Strategy Logic\nRule\n## Optimization\nTune everything\n'
            '## Risks\nGap\n> Source (javascript)\n```js\n'
            '// Summary remains in original code\nif(a || b) buy();\n```')
    packet = focused_reading_text(body)
    assert all(value in packet for value in ('Idea', 'Rule', 'Gap', 'if(a || b) buy();'))
    assert 'Promotion' not in packet and 'Tune everything' not in packet
    assert '// Summary remains in original code' in packet


def test_focus_omits_duplicate_argument_table_not_source_inputs():
    body = ('## Overview\nIdea\n> Strategy Arguments\nDuplicate table\n'
            '> Source (pine)\n```pine\nn = input(20)\n```')
    packet = focused_reading_text(body)
    assert 'Duplicate table' not in packet
    assert 'n = input(20)' in packet


def test_focus_does_not_treat_source_headings_as_prose_sections():
    body = ('> Source (python)\n```python\n# Optimization\n'
            'if x:\n    buy()\n```\n> Detail\nhttps://example.com')
    assert '# Optimization\nif x:\n    buy()' in focused_reading_text(body)
    assert 'https://example.com' in focused_reading_text(body)


def test_dense_keeps_statements_indentation_and_inline_comments():
    body = ('\n// commentary\n    // another comment\nif condition:\n'
            '    buy()  // inline stays\n# python comment stays\n')
    assert dense_reading_text(body) == (
        'if condition:\n    buy()  // inline stays\n# python comment stays')

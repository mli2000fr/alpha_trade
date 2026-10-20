from scripts.research.us_index_deletion_source_check import echoed_terms


def test_echo_detects_boolean_text_interpreted_as_literals():
    value={'query':{'query':{'bool':{'must':[{'match_phrase':{'doc_text':x}} for x in ['Russell','AND','(']]}}}}
    assert echoed_terms(value)==['Russell','AND','(']
    assert echoed_terms(value)!=['Russell','removed']


def test_simple_query_is_not_assumed_valid_without_echo():
    assert echoed_terms({'hits':{'total':0}})==[]

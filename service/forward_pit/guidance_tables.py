"""Conservative HTML table provenance for E21 research dollar ranges."""
import re
from service.forward_pit.guidance_audit import VisibleText


class TableLayout(VisibleText):
    def __init__(self):
        super().__init__()
        self.visible = ''
        self.synced = 0
        self.tables = []
        self.stack = []
        self.last_table_end = 0

    def sync(self):
        for part in self.parts[self.synced:]:
            part = re.sub(r'\s+', ' ', part)
            if self.visible.endswith(' ') and part.startswith(' '):
                part = part[1:]
            self.visible += part
        self.synced = len(self.parts)

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        self.sync()
        if tag == 'table':
            table = {'id': len(self.tables), 'start': len(self.visible), 'rows': [],
                'heading': self.visible[max(self.last_table_end, len(self.visible)-750):],
                'nested': bool(self.stack)}
            self.tables.append(table)
            self.stack.append({'table': table, 'row': None, 'cell': None})
        elif self.stack and tag == 'tr':
            self.stack[-1]['row'] = []
        elif self.stack and tag in ['td', 'th']:
            attributes = dict(attrs)
            self.stack[-1]['cell'] = {'start': len(self.visible), 'kind': tag,
                'colspan': attributes.get('colspan', '1'), 'rowspan': attributes.get('rowspan', '1')}

    def handle_data(self, data):
        super().handle_data(data)
        self.sync()

    def handle_endtag(self, tag):
        if self.stack and tag in ['td', 'th']:
            frame = self.stack[-1]
            if frame['cell'] and frame['row'] is not None:
                cell = frame['cell']
                cell.update(end=len(self.visible), text=self.visible[cell['start']:].strip())
                frame['row'].append(cell)
                frame['cell'] = None
        elif self.stack and tag == 'tr':
            frame = self.stack[-1]
            if frame['row'] is not None:
                frame['table']['rows'].append(frame['row'])
                frame['row'] = None
        elif self.stack and tag == 'table':
            frame = self.stack.pop()
            frame['table']['end'] = len(self.visible)
            self.last_table_end = len(self.visible)
        super().handle_endtag(tag)
        self.sync()


def table_context(layout, start, end):
    for table in reversed(layout.tables):
        if not table['start'] <= start < table.get('end', -1):
            continue
        for row_index, row in enumerate(table['rows']):
            for cell_index, cell in enumerate(row):
                if cell['start'] <= start and end <= cell['end']:
                    labels = [c['text'] for c in row[:cell_index] if c['text']]
                    label = labels[0] if labels else None
                    heading = table['heading']
                    result = {'table_id': table['id'], 'row_index': row_index,
                        'cell_index': cell_index, 'row_label': label,
                        'heading': heading, 'cell_text': cell['text'],
                        'role': 'AMBIGUOUS', 'reason': 'NO_EXPLICIT_TABLE_ROLE'}
                    if table['nested'] or any(c['rowspan'] != '1' for c in row):
                        result['reason'] = 'NESTED_OR_ROWSPAN_REQUIRES_REVIEW'
                        return result
                    if re.search(r'\brespectively\b', cell['text'], re.I):
                        result['reason'] = 'SEPARATE_VALUES_NOT_INTERVAL'
                        return result
                    # Column headings may explicitly distinguish old/current guidance.
                    previous_headers = [r for r in table['rows'][:row_index] if any(c['kind'] == 'th' for c in r)]
                    column_header = None
                    if previous_headers and all(c['colspan'] == '1' for c in previous_headers[-1] + row):
                        header_row = previous_headers[-1]
                        if cell_index < len(header_row):
                            column_header = header_row[cell_index]['text']
                    result['column_header'] = column_header
                    if column_header and re.search(r'prior|previous', column_header, re.I) and re.search(r'guidance|forecast|outlook', column_header, re.I):
                        result.update(role='PRIOR_FORECAST', reason='EXPLICIT_PRIOR_COLUMN')
                    elif column_header and re.search(r'current|new|updated', column_header, re.I) and re.search(r'guidance|forecast|outlook', column_header, re.I):
                        result.update(role='NEW_FORECAST', reason='EXPLICIT_CURRENT_COLUMN')
                    elif re.search(r'following table summarizes[^.!?]{0,180}\btargets\s*:', heading, re.I):
                        result.update(role='NEW_FORECAST', reason='EXPLICIT_TARGETS_HEADING')
                    elif re.search(r'\b(?:consolidated statements of (?:income|operations)|actual results)\b', heading, re.I):
                        result.update(role='REALIZED_RESULT', reason='EXPLICIT_RESULTS_HEADING')
                    return result
        return {'table_id': table['id'], 'role': 'AMBIGUOUS',
            'reason': 'RANGE_CROSSES_TABLE_CELLS', 'heading': table['heading']}
    return None

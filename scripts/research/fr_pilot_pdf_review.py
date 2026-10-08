"""Render and extract the six bounded pilot PDFs with the bundled PDF runtime."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path


def run(report_path, output_name='extraction'):
    from pypdf import PdfReader
    import pypdfium2
    report_path = Path(report_path).resolve()
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if report['market_code'] != 'FR_EQ' or report['requested'] > 6:
        raise ValueError('Bounded FR pilot required')
    if output_name not in ('extraction', 'extraction-v2'):
        raise ValueError('Local extraction directory required')
    output = report_path.parent / output_name
    output.mkdir(exist_ok=False)
    documents = []
    for item in report['documents']:
        path = Path(item['pdf_path']).resolve()
        if not path.is_relative_to(report_path.parent / 'pdfs'):
            raise ValueError('PDF outside archive')
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Changed PDF')
        reader = PdfReader(path)
        if len(reader.pages) > 40:
            raise ValueError('Review page limit exceeded')
        pages = [{'page': n + 1, 'text': page.extract_text() or ''}
                 for n, page in enumerate(reader.pages)]
        text_path = output / (item['id'] + '.json')
        text_path.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding='utf-8')
        pdf = pypdfium2.PdfDocument(str(path))
        renders = []
        for n in range(len(pdf)):
            render_path = output / f"{item['id']}-p{n + 1}.png"
            page = pdf[n]
            bitmap = page.render(scale=1.3)
            bitmap.to_pil().save(render_path)
            bitmap.close()
            page.close()
            renders.append(str(render_path))
        pdf.close()
        documents.append({'id': item['id'], 'sha256': item['sha256'],
                          'pages': len(pages), 'text_path': str(text_path), 'renders': renders})
        print(json.dumps({'id': item['id'], 'pages': pages}, ensure_ascii=True))
    (output / 'manifest.json').write_text(json.dumps({
        'created_at': datetime.now(UTC).isoformat(), 'documents': documents,
        'status': 'EXTRACTED_RENDERED_NOT_QUALIFIED'}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    parser.add_argument('--output-name', default='extraction')
    args = parser.parse_args()
    run(args.report, args.output_name)

"""Extract relevant annual-report pages without promoting evidence."""
import sys
from pathlib import Path

from pypdf import PdfReader


def main():
    for argument in sys.argv[1:]:
        path = Path(argument)
        reader = PdfReader(path)
        for index, page in enumerate(reader.pages):
            try:
                content = page.extract_text()
            except (UnicodeError, ValueError) as exc:
                print(f"UNREADABLE {path.name} page={index + 1}: {exc}")
                continue
            if any(term in content.lower() for term in
                   ("registered office", "7.9 dividends", "7.8 equity")):
                print(f"\nSOURCE {path.name} PAGE {index + 1}\n{content}")


if __name__ == "__main__":
    main()

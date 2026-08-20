import sys
sys.path.insert(0, "f:/projets")
import re, requests
UA = {"User-Agent": "AlphaTradeML/1.0 (alphatrade@example.com)"}

# tester la fonction fetch_form4_xml corrigée sur TSCO
from scripts.e4b4_finra_form4_download import fetch_form4_xml, parse_transactions, _get

cik = "0000916365"
acc = "0002144093-26-000007"
primary = "xslF345X06/wk-form4_1786480267.xml"

xml = fetch_form4_xml(cik, acc, primary)
print("TSCO xml len:", len(xml))
if xml:
    txs = parse_transactions(xml)
    print("TSCO n tx:", len(txs))
    for t in txs[:3]:
        print("  ", t)

# BAX aussi
cik2 = "0000010456"
acc2 = "0001062993-25-008905"
xml2 = fetch_form4_xml(cik2, acc2, None)
txs2 = parse_transactions(xml2)
print("\nBAX n tx:", len(txs2))
print("  ", txs2[0] if txs2 else None)

import requests, re
UA = {"User-Agent": "AlphaTradeML/1.0 (alphatrade@example.com)"}

# reprendre la fonction parse_transactions corrigée pour test
def val(blk, tag):
    m = re.search(rf"<{tag}[^>]*>\s*<value>(.*?)</value>", blk, re.S)
    if m:
        return m.group(1).strip()
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", blk, re.S)
    if m:
        inner = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        return inner if inner else None
    return None

def parse_transactions(xml):
    blocks = re.findall(r"<(?:nonDerivative|derivative)Transaction[s]?>(.*?)</(?:nonDerivative|derivative)Transaction[s]?>", xml, re.S)
    out = []
    for blk in blocks:
        out.append({
            "code": val(blk, "transactionCode"),
            "date": val(blk, "transactionDate"),
            "shares": val(blk, "transactionShares"),
            "price": val(blk, "transactionPricePerShare"),
            "owned": val(blk, "sharesOwnedFollowingTransaction"),
            "acqdisp": val(blk, "transactionAcquiredDisposedCode"),
        })
    return out

# test BAX
url = "https://www.sec.gov/Archives/edgar/data/0000010456/000106299325008905/form4.xml"
r = requests.get(url, headers=UA, timeout=30)
txs = parse_transactions(r.text)
print("BAX test: n tx =", len(txs))
for t in txs[:3]:
    print("  ", t)

# test TSCO (celui qui donnait 0)
url2 = "https://www.sec.gov/Archives/edgar/data/0000916365/0000916365/primary_doc.xml"  # placeholder
# chercher un vrai accession TSCO via submissions
r3 = requests.get("https://data.sec.gov/submissions/CIK0000916365.json", headers=UA, timeout=30).json()
rec = r3["filings"]["recent"]
for i, fm in enumerate(rec["form"]):
    if fm == "4":
        acc = rec["accessionNumber"][i]
        print("TSCO accession test:", acc, rec["filingDate"][i])
        url3 = f"https://www.sec.gov/Archives/edgar/data/916365/{acc.replace('-','')}/form4.xml"
        rr = requests.get(url3, headers=UA, timeout=30)
        txs3 = parse_transactions(rr.text)
        print("  TSCO n tx:", len(txs3), "| sample:", txs3[0] if txs3 else None)
        break

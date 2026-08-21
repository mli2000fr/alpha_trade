import requests, re
UA = {"User-Agent": "AlphaTradeML/1.0 (alphatrade@example.com)"}

acc = "0002144093-26-000007"
url = f"https://www.sec.gov/Archives/edgar/data/916365/{acc.replace('-','')}/form4.xml"
r = requests.get(url, headers=UA, timeout=30)
print("status:", r.status_code, "len:", len(r.content))
txt = r.text

# chercher des motifs transaction
print("\n--- motifs trouvés ---")
for pat in ["nonDerivativeTransaction", "derivativeTransaction", "transactionCode", "<transaction>", "ownershipDocument", "nonDerivativeHolding"]:
    print(f"  {pat}: {len(re.findall(pat, txt))} occurrences")

# montrer le début du XML
print("\n--- début XML ---")
print(txt[:1500])

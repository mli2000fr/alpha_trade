import requests, re
UA = {"User-Agent": "AlphaTradeML/1.0 (alphatrade@example.com)"}

# un Form 4 BAX déjà téléchargé (accession 0001062993-25-008905)
cik = "0000010456"
acc = "0001062993-25-008905"
url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-','')}/form4.xml"
r = requests.get(url, headers=UA, timeout=30)
print("status:", r.status_code, "len:", len(r.content))
txt = r.text

# montrer les premières balises autour de transactionCode
for tag in ["transactionCode", "transactionDate", "transactionShares", "transactionPricePerShare", "sharesOwnedFollowingTransaction", "transactionAcquiredDisposedCode"]:
    # chercher toutes les formes: <tag>...</tag>, <tag attr>...</tag>
    pat = re.compile(rf"<{tag}[^>]*>(.*?)</{tag}>", re.S)
    ms = pat.findall(txt)
    if ms:
        print(f"  {tag}: {[m.strip()[:60] for m in ms[:2]]}")

# structure générale: montrer un extrait
print("\n--- extrait XML ---")
i = txt.find("nonDerivativeTransaction")
print(txt[i:i+800] if i >= 0 else "pas de nonDerivativeTransaction; len="+str(len(txt)))

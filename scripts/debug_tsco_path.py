import requests, re
UA = {"User-Agent": "AlphaTradeML/1.0 (alphatrade@example.com)"}

# TSCO accession 0002144093-26-000007 -> lister le dossier d'archives
cik = "916365"
acc = "0002144093-26-000007"
url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-','')}/"
r = requests.get(url, headers=UA, timeout=30)
print("index status:", r.status_code)
# extraire les liens de fichiers
links = re.findall(r'href="([^"]+)"', r.text)
for l in links:
    if "xml" in l.lower() or "htm" in l.lower():
        print("  ", l)

# aussi via submissions recent primaryDocument
r2 = requests.get("https://data.sec.gov/submissions/CIK0000916365.json", headers=UA, timeout=30).json()
rec = r2["filings"]["recent"]
for i, fm in enumerate(rec["form"]):
    if fm == "4" and rec["accessionNumber"][i] == acc:
        print("\nprimaryDocument:", rec["primaryDocument"][i])
        print("primaryDocDescription:", rec["primaryDocDescription"][i])
        break

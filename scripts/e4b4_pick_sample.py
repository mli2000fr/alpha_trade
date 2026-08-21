from pathlib import Path

ticket = [s.strip().upper() for s in open("config/ticket_recherche.txt", encoding="utf-8").read().split(",") if s.strip()]
print("n symboles univers:", len(ticket))
sample = ticket[::20]
print("=== echantillon 20 symboles ===")
print(", ".join(sample))
Path("artifacts/models/oracle/e4b4_sample20.txt").write_text("\n".join(sample), encoding="utf-8")
print("sauve:", "artifacts/models/oracle/e4b4_sample20.txt")

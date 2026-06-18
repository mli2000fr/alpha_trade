"""Remove risk_force_close_on_breaker from all presets."""
import yaml

with open("f:/projets/config/capital_presets.yaml", "r") as f:
    data = yaml.safe_load(f)

for preset in data["presets"]:
    vals = preset["values"]
    vals.pop("risk_force_close_on_breaker", None)

with open("f:/projets/config/capital_presets.yaml", "w") as f:
    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

# Verify
with open("f:/projets/config/capital_presets.yaml", "r") as f:
    verify = yaml.safe_load(f)
for p in verify["presets"]:
    has = "risk_force_close_on_breaker" in p["values"]
    print(f"  {p['key']}: force_close_in_preset={has}")
print("Done")

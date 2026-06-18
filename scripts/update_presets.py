"""Add quick win params + force_close to all capital presets."""
import yaml

with open("f:/projets/config/capital_presets.yaml", "r") as f:
    data = yaml.safe_load(f)

params_before_exec = {
    "risk_min_score_threshold": 0.7,
    "risk_min_breakout_days": 1,
    "risk_force_close_on_breaker": True,
}

params_after_trailing = {
    "execution_entry_order_type": "limit",
    "execution_limit_price_buffer_bps": -100,
}

for preset in data["presets"]:
    key = preset["key"]
    vals = preset["values"]
    new_vals = {}
    added_before = False
    added_after = False

    for k, v in vals.items():
        new_vals[k] = v
        if k == "risk_prediction_weight" and not added_before:
            for nk, nv in params_before_exec.items():
                if nk not in new_vals:
                    new_vals[nk] = nv
            added_before = True
        if k == "execution_trailing_r_multiple" and not added_after:
            for nk, nv in params_after_trailing.items():
                if nk not in new_vals:
                    new_vals[nk] = nv
            added_after = True

    # Fix max_positions for micro account
    if key == "capital_0_2000_eur":
        new_vals["risk_max_positions"] = 3

    preset["values"] = new_vals

with open("f:/projets/config/capital_presets.yaml", "w") as f:
    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

print("Done. Verifying...")
with open("f:/projets/config/capital_presets.yaml", "r") as f:
    verify = yaml.safe_load(f)
for p in verify["presets"]:
    v = p["values"]
    ok = all(k in v for k in ["risk_min_score_threshold", "risk_min_breakout_days", "risk_force_close_on_breaker", "execution_entry_order_type", "execution_limit_price_buffer_bps"])
    maxpos = v.get("risk_max_positions", "?")
    print(f"  {p['key']}: {'OK' if ok else 'MISSING'} (max_pos={maxpos})")

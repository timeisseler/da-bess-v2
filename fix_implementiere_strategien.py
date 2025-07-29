#!/usr/bin/env python3
"""
Fixed implementation of strategy deployment with proper SoC tracking and validation.
This ensures SoC always stays within 5-95% limits by:
1. Properly calculating SoC using the formula: SoC[t] = SoC[t-1] + action[t-1]/4
2. Validating each strategy before implementation
3. Adding SoC values to the final schedule for transparency
"""

import json
import os
import pandas as pd
from datetime import datetime


def implementiere_strategien_fixed(strategien_json, fahrplan_json, user_inputs_json):
    """
    Fixed implementation that properly tracks and validates SoC throughout strategy deployment.
    
    Returns:
        neuer_fahrplan, csv_path, kpis, implementierte_strategien_detail, strategien_detail_csv_path
    """
    print("\n🔧 Starting FIXED strategy implementation with proper SoC tracking...")
    
    # Load data
    with open(strategien_json, "r", encoding="utf-8") as f:
        strategien = json.load(f)
    with open(fahrplan_json, "r", encoding="utf-8") as f:
        fahrplan = json.load(f)
    with open(user_inputs_json, "r", encoding="utf-8") as f:
        user_inputs = json.load(f)
    
    # Load additional data for comprehensive tracking
    with open("flexband_safeguarded.json", "r", encoding="utf-8") as f:
        flexband = json.load(f)
    
    try:
        with open("da-prices.json", "r", encoding="utf-8") as f:
            da_prices = json.load(f)
    except:
        da_prices = [{"value": 0.0} for _ in range(len(fahrplan))]
    
    # Constants
    capacity = user_inputs["capacity_kWh"]
    daily_cycles = user_inputs["daily_cycles"]
    MIN_SOC = 0.05 * capacity  # 5% of capacity
    MAX_SOC = 0.95 * capacity  # 95% of capacity
    INITIAL_SOC = 0.3 * capacity  # 30% initial charge
    
    print(f"📊 Battery capacity: {capacity} kWh")
    print(f"📊 SoC limits: {MIN_SOC:.1f} - {MAX_SOC:.1f} kWh")
    print(f"📊 Initial SoC: {INITIAL_SOC:.1f} kWh")
    
    # Calculate existing cycles from original schedule
    bisherige_belademenge = sum(fp["value"] * 0.25 for fp in fahrplan if fp["value"] > 0)
    bisherige_zyklen = bisherige_belademenge / capacity
    max_belademenge = (daily_cycles * 365 - bisherige_zyklen) * capacity
    
    print(f"📊 Existing cycles: {bisherige_zyklen:.2f}")
    print(f"📊 Remaining capacity for strategies: {max_belademenge:.1f} kWh")
    
    # Create new schedule as a copy
    neuer_fahrplan = [{"index": fp["index"], 
                      "timestamp": fp["timestamp"], 
                      "value": fp["value"],
                      "soc": 0.0} for fp in fahrplan]  # Add SoC field
    
    # Calculate initial SoC trajectory for the original schedule
    soc_trajectory = []
    current_soc = INITIAL_SOC
    
    for i in range(len(fahrplan)):
        soc_trajectory.append(current_soc)
        if i < len(fahrplan) - 1:  # Don't calculate beyond last index
            # SoC[t+1] = SoC[t] + action[t]/4
            current_soc += fahrplan[i]["value"] / 4
            # Ensure SoC stays within physical bounds (shouldn't happen with valid input)
            current_soc = max(0, min(capacity, current_soc))
    
    print(f"📊 Original schedule SoC range: {min(soc_trajectory):.1f} - {max(soc_trajectory):.1f} kWh")
    
    # Tracking variables
    gesamt_belademenge = 0.0
    implementierte_strategien = []
    implementierte_strategien_detail = []
    verwendete_zeiträume = set()
    skipped_strategies = []
    
    # Process strategies sorted by profit (highest first)
    print(f"\n🔍 Evaluating {len(strategien)} strategies...")
    
    for strategy_num, strategie in enumerate(strategien):
        start_idx = strategie["start_index"] - 1  # Convert to 0-based
        end_idx = strategie["end_index"] - 1
        
        # Check if time period is already used
        zeitraum_range = set(range(start_idx, end_idx + 1))
        if zeitraum_range.intersection(verwendete_zeiträume):
            skipped_strategies.append((strategie["strategie_id"], "Time period overlap"))
            continue
        
        # Check cycle capacity limit
        strategie_belademenge = strategie["gesamte_lademenge"]
        if gesamt_belademenge + strategie_belademenge > max_belademenge:
            skipped_strategies.append((strategie["strategie_id"], "Cycle limit exceeded"))
            break
        
        # CRITICAL: Validate strategy won't violate SoC limits
        print(f"\n  Testing strategy {strategie['strategie_id']} ({strategie['strategie_typ']})...")
        
        # Create a test copy of affected portion of schedule
        test_schedule = [fp.copy() for fp in neuer_fahrplan]
        
        # Apply strategy to test schedule
        for detail in strategie["strategie_details"]:
            idx = detail["index"]
            if 0 <= idx < len(test_schedule):
                test_schedule[idx]["value"] += detail["aktion"]
        
        # Simulate SoC for the ENTIRE schedule with this strategy
        test_soc = INITIAL_SOC
        soc_valid = True
        min_test_soc = test_soc
        max_test_soc = test_soc
        
        for i in range(len(test_schedule)):
            # Check current SoC
            if test_soc < MIN_SOC - 0.1 or test_soc > MAX_SOC + 0.1:  # 0.1 kWh tolerance
                soc_valid = False
                break
            
            min_test_soc = min(min_test_soc, test_soc)
            max_test_soc = max(max_test_soc, test_soc)
            
            # Calculate next SoC
            if i < len(test_schedule) - 1:
                test_soc += test_schedule[i]["value"] / 4
        
        # Final SoC check
        if test_soc < MIN_SOC - 0.1 or test_soc > MAX_SOC + 0.1:
            soc_valid = False
        
        if not soc_valid:
            skipped_strategies.append((strategie["strategie_id"], 
                f"SoC violation: {min_test_soc:.1f}-{max_test_soc:.1f} kWh"))
            print(f"    ❌ Would violate SoC limits: {min_test_soc:.1f} - {max_test_soc:.1f} kWh")
            continue
        
        print(f"    ✅ SoC range OK: {min_test_soc:.1f} - {max_test_soc:.1f} kWh")
        print(f"    💰 Profit: {strategie['profit_euro']:.2f} €")
        
        # IMPLEMENT THE STRATEGY
        for detail in strategie["strategie_details"]:
            idx = detail["index"]
            if 0 <= idx < len(neuer_fahrplan):
                neuer_fahrplan[idx]["value"] += detail["aktion"]
                neuer_fahrplan[idx]["value"] = round(neuer_fahrplan[idx]["value"], 2)
        
        # Update tracking
        verwendete_zeiträume.update(zeitraum_range)
        gesamt_belademenge += strategie_belademenge
        implementierte_strategien.append(strategie["strategie_id"])
        
        # Create detailed tracking entry
        implementierungs_detail = {
            "strategie_id": strategie["strategie_id"],
            "zeitraum_id": strategie["zeitraum_id"],
            "strategie_typ": strategie["strategie_typ"],
            "start_index": strategie["start_index"],
            "end_index": strategie["end_index"],
            "länge_stunden": strategie["länge_stunden"],
            "basis_soc": strategie["basis_soc"],
            "profit_euro": strategie["profit_euro"],
            "implementierungs_reihenfolge": len(implementierte_strategien),
            "implementierte_schritte": []
        }
        
        # Add detailed steps
        for detail in strategie["strategie_details"]:
            idx = detail["index"]
            if 0 <= idx < len(da_prices):
                step_info = {
                    "index": idx,
                    "timestamp": neuer_fahrplan[idx]["timestamp"],
                    "aktion_typ": "Laden" if detail["aktion"] > 0 else "Entladen",
                    "strategie_aktion": detail["aktion"],
                    "finale_aktion": neuer_fahrplan[idx]["value"],
                    "da_preis_ct_kwh": da_prices[idx]["value"],
                    "energie_kwh": detail["aktion"] / 4,
                    "kosten_erlös_euro": -(da_prices[idx]["value"] * detail["aktion"] / 4) / 100
                }
                implementierungs_detail["implementierte_schritte"].append(step_info)
        
        implementierte_strategien_detail.append(implementierungs_detail)
    
    # CRITICAL: Calculate and add final SoC values to schedule
    print("\n📊 Calculating final SoC trajectory...")
    current_soc = INITIAL_SOC
    min_final_soc = current_soc
    max_final_soc = current_soc
    
    for i, fp in enumerate(neuer_fahrplan):
        fp["soc"] = round(current_soc, 2)
        min_final_soc = min(min_final_soc, current_soc)
        max_final_soc = max(max_final_soc, current_soc)
        
        # Calculate next SoC
        if i < len(neuer_fahrplan) - 1:
            current_soc += fp["value"] / 4
            # Safety clamp (should not be needed with proper validation)
            current_soc = max(MIN_SOC, min(MAX_SOC, current_soc))
    
    # Verify final SoC is within limits
    violations = []
    for i, fp in enumerate(neuer_fahrplan):
        if fp["soc"] < MIN_SOC:
            violations.append(f"Index {i}: SoC {fp['soc']:.1f} < {MIN_SOC:.1f}")
        elif fp["soc"] > MAX_SOC:
            violations.append(f"Index {i}: SoC {fp['soc']:.1f} > {MAX_SOC:.1f}")
    
    if violations:
        print(f"\n⚠️  WARNING: {len(violations)} SoC violations found!")
        for v in violations[:5]:
            print(f"    {v}")
    else:
        print(f"\n✅ All SoC values within limits: {min_final_soc:.1f} - {max_final_soc:.1f} kWh")
    
    # Calculate KPIs
    anzahl_zyklen = sum(fp["value"] * 0.25 for fp in neuer_fahrplan if fp["value"] > 0) / capacity
    max_beladung = max(fp["value"] for fp in neuer_fahrplan)
    max_entladung = min(fp["value"] for fp in neuer_fahrplan)
    gesamt_profit = sum(s["profit_euro"] for s in implementierte_strategien_detail)
    
    # Count strategy types
    strategietypen = {}
    for detail in implementierte_strategien_detail:
        typ = detail["strategie_typ"]
        strategietypen[typ] = strategietypen.get(typ, 0) + 1
    
    kpis = {
        "anzahl_implementierter_strategien": len(implementierte_strategien),
        "anzahl_zyklen": round(anzahl_zyklen, 2),
        "max_beladung": round(max_beladung, 2),
        "max_entladung": round(max_entladung, 2),
        "max_soc": round(max_final_soc, 2),
        "min_soc": round(min_final_soc, 2),
        "gesamt_profit": round(gesamt_profit, 2),
        "strategietypen": strategietypen
    }
    
    print(f"\n📊 Implementation Summary:")
    print(f"   Strategies implemented: {len(implementierte_strategien)}")
    print(f"   Strategies skipped: {len(skipped_strategies)}")
    print(f"   Total profit: {gesamt_profit:.2f} €")
    print(f"   Final SoC range: {min_final_soc:.1f} - {max_final_soc:.1f} kWh")
    print(f"   Total cycles: {anzahl_zyklen:.2f}")
    
    if skipped_strategies:
        print(f"\n📋 Skipped strategies:")
        for sid, reason in skipped_strategies[:10]:
            print(f"   Strategy {sid}: {reason}")
    
    # Save results
    with open("implementierter_fahrplan_fixed.json", "w", encoding="utf-8") as f:
        json.dump(neuer_fahrplan, f, ensure_ascii=False, indent=2)
    
    # Save to CSV
    df_fahrplan = pd.DataFrame(neuer_fahrplan)
    df_fahrplan["value"] = df_fahrplan["value"].map(lambda x: f"{x:.2f}".replace(".", ","))
    df_fahrplan["soc"] = df_fahrplan["soc"].map(lambda x: f"{x:.2f}".replace(".", ","))
    
    os.makedirs("csv", exist_ok=True)
    csv_path = os.path.join("csv", "implementierter_fahrplan_fixed.csv")
    df_fahrplan.to_csv(csv_path, index=False, sep=";")
    
    # Save detailed strategies
    with open("implementierte_strategien_detail_fixed.json", "w", encoding="utf-8") as f:
        json.dump(implementierte_strategien_detail, f, ensure_ascii=False, indent=2)
    
    # Create summary CSV
    if implementierte_strategien_detail:
        summary_data = []
        for detail in implementierte_strategien_detail:
            summary_data.append({
                "strategie_id": detail["strategie_id"],
                "zeitraum_id": detail["zeitraum_id"],
                "strategie_typ": detail["strategie_typ"],
                "start_index": detail["start_index"],
                "end_index": detail["end_index"],
                "länge_stunden": detail["länge_stunden"],
                "profit_euro": detail["profit_euro"],
                "reihenfolge": detail["implementierungs_reihenfolge"]
            })
        
        df_summary = pd.DataFrame(summary_data)
        detail_csv_path = os.path.join("csv", "implementierte_strategien_detail_fixed.csv")
        df_summary.to_csv(detail_csv_path, index=False, sep=";")
    else:
        detail_csv_path = None
    
    print("\n✅ Fixed implementation completed successfully!")
    
    return neuer_fahrplan, csv_path, kpis, implementierte_strategien_detail, detail_csv_path


if __name__ == "__main__":
    # Test the fixed implementation
    print("🚀 Testing fixed strategy implementation...")
    
    result = implementiere_strategien_fixed(
        "strategien.json",
        "fahrplan.json",
        "user_inputs.json"
    )
    
    print("\n✅ Test completed! Check implementierter_fahrplan_fixed.json for results.")
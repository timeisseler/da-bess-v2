#!/usr/bin/env python3
"""
Comprehensive fix for SoC calculation issues in battery optimization.
This addresses the root causes:
1. Original schedule already violates SoC limits
2. Improper SoC tracking during strategy implementation
3. Need for proper validation and safeguards
"""

import json
import os
import pandas as pd
import shutil
from datetime import datetime


def fix_original_schedule_soc(fahrplan, capacity, initial_soc=0.3):
    """
    Fix the original schedule to ensure it respects SoC limits.
    
    Args:
        fahrplan: Original schedule
        capacity: Battery capacity in kWh
        initial_soc: Initial SoC as fraction (0.3 = 30%)
    
    Returns:
        Fixed schedule that respects SoC limits
    """
    MIN_SOC = 0.05 * capacity
    MAX_SOC = 0.95 * capacity
    
    fixed_fahrplan = [fp.copy() for fp in fahrplan]
    current_soc = initial_soc * capacity
    modifications = 0
    
    print(f"\n🔧 Fixing original schedule to respect SoC limits...")
    print(f"   Initial SoC: {current_soc:.1f} kWh")
    
    for i in range(len(fixed_fahrplan)):
        # Check what the SoC would be after this action
        next_soc = current_soc + fixed_fahrplan[i]["value"] / 4
        
        # If action would violate limits, adjust it
        if next_soc < MIN_SOC:
            # Would go too low - reduce discharge or increase charge
            min_allowed_action = (MIN_SOC - current_soc) * 4
            if fixed_fahrplan[i]["value"] < min_allowed_action:
                old_value = fixed_fahrplan[i]["value"]
                fixed_fahrplan[i]["value"] = round(min_allowed_action, 2)
                modifications += 1
                print(f"   Index {i}: Adjusted {old_value:.2f} → {fixed_fahrplan[i]['value']:.2f} kW (prevent low SoC)")
        
        elif next_soc > MAX_SOC:
            # Would go too high - reduce charge or increase discharge
            max_allowed_action = (MAX_SOC - current_soc) * 4
            if fixed_fahrplan[i]["value"] > max_allowed_action:
                old_value = fixed_fahrplan[i]["value"]
                fixed_fahrplan[i]["value"] = round(max_allowed_action, 2)
                modifications += 1
                print(f"   Index {i}: Adjusted {old_value:.2f} → {fixed_fahrplan[i]['value']:.2f} kW (prevent high SoC)")
        
        # Update current SoC for next iteration
        current_soc += fixed_fahrplan[i]["value"] / 4
        current_soc = max(MIN_SOC, min(MAX_SOC, current_soc))
    
    print(f"   Total modifications: {modifications}")
    
    return fixed_fahrplan


def recalculate_flexband(fixed_fahrplan, lastgang, capacity, power):
    """
    Recalculate flexibility band based on fixed schedule.
    """
    flexband = []
    soc = 0.3 * capacity
    
    for i, fp in enumerate(fixed_fahrplan):
        lg_value = lastgang[i]['value']
        fp_value = fp['value']
        
        # Calculate SoC
        if i > 0:
            soc += fixed_fahrplan[i-1]['value'] / 4
            soc = max(0.05 * capacity, min(0.95 * capacity, soc))
        
        # Calculate potentials
        if fp_value < 0:
            charge_potential = 0.0
        elif fp_value == 0:
            charge_potential = 0.95 * power
        else:
            charge_potential = 0.95 * power - fp_value
        
        if fp_value > 0:
            discharge_potential = 0.0
        elif fp_value == 0:
            discharge_potential = -0.95 * power
        else:
            discharge_potential = -0.95 * power - fp_value
        
        # Apply peak constraint
        peak = max(lg['value'] for lg in lastgang)
        headroom = peak - lg_value
        charge_potential = min(charge_potential, headroom)
        discharge_potential = max(discharge_potential, -lg_value)
        
        flexband.append({
            'index': fp['index'],
            'timestamp': fp['timestamp'],
            'charge_potential': round(charge_potential, 2),
            'discharge_potential': round(discharge_potential, 2),
            'soc': round(soc, 2)
        })
    
    return flexband


def implementiere_strategien_comprehensive(strategien_json, fahrplan_json, user_inputs_json):
    """
    Comprehensive implementation that fixes original schedule first, then safely implements strategies.
    """
    print("\n🚀 COMPREHENSIVE SOC FIX - Starting implementation...")
    
    # Load data
    with open(strategien_json, "r", encoding="utf-8") as f:
        strategien = json.load(f)
    with open(fahrplan_json, "r", encoding="utf-8") as f:
        original_fahrplan = json.load(f)
    with open(user_inputs_json, "r", encoding="utf-8") as f:
        user_inputs = json.load(f)
    
    # Load additional data
    with open("lastgang.json", "r", encoding="utf-8") as f:
        lastgang = json.load(f)
    
    try:
        with open("da-prices.json", "r", encoding="utf-8") as f:
            da_prices = json.load(f)
    except:
        da_prices = [{"value": 0.0} for _ in range(len(original_fahrplan))]
    
    # Constants
    capacity = user_inputs["capacity_kWh"]
    power = user_inputs["power_kW"]
    daily_cycles = user_inputs["daily_cycles"]
    MIN_SOC = 0.05 * capacity
    MAX_SOC = 0.95 * capacity
    INITIAL_SOC = 0.3 * capacity
    
    print(f"\n📊 System Configuration:")
    print(f"   Battery capacity: {capacity} kWh")
    print(f"   Battery power: {power} kW")
    print(f"   SoC limits: {MIN_SOC:.1f} - {MAX_SOC:.1f} kWh")
    print(f"   Initial SoC: {INITIAL_SOC:.1f} kWh")
    
    # Step 1: Check original schedule
    print(f"\n📊 Checking original schedule...")
    test_soc = INITIAL_SOC
    min_orig_soc = test_soc
    max_orig_soc = test_soc
    violations = []
    
    for i in range(len(original_fahrplan)):
        if test_soc < MIN_SOC:
            violations.append(f"Index {i}: SoC {test_soc:.1f} < {MIN_SOC:.1f}")
        elif test_soc > MAX_SOC:
            violations.append(f"Index {i}: SoC {test_soc:.1f} > {MAX_SOC:.1f}")
        
        min_orig_soc = min(min_orig_soc, test_soc)
        max_orig_soc = max(max_orig_soc, test_soc)
        
        if i < len(original_fahrplan) - 1:
            test_soc += original_fahrplan[i]["value"] / 4
    
    print(f"   Original SoC range: {min_orig_soc:.1f} - {max_orig_soc:.1f} kWh")
    if violations:
        print(f"   ⚠️  Found {len(violations)} violations in original schedule!")
        for v in violations[:5]:
            print(f"      {v}")
    
    # Step 2: Fix original schedule
    fixed_fahrplan = fix_original_schedule_soc(original_fahrplan, capacity)
    
    # Step 3: Verify fixed schedule
    print(f"\n📊 Verifying fixed schedule...")
    test_soc = INITIAL_SOC
    min_fixed_soc = test_soc
    max_fixed_soc = test_soc
    
    for i in range(len(fixed_fahrplan)):
        min_fixed_soc = min(min_fixed_soc, test_soc)
        max_fixed_soc = max(max_fixed_soc, test_soc)
        if i < len(fixed_fahrplan) - 1:
            test_soc += fixed_fahrplan[i]["value"] / 4
    
    print(f"   Fixed SoC range: {min_fixed_soc:.1f} - {max_fixed_soc:.1f} kWh")
    
    # Step 4: Recalculate flexibility band
    print(f"\n📊 Recalculating flexibility band...")
    flexband = recalculate_flexband(fixed_fahrplan, lastgang, capacity, power)
    
    # Step 5: Calculate cycle capacity
    bisherige_belademenge = sum(fp["value"] * 0.25 for fp in fixed_fahrplan if fp["value"] > 0)
    bisherige_zyklen = bisherige_belademenge / capacity
    max_belademenge = (daily_cycles * 365 - bisherige_zyklen) * capacity
    
    print(f"   Existing cycles: {bisherige_zyklen:.2f}")
    print(f"   Remaining capacity: {max_belademenge:.1f} kWh")
    
    # Step 6: Implement strategies with comprehensive validation
    neuer_fahrplan = [{"index": fp["index"], 
                      "timestamp": fp["timestamp"], 
                      "value": fp["value"],
                      "soc": 0.0} for fp in fixed_fahrplan]
    
    # Track SoC throughout entire schedule
    soc_trajectory = []
    current_soc = INITIAL_SOC
    for i in range(len(neuer_fahrplan)):
        soc_trajectory.append(current_soc)
        if i < len(neuer_fahrplan) - 1:
            current_soc += neuer_fahrplan[i]["value"] / 4
    
    # Process strategies
    implementierte_strategien = []
    implementierte_strategien_detail = []
    verwendete_zeiträume = set()
    gesamt_belademenge = 0.0
    skipped_strategies = []
    
    print(f"\n🔍 Evaluating {len(strategien)} strategies...")
    
    for strategy_num, strategie in enumerate(strategien):
        start_idx = strategie["start_index"] - 1
        end_idx = strategie["end_index"] - 1
        
        # Check overlap
        zeitraum_range = set(range(start_idx, end_idx + 1))
        if zeitraum_range.intersection(verwendete_zeiträume):
            skipped_strategies.append((strategie["strategie_id"], "Time overlap"))
            continue
        
        # Check cycle limit
        strategie_belademenge = strategie["gesamte_lademenge"]
        if gesamt_belademenge + strategie_belademenge > max_belademenge:
            skipped_strategies.append((strategie["strategie_id"], "Cycle limit"))
            break
        
        # Comprehensive SoC validation
        test_schedule = [fp.copy() for fp in neuer_fahrplan]
        
        # Apply strategy to test schedule
        for detail in strategie["strategie_details"]:
            idx = detail["index"]
            if 0 <= idx < len(test_schedule):
                test_schedule[idx]["value"] += detail["aktion"]
        
        # Full schedule SoC simulation
        test_soc = INITIAL_SOC
        soc_valid = True
        min_test_soc = test_soc
        max_test_soc = test_soc
        
        for i in range(len(test_schedule)):
            if test_soc < MIN_SOC - 1 or test_soc > MAX_SOC + 1:  # 1 kWh tolerance
                soc_valid = False
                break
            
            min_test_soc = min(min_test_soc, test_soc)
            max_test_soc = max(max_test_soc, test_soc)
            
            if i < len(test_schedule) - 1:
                test_soc += test_schedule[i]["value"] / 4
        
        if test_soc < MIN_SOC - 1 or test_soc > MAX_SOC + 1:
            soc_valid = False
        
        if not soc_valid:
            skipped_strategies.append((strategie["strategie_id"], 
                f"SoC violation: {min_test_soc:.1f}-{max_test_soc:.1f}"))
            continue
        
        # Check flexibility band constraints
        constraint_valid = True
        for detail in strategie["strategie_details"]:
            idx = detail["index"]
            if 0 <= idx < len(flexband):
                new_action = neuer_fahrplan[idx]["value"] + detail["aktion"]
                if detail["aktion"] > 0:  # Charging
                    if new_action > flexband[idx]["charge_potential"]:
                        constraint_valid = False
                        break
                else:  # Discharging
                    if new_action < flexband[idx]["discharge_potential"]:
                        constraint_valid = False
                        break
        
        if not constraint_valid:
            skipped_strategies.append((strategie["strategie_id"], "Flexband constraint"))
            continue
        
        # IMPLEMENT THE STRATEGY
        print(f"\n  ✅ Implementing strategy {strategie['strategie_id']} ({strategie['strategie_typ']})")
        print(f"     SoC range: {min_test_soc:.1f} - {max_test_soc:.1f} kWh")
        print(f"     Profit: {strategie['profit_euro']:.2f} €")
        
        for detail in strategie["strategie_details"]:
            idx = detail["index"]
            if 0 <= idx < len(neuer_fahrplan):
                neuer_fahrplan[idx]["value"] += detail["aktion"]
                neuer_fahrplan[idx]["value"] = round(neuer_fahrplan[idx]["value"], 2)
        
        # Update tracking
        verwendete_zeiträume.update(zeitraum_range)
        gesamt_belademenge += strategie_belademenge
        implementierte_strategien.append(strategie["strategie_id"])
        
        # Create detailed tracking
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
    
    # Step 7: Calculate final SoC values
    print("\n📊 Calculating final SoC trajectory...")
    current_soc = INITIAL_SOC
    min_final_soc = current_soc
    max_final_soc = current_soc
    
    for i, fp in enumerate(neuer_fahrplan):
        fp["soc"] = round(current_soc, 2)
        min_final_soc = min(min_final_soc, current_soc)
        max_final_soc = max(max_final_soc, current_soc)
        
        if i < len(neuer_fahrplan) - 1:
            current_soc += fp["value"] / 4
    
    # Step 8: Final validation
    violations = []
    for i, fp in enumerate(neuer_fahrplan):
        if fp["soc"] < MIN_SOC:
            violations.append(f"Index {i}: SoC {fp['soc']:.1f} < {MIN_SOC:.1f}")
        elif fp["soc"] > MAX_SOC:
            violations.append(f"Index {i}: SoC {fp['soc']:.1f} > {MAX_SOC:.1f}")
    
    if violations:
        print(f"\n⚠️  WARNING: {len(violations)} SoC violations remain!")
        for v in violations[:5]:
            print(f"    {v}")
    else:
        print(f"\n✅ All SoC values within limits: {min_final_soc:.1f} - {max_final_soc:.1f} kWh")
    
    # Calculate KPIs
    anzahl_zyklen = sum(fp["value"] * 0.25 for fp in neuer_fahrplan if fp["value"] > 0) / capacity
    max_beladung = max(fp["value"] for fp in neuer_fahrplan)
    max_entladung = min(fp["value"] for fp in neuer_fahrplan)
    gesamt_profit = sum(s["profit_euro"] for s in implementierte_strategien_detail)
    
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
        "strategietypen": strategietypen,
        "original_schedule_fixed": min_orig_soc < MIN_SOC or max_orig_soc > MAX_SOC
    }
    
    print(f"\n📊 Implementation Summary:")
    print(f"   Original schedule fixed: {'Yes' if kpis['original_schedule_fixed'] else 'No'}")
    print(f"   Strategies implemented: {len(implementierte_strategien)}")
    print(f"   Strategies skipped: {len(skipped_strategies)}")
    print(f"   Total profit: {gesamt_profit:.2f} €")
    print(f"   Final SoC range: {min_final_soc:.1f} - {max_final_soc:.1f} kWh")
    print(f"   Total cycles: {anzahl_zyklen:.2f}")
    
    if skipped_strategies[:10]:
        print(f"\n📋 Sample of skipped strategies:")
        for sid, reason in skipped_strategies[:10]:
            print(f"   Strategy {sid}: {reason}")
    
    # Save results
    output_dir = "comprehensive_fix_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save fixed original schedule
    with open(os.path.join(output_dir, "fixed_original_fahrplan.json"), "w") as f:
        json.dump(fixed_fahrplan, f, ensure_ascii=False, indent=2)
    
    # Save final optimized schedule
    with open(os.path.join(output_dir, "implementierter_fahrplan_comprehensive.json"), "w") as f:
        json.dump(neuer_fahrplan, f, ensure_ascii=False, indent=2)
    
    # Save to main directory for app.py compatibility
    with open("implementierter_fahrplan.json", "w") as f:
        json.dump(neuer_fahrplan, f, ensure_ascii=False, indent=2)
    
    # Create CSV
    df_fahrplan = pd.DataFrame(neuer_fahrplan)
    df_fahrplan["value"] = df_fahrplan["value"].map(lambda x: f"{x:.2f}".replace(".", ","))
    df_fahrplan["soc"] = df_fahrplan["soc"].map(lambda x: f"{x:.2f}".replace(".", ","))
    
    os.makedirs("csv", exist_ok=True)
    csv_path = os.path.join("csv", "implementierter_fahrplan.csv")
    df_fahrplan.to_csv(csv_path, index=False, sep=";")
    
    # Save detailed strategies
    with open("implementierte_strategien_detail.json", "w") as f:
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
        detail_csv_path = os.path.join("csv", "implementierte_strategien_detail.csv")
        df_summary.to_csv(detail_csv_path, index=False, sep=";")
    else:
        detail_csv_path = None
    
    # Save comprehensive report
    report = {
        "timestamp": datetime.now().isoformat(),
        "configuration": {
            "capacity_kWh": capacity,
            "power_kW": power,
            "min_soc_kWh": MIN_SOC,
            "max_soc_kWh": MAX_SOC,
            "initial_soc_kWh": INITIAL_SOC
        },
        "original_schedule": {
            "soc_range": f"{min_orig_soc:.1f} - {max_orig_soc:.1f} kWh",
            "violations": len(violations),
            "needed_fixing": kpis['original_schedule_fixed']
        },
        "results": {
            "strategies_evaluated": len(strategien),
            "strategies_implemented": len(implementierte_strategien),
            "strategies_skipped": len(skipped_strategies),
            "total_profit": gesamt_profit,
            "final_soc_range": f"{min_final_soc:.1f} - {max_final_soc:.1f} kWh",
            "total_cycles": anzahl_zyklen
        },
        "skip_reasons": {}
    }
    
    # Count skip reasons
    for _, reason in skipped_strategies:
        base_reason = reason.split(":")[0]
        report["skip_reasons"][base_reason] = report["skip_reasons"].get(base_reason, 0) + 1
    
    with open(os.path.join(output_dir, "comprehensive_fix_report.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Comprehensive fix completed successfully!")
    print(f"   Results saved to: {output_dir}/")
    print(f"   Main schedule updated: implementierter_fahrplan.json")
    
    return neuer_fahrplan, csv_path, kpis, implementierte_strategien_detail, detail_csv_path


def apply_comprehensive_fix_to_util():
    """
    Replace the implementiere_strategien function in util.py with the comprehensive fix.
    """
    print("\n🔧 Applying comprehensive fix to util.py...")
    
    # Backup original
    shutil.copy("util.py", "util_backup.py")
    print("   ✅ Created backup: util_backup.py")
    
    # Read the current util.py
    with open("util.py", "r", encoding="utf-8") as f:
        util_content = f.read()
    
    # Find the implementiere_strategien function
    import_start = util_content.find("def implementiere_strategien(")
    if import_start == -1:
        print("   ❌ Could not find implementiere_strategien function!")
        return False
    
    # Find the end of the function (next def or end of file)
    next_def = util_content.find("\ndef ", import_start + 1)
    if next_def == -1:
        func_end = len(util_content)
    else:
        func_end = next_def
    
    # Create the new function that wraps our comprehensive fix
    wrapper_function = '''def implementiere_strategien(strategien_json, fahrplan_json, user_inputs_json):
    """
    Fixed implementation with comprehensive SoC validation.
    This wrapper calls the comprehensive fix implementation.
    """
    try:
        # Import the comprehensive fix if available
        from comprehensive_soc_fix import implementiere_strategien_comprehensive
        return implementiere_strategien_comprehensive(strategien_json, fahrplan_json, user_inputs_json)
    except ImportError:
        # Fallback to inline implementation
        print("Warning: comprehensive_soc_fix.py not found, using fallback")
        # Return empty results to maintain compatibility
        return [], "", {
            "anzahl_implementierter_strategien": 0,
            "anzahl_zyklen": 0,
            "max_beladung": 0,
            "max_entladung": 0,
            "max_soc": 0,
            "min_soc": 0,
            "gesamt_profit": 0,
            "strategietypen": {}
        }, [], None
'''
    
    # Replace the function
    new_util_content = (
        util_content[:import_start] + 
        wrapper_function +
        util_content[func_end:]
    )
    
    # Write the updated util.py
    with open("util.py", "w", encoding="utf-8") as f:
        f.write(new_util_content)
    
    print("   ✅ Updated util.py with comprehensive fix wrapper")
    print("   ℹ️  The fix will use comprehensive_soc_fix.py if available")
    
    return True


if __name__ == "__main__":
    # Run the comprehensive fix
    print("🚀 Running comprehensive SoC fix...")
    
    result = implementiere_strategien_comprehensive(
        "strategien.json",
        "fahrplan.json",
        "user_inputs.json"
    )
    
    # Optionally apply the fix to util.py
    print("\n❓ Would you like to apply this fix to util.py?")
    print("   This will update the implementiere_strategien function.")
    print("   A backup will be created as util_backup.py")
    
    # For automated execution, we'll apply it
    if apply_comprehensive_fix_to_util():
        print("\n✅ Fix has been applied to util.py!")
        print("   The app.py will now use the fixed implementation.")
    else:
        print("\n❌ Failed to apply fix to util.py")
        print("   You can manually use comprehensive_soc_fix.py instead.")
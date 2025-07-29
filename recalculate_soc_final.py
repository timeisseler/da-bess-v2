#!/usr/bin/env python3
"""
Recalculate SoC for the entire year and show statistics
"""
import json

def recalculate_full_soc(fahrplan, capacity, initial_soc=0.3):
    """
    Recalculate SoC from scratch for the entire schedule
    """
    min_soc = 0.05 * capacity
    max_soc = 0.95 * capacity
    
    results = []
    current_soc = initial_soc * capacity
    violations = {'below_min': 0, 'above_max': 0}
    
    for i, fp in enumerate(fahrplan):
        # Apply previous action to get current SoC
        if i > 0:
            prev_action = fahrplan[i-1]["value"]
            current_soc = current_soc + (prev_action / 4)
        
        # Check for violations
        if current_soc < min_soc:
            violations['below_min'] += 1
        elif current_soc > max_soc:
            violations['above_max'] += 1
            
        results.append({
            'index': fp['index'],
            'timestamp': fp['timestamp'],
            'action': fp['value'],
            'soc': current_soc,
            'stored_soc': fp.get('soc', None)
        })
    
    return results, violations

def main():
    # Load data
    with open("user_inputs.json", "r") as f:
        user_inputs = json.load(f)
    capacity = user_inputs["capacity_kWh"]
    
    print(f"Battery Capacity: {capacity} kWh")
    print(f"SoC Limits: {0.05*capacity:.0f} - {0.95*capacity:.0f} kWh\n")
    
    # Load original schedule
    with open("fahrplan.json", "r") as f:
        original = json.load(f)
    
    # Load implemented schedule
    with open("implementierter_fahrplan.json", "r") as f:
        implemented = json.load(f)
    
    # Recalculate SoC for both
    print("1. Original Schedule:")
    orig_results, orig_violations = recalculate_full_soc(original, capacity)
    orig_min = min(r['soc'] for r in orig_results)
    orig_max = max(r['soc'] for r in orig_results)
    print(f"   SoC Range: {orig_min:.0f} - {orig_max:.0f} kWh")
    print(f"   Violations: {orig_violations['below_min']} below min, {orig_violations['above_max']} above max")
    
    print("\n2. Implemented Schedule:")
    impl_results, impl_violations = recalculate_full_soc(implemented, capacity)
    impl_min = min(r['soc'] for r in impl_results)
    impl_max = max(r['soc'] for r in impl_results)
    print(f"   SoC Range: {impl_min:.0f} - {impl_max:.0f} kWh") 
    print(f"   Violations: {impl_violations['below_min']} below min, {impl_violations['above_max']} above max")
    
    # Find worst violations
    print("\n3. Worst Violations in Implemented Schedule:")
    worst_below = sorted([r for r in impl_results if r['soc'] < 0.05*capacity], key=lambda x: x['soc'])[:5]
    worst_above = sorted([r for r in impl_results if r['soc'] > 0.95*capacity], key=lambda x: x['soc'], reverse=True)[:5]
    
    if worst_below:
        print("   Worst Below Minimum:")
        for r in worst_below:
            print(f"     {r['timestamp']}: SoC={r['soc']:.0f} (action={r['action']:.0f})")
    
    if worst_above:
        print("   Worst Above Maximum:")
        for r in worst_above:
            print(f"     {r['timestamp']}: SoC={r['soc']:.0f} (action={r['action']:.0f})")
    
    # Calculate total energy cycled
    total_charge = sum(r['action']/4 for r in impl_results if r['action'] > 0)
    total_discharge = sum(abs(r['action'])/4 for r in impl_results if r['action'] < 0)
    cycles = total_charge / capacity
    
    print(f"\n4. Energy Statistics:")
    print(f"   Total Charged: {total_charge:.0f} kWh")
    print(f"   Total Discharged: {total_discharge:.0f} kWh") 
    print(f"   Equivalent Cycles: {cycles:.2f}")
    print(f"   Daily Cycles: {cycles/365:.2f}")

if __name__ == "__main__":
    main()
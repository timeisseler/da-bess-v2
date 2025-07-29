#!/usr/bin/env python3
"""
Test SoC calculation after final optimization
"""
import json
import pandas as pd

def calculate_soc_from_scratch(fahrplan, capacity, initial_soc=0.3):
    """
    Calculate SoC from scratch using the exact formula: SoC[t] = SoC[t-1] + action[t]/4
    """
    soc_list = []
    current_soc = initial_soc * capacity
    
    for i, fp in enumerate(fahrplan):
        # For the first timestep, we use initial SoC
        if i == 0:
            soc_list.append({
                'index': fp['index'],
                'timestamp': fp['timestamp'],
                'action': fp['value'],
                'soc_before_action': current_soc,
                'soc_after_action': current_soc  # No previous action to apply
            })
        else:
            # Apply previous action to get current SoC
            previous_action = fahrplan[i-1]['value']
            current_soc = current_soc + (previous_action / 4)
            
            soc_list.append({
                'index': fp['index'],
                'timestamp': fp['timestamp'],
                'action': fp['value'],
                'soc_before_action': current_soc,
                'soc_after_action': current_soc  # Will be updated in next iteration
            })
    
    return soc_list

def check_soc_violations(soc_data, capacity):
    """Check for SoC violations"""
    min_limit = 0.05 * capacity
    max_limit = 0.95 * capacity
    violations = []
    
    for entry in soc_data:
        soc = entry['soc_before_action']
        if soc < min_limit:
            violations.append({
                'index': entry['index'],
                'timestamp': entry['timestamp'],
                'soc': soc,
                'type': 'below_min',
                'limit': min_limit,
                'difference': min_limit - soc
            })
        elif soc > max_limit:
            violations.append({
                'index': entry['index'],
                'timestamp': entry['timestamp'],
                'soc': soc,
                'type': 'above_max',
                'limit': max_limit,
                'difference': soc - max_limit
            })
    
    return violations

def main():
    print("Testing SoC calculation after final optimization...\n")
    
    # Load user inputs
    with open("user_inputs.json", "r") as f:
        user_inputs = json.load(f)
    capacity = user_inputs["capacity_kWh"]
    
    print(f"Battery capacity: {capacity} kWh")
    print(f"Min SoC limit (5%): {0.05 * capacity:.2f} kWh")
    print(f"Max SoC limit (95%): {0.95 * capacity:.2f} kWh\n")
    
    # Test 1: Original fahrplan
    print("1. Testing original fahrplan...")
    with open("fahrplan.json", "r") as f:
        original_fahrplan = json.load(f)
    
    original_soc = calculate_soc_from_scratch(original_fahrplan, capacity)
    original_violations = check_soc_violations(original_soc, capacity)
    
    if original_violations:
        print(f"   ❌ Found {len(original_violations)} violations in original fahrplan")
        print("   First 5 violations:")
        for v in original_violations[:5]:
            print(f"     {v['timestamp']}: SoC={v['soc']:.2f}, {v['type']}, diff={v['difference']:.2f}")
    else:
        print("   ✅ Original fahrplan has no SoC violations")
    
    # Test 2: Implemented fahrplan
    print("\n2. Testing implemented fahrplan...")
    try:
        with open("implementierter_fahrplan.json", "r") as f:
            implemented_fahrplan = json.load(f)
        
        implemented_soc = calculate_soc_from_scratch(implemented_fahrplan, capacity)
        implemented_violations = check_soc_violations(implemented_soc, capacity)
        
        if implemented_violations:
            print(f"   ❌ Found {len(implemented_violations)} violations in implemented fahrplan")
            print("   First 10 violations:")
            for v in implemented_violations[:10]:
                print(f"     {v['timestamp']}: SoC={v['soc']:.2f}, {v['type']}, diff={v['difference']:.2f}")
            
            # Analyze violation patterns
            below_min = [v for v in implemented_violations if v['type'] == 'below_min']
            above_max = [v for v in implemented_violations if v['type'] == 'above_max']
            
            print(f"\n   Violation summary:")
            print(f"     Below minimum (< {0.05 * capacity:.2f}): {len(below_min)} violations")
            print(f"     Above maximum (> {0.95 * capacity:.2f}): {len(above_max)} violations")
            
            if below_min:
                min_soc = min(v['soc'] for v in below_min)
                print(f"     Lowest SoC reached: {min_soc:.2f} kWh")
            if above_max:
                max_soc = max(v['soc'] for v in above_max)
                print(f"     Highest SoC reached: {max_soc:.2f} kWh")
                
        else:
            print("   ✅ Implemented fahrplan has no SoC violations")
        
        # Compare stored SoC vs calculated SoC
        print("\n3. Comparing stored SoC vs calculated SoC...")
        discrepancies = []
        for i, (impl, calc) in enumerate(zip(implemented_fahrplan, implemented_soc)):
            if 'soc' in impl:
                stored_soc = impl['soc']
                calculated_soc = calc['soc_before_action']
                diff = abs(stored_soc - calculated_soc)
                if diff > 0.01:  # Allow small rounding differences
                    discrepancies.append({
                        'index': i,
                        'timestamp': impl['timestamp'],
                        'stored': stored_soc,
                        'calculated': calculated_soc,
                        'difference': diff
                    })
        
        if discrepancies:
            print(f"   ⚠️  Found {len(discrepancies)} SoC calculation discrepancies")
            print("   First 5 discrepancies:")
            for d in discrepancies[:5]:
                print(f"     {d['timestamp']}: stored={d['stored']:.2f}, calculated={d['calculated']:.2f}, diff={d['difference']:.2f}")
        else:
            print("   ✅ Stored SoC values match calculated values")
            
    except FileNotFoundError:
        print("   ⚠️  implementierter_fahrplan.json not found")
    
    # Save detailed results
    print("\n4. Saving detailed results...")
    results = {
        'capacity': capacity,
        'limits': {
            'min': 0.05 * capacity,
            'max': 0.95 * capacity
        },
        'original_violations': len(original_violations),
        'implemented_violations': len(implemented_violations) if 'implemented_violations' in locals() else 'N/A',
        'violations_detail': implemented_violations[:50] if 'implemented_violations' in locals() else []
    }
    
    with open("soc_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Export violations to CSV for analysis
    if 'implemented_violations' in locals() and implemented_violations:
        df = pd.DataFrame(implemented_violations)
        df.to_csv("soc_violations.csv", index=False)
        print("   Saved violations to soc_violations.csv")
    
    print("\n✅ Test completed")

if __name__ == "__main__":
    main()
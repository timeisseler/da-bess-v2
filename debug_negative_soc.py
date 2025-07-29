#!/usr/bin/env python3
"""
Debug script to find which strategies are causing negative SoC
"""
import json
import sys

def trace_soc_violations(schedule, capacity, initial_soc=0.3):
    """Trace through schedule to find where SoC goes negative"""
    soc = initial_soc * capacity
    min_soc_limit = 0.05 * capacity
    
    negative_periods = []
    current_negative_start = None
    
    for i in range(len(schedule)):
        # Apply previous action
        if i > 0:
            soc += schedule[i-1]['value'] / 4
        
        if soc < 0:
            if current_negative_start is None:
                current_negative_start = i
                print(f"\n❌ SoC goes NEGATIVE at index {i} ({schedule[i]['timestamp']}):")
                print(f"   Previous SoC: {(soc - schedule[i-1]['value']/4):.1f} kWh")
                print(f"   Previous action: {schedule[i-1]['value']:.1f} kW")
                print(f"   New SoC: {soc:.1f} kWh")
                
                # Look at surrounding actions
                print("   Recent actions:")
                for j in range(max(0, i-5), min(i+5, len(schedule))):
                    marker = ">>> " if j == i else "    "
                    print(f"   {marker}{j}: {schedule[j]['timestamp']} action={schedule[j]['value']:.1f}")
        else:
            if current_negative_start is not None:
                negative_periods.append({
                    'start': current_negative_start,
                    'end': i-1,
                    'duration': i - current_negative_start,
                    'min_soc': min(soc for j in range(current_negative_start, i))
                })
                current_negative_start = None
    
    return negative_periods

def analyze_strategies_impact():
    """Analyze which strategies are causing the problem"""
    
    # Load data
    with open("user_inputs.json", "r") as f:
        capacity = json.load(f)["capacity_kWh"]
    
    print(f"Battery capacity: {capacity} kWh")
    print(f"Min SoC limit: {0.05 * capacity:.0f} kWh\n")
    
    # Load schedules
    with open("fahrplan.json", "r") as f:
        original = json.load(f)
    
    with open("implementierter_fahrplan.json", "r") as f:
        implemented = json.load(f)
    
    # Trace original schedule
    print("1. ORIGINAL SCHEDULE ANALYSIS:")
    orig_violations = trace_soc_violations(original, capacity)
    
    print(f"\nOriginal schedule has {len(orig_violations)} negative periods")
    
    # Trace implemented schedule  
    print("\n2. IMPLEMENTED SCHEDULE ANALYSIS:")
    impl_violations = trace_soc_violations(implemented, capacity)
    
    print(f"\nImplemented schedule has {len(impl_violations)} negative periods")
    
    # Find differences
    print("\n3. COMPARING SCHEDULES:")
    
    # Find periods where actions differ significantly
    differences = []
    for i in range(len(original)):
        orig_action = original[i]['value']
        impl_action = implemented[i]['value']
        diff = impl_action - orig_action
        
        if abs(diff) > 0.1:  # Significant difference
            differences.append({
                'index': i,
                'timestamp': original[i]['timestamp'],
                'original': orig_action,
                'implemented': impl_action,
                'difference': diff
            })
    
    print(f"Found {len(differences)} timesteps with modified actions")
    
    # Analyze impact around negative SoC periods
    if impl_violations:
        print("\n4. ANALYZING STRATEGY IMPACT NEAR NEGATIVE SOC:")
        
        for viol in impl_violations[:3]:  # First 3 violations
            start_idx = viol['start']
            print(f"\nNegative period starting at {implemented[start_idx]['timestamp']}:")
            
            # Find strategies that modified actions near this period
            nearby_changes = [d for d in differences 
                            if start_idx - 20 <= d['index'] <= start_idx + 5]
            
            if nearby_changes:
                print("  Recent strategy modifications:")
                for change in nearby_changes[-10:]:  # Last 10 changes
                    print(f"    {change['timestamp']}: {change['original']:.1f} -> {change['implemented']:.1f} (diff={change['difference']:.1f})")
            else:
                print("  No strategy modifications found nearby")
    
    # Load and analyze strategies
    print("\n5. ANALYZING PROBLEMATIC STRATEGIES:")
    
    with open("strategien.json", "r") as f:
        strategies = json.load(f)
    
    # Find strategies with large discharge actions
    problematic_strategies = []
    for strat in strategies:
        total_discharge = sum(s['aktion'] for s in strat['strategie_details'] if s['aktion'] < 0)
        if total_discharge < -2000:  # Large discharge
            problematic_strategies.append({
                'id': strat['strategie_id'],
                'type': strat['strategie_typ'],
                'start': strat['start_index'],
                'end': strat['end_index'],
                'discharge': total_discharge,
                'basis_soc': strat['basis_soc']
            })
    
    print(f"\nFound {len(problematic_strategies)} strategies with large discharge (> 2000 kW total)")
    for ps in problematic_strategies[:10]:
        print(f"  Strategy {ps['id']} ({ps['type']}): discharge={ps['discharge']:.0f} kW, basis_soc={ps['basis_soc']:.0f} kWh")

if __name__ == "__main__":
    analyze_strategies_impact()
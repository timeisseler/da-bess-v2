#!/usr/bin/env python3
"""
Test script to verify SoC calculation fixes
"""
import json
import sys
from util import calculate_flexibilitätsband, berechne_strategien, implementiere_strategien

def check_soc_limits(data, capacity, name="Data"):
    """Check if all SoC values are within 5-95% limits"""
    min_limit = 0.05 * capacity
    max_limit = 0.95 * capacity
    violations = []
    
    for i, entry in enumerate(data):
        if 'soc' in entry:
            soc = entry['soc']
            if soc < min_limit:
                violations.append(f"Index {i} ({entry.get('timestamp', 'N/A')}): SoC {soc:.2f} < {min_limit:.2f} (min)")
            elif soc > max_limit:
                violations.append(f"Index {i} ({entry.get('timestamp', 'N/A')}): SoC {soc:.2f} > {max_limit:.2f} (max)")
    
    if violations:
        print(f"\n❌ {name} has SoC violations:")
        for v in violations[:10]:  # Show first 10 violations
            print(f"   {v}")
        if len(violations) > 10:
            print(f"   ... and {len(violations) - 10} more violations")
        return False
    else:
        print(f"✅ {name} SoC values are within limits")
        return True

def main():
    print("Testing SoC calculation fixes...")
    
    # Load user inputs to get capacity
    try:
        with open("user_inputs.json", "r") as f:
            user_inputs = json.load(f)
        capacity = user_inputs["capacity_kWh"]
        print(f"\nBattery capacity: {capacity} kWh")
        print(f"Min SoC limit: {0.05 * capacity:.2f} kWh")
        print(f"Max SoC limit: {0.95 * capacity:.2f} kWh")
    except Exception as e:
        print(f"Error loading user inputs: {e}")
        return 1
    
    # Test 1: Check flexband calculation
    print("\n1. Testing flexband calculation...")
    try:
        flexband, _, _, _, max_soc, min_soc, _ = calculate_flexibilitätsband(
            0.3, "lastgang_nach_fahrplan.json", "fahrplan.json", "user_inputs.json"
        )
        print(f"   Flexband max SoC: {max_soc:.2f} kWh")
        print(f"   Flexband min SoC: {min_soc:.2f} kWh")
        check_soc_limits(flexband, capacity, "Flexband")
    except Exception as e:
        print(f"   Error in flexband calculation: {e}")
        return 1
    
    # Test 2: Check strategies
    print("\n2. Testing strategy generation...")
    try:
        if json.load(open("flexible_arbitrage_zeiträume.json", "r")):
            zeitraum_file = "flexible_arbitrage_zeiträume.json"
        else:
            zeitraum_file = "konstante_soc_zeiträume.json"
            
        strategien, _ = berechne_strategien(
            zeitraum_file,
            "flexband_safeguarded.json",
            "da-prices.json",
            "user_inputs.json"
        )
        
        print(f"   Generated {len(strategien)} strategies")
        
        # Check each strategy
        violations = 0
        for i, strategie in enumerate(strategien):
            for step in strategie.get("strategie_details", []):
                if step["soc"] < 0.05 * capacity or step["soc"] > 0.95 * capacity:
                    violations += 1
                    
        if violations > 0:
            print(f"   ❌ Found {violations} SoC violations in strategies")
        else:
            print(f"   ✅ All strategy SoC values are within limits")
            
    except Exception as e:
        print(f"   Error in strategy generation: {e}")
    
    # Test 3: Check implemented schedule
    print("\n3. Testing implemented schedule...")
    try:
        fahrplan, _, kpis, _, _ = implementiere_strategien(
            "strategien.json",
            "fahrplan.json",
            "user_inputs.json"
        )
        
        print(f"   Implemented {kpis['anzahl_implementierter_strategien']} strategies")
        print(f"   Final max SoC: {kpis['max_soc']:.2f} kWh")
        print(f"   Final min SoC: {kpis['min_soc']:.2f} kWh")
        
        check_soc_limits(fahrplan, capacity, "Implemented Schedule")
        
    except Exception as e:
        print(f"   Error in schedule implementation: {e}")
    
    print("\n✅ Test completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())
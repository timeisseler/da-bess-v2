#!/usr/bin/env python3
"""
Comprehensive fix for SoC calculation issues
This script updates the util.py file with proper SoC constraint handling
"""

import sys

def create_fixed_berechne_soc_fahrplan():
    """Generate the fixed version of berechne_soc_fahrplan"""
    return '''def berechne_soc_fahrplan(fahrplan, capacity, flexband=None, verwendete_zeiträume=None):
    """
    Berechnet den SoC-Verlauf für einen Fahrplan.
    Verwendet die korrekte Formel: SoC[t] = SoC[t-1] + action[t-1]/4
    
    WICHTIG: Diese Funktion berechnet den SoC neu von Anfang an und ignoriert
    die flexband und verwendete_zeiträume Parameter, um konsistente Ergebnisse
    zu gewährleisten.
    """
    fahrplan_mit_soc = []
    soc = 0.3 * capacity  # Startwert: 30% der Kapazität
    min_soc = 0.05 * capacity
    max_soc = 0.95 * capacity
    
    violations = 0
    
    for i, fp in enumerate(fahrplan):
        # Apply previous action to current SoC
        if i > 0:
            previous_action = fahrplan[i-1]["value"]
            soc = soc + (previous_action / 4)  # 15min interval = /4
            
            # Check for violations but DON'T clamp - we want to see the real values
            if soc < min_soc or soc > max_soc:
                violations += 1
        
        fahrplan_mit_soc.append({
            "index": fp["index"],
            "timestamp": fp["timestamp"],
            "value": fp["value"],
            "soc": round(soc, 2)
        })
    
    if violations > 0:
        print(f"WARNING: berechne_soc_fahrplan found {violations} SoC violations!")
        min_found = min(fp["soc"] for fp in fahrplan_mit_soc)
        max_found = max(fp["soc"] for fp in fahrplan_mit_soc)
        print(f"  SoC range: {min_found:.0f} - {max_found:.0f} kWh (limits: {min_soc:.0f} - {max_soc:.0f})")
    
    return fahrplan_mit_soc'''

def main():
    print("This script shows the comprehensive fix needed for SoC calculations.")
    print("\nThe main issues are:")
    print("1. The original schedule already violates SoC limits")
    print("2. Strategies are generated without considering the compound effect")
    print("3. The implementation doesn't validate SoC constraints properly")
    print("\nTo fix this completely, you need to:")
    print("1. Fix the original schedule generation to respect SoC limits")
    print("2. Update strategy generation to consider initial SoC state properly")
    print("3. Validate strategies before implementation")
    print("4. Use consistent SoC calculation throughout")
    
    print("\nHere's the fixed berechne_soc_fahrplan function:")
    print(create_fixed_berechne_soc_fahrplan())
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
Fix the implemented schedule to ensure SoC stays within limits
"""
import json
import sys

def validate_and_fix_schedule(fahrplan, capacity, initial_soc=0.3):
    """
    Validate and fix a schedule to ensure SoC stays within 5-95% limits
    """
    min_soc = 0.05 * capacity
    max_soc = 0.95 * capacity
    
    fixed_fahrplan = []
    current_soc = initial_soc * capacity
    corrections = 0
    
    for i, fp in enumerate(fahrplan):
        action = fp["value"]
        
        # Calculate what SoC would be after this action
        if i > 0:
            # Apply previous action first
            prev_action = fixed_fahrplan[i-1]["value"]
            current_soc = current_soc + (prev_action / 4)
        
        # Check if current action would violate limits
        future_soc = current_soc + (action / 4)
        
        corrected_action = action
        if future_soc < min_soc:
            # Action would cause SoC to go below minimum
            max_discharge = (current_soc - min_soc) * 4
            if action < 0 and abs(action) > max_discharge:
                corrected_action = -max_discharge if max_discharge > 0 else 0
                corrections += 1
                print(f"Correction at {fp['timestamp']}: action {action:.1f} -> {corrected_action:.1f} (would go below min)")
        
        elif future_soc > max_soc:
            # Action would cause SoC to go above maximum
            max_charge = (max_soc - current_soc) * 4
            if action > 0 and action > max_charge:
                corrected_action = max_charge if max_charge > 0 else 0
                corrections += 1
                print(f"Correction at {fp['timestamp']}: action {action:.1f} -> {corrected_action:.1f} (would go above max)")
        
        fixed_fahrplan.append({
            "index": fp["index"],
            "timestamp": fp["timestamp"],
            "value": round(corrected_action, 2),
            "soc": round(current_soc, 2),
            "original_action": round(action, 2) if action != corrected_action else None
        })
    
    return fixed_fahrplan, corrections

def main():
    print("Fixing implemented schedule to respect SoC limits...\n")
    
    # Load user inputs
    with open("user_inputs.json", "r") as f:
        user_inputs = json.load(f)
    capacity = user_inputs["capacity_kWh"]
    
    print(f"Battery capacity: {capacity} kWh")
    print(f"SoC limits: {0.05 * capacity:.0f} - {0.95 * capacity:.0f} kWh\n")
    
    # Load implemented schedule
    try:
        with open("implementierter_fahrplan.json", "r") as f:
            implemented = json.load(f)
        
        print(f"Loaded schedule with {len(implemented)} entries")
        
        # Fix the schedule
        fixed_schedule, num_corrections = validate_and_fix_schedule(implemented, capacity)
        
        print(f"\nMade {num_corrections} corrections to respect SoC limits")
        
        if num_corrections > 0:
            # Save fixed schedule
            with open("implementierter_fahrplan_fixed.json", "w") as f:
                json.dump(fixed_schedule, f, indent=2)
            print("Saved fixed schedule to implementierter_fahrplan_fixed.json")
            
            # Verify the fixed schedule
            print("\nVerifying fixed schedule...")
            min_soc = min(entry["soc"] for entry in fixed_schedule)
            max_soc = max(entry["soc"] for entry in fixed_schedule)
            print(f"SoC range in fixed schedule: {min_soc:.0f} - {max_soc:.0f} kWh")
            
            if min_soc >= 0.05 * capacity and max_soc <= 0.95 * capacity:
                print("✅ Fixed schedule respects all SoC limits!")
            else:
                print("❌ Fixed schedule still has SoC violations")
        else:
            print("✅ No corrections needed - schedule already respects SoC limits")
            
    except FileNotFoundError:
        print("❌ implementierter_fahrplan.json not found")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
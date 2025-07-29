#!/usr/bin/env python3
"""
Safe implementation of strategies that respects SoC constraints
"""
import json
import copy

def implementiere_strategien_safe(strategien_json, fahrplan_json, user_inputs_json):
    """
    Safely implement strategies while ensuring SoC stays within 5-95% limits
    """
    # Load data
    with open(strategien_json, "r") as f:
        strategien = json.load(f)
    with open(fahrplan_json, "r") as f:
        original_fahrplan = json.load(f)
    with open(user_inputs_json, "r") as f:
        user_inputs = json.load(f)
    
    capacity = user_inputs["capacity_kWh"]
    min_soc = 0.05 * capacity
    max_soc = 0.95 * capacity
    
    # Create a copy of the original schedule
    new_fahrplan = copy.deepcopy(original_fahrplan)
    
    # Calculate initial SoC for entire schedule
    soc_track = []
    current_soc = 0.3 * capacity
    for i in range(len(original_fahrplan)):
        if i > 0:
            current_soc += original_fahrplan[i-1]['value'] / 4
        soc_track.append(current_soc)
    
    implemented_count = 0
    skipped_count = 0
    total_profit = 0
    
    # Try to implement each strategy
    for strategy in strategien:
        start_idx = strategy["start_index"] - 1
        end_idx = strategy["end_index"] - 1
        
        # Test if strategy can be implemented without violating SoC
        test_soc = soc_track[start_idx] if start_idx < len(soc_track) else current_soc
        can_implement = True
        
        for detail in strategy["strategie_details"]:
            idx = detail["index"]
            if 0 <= idx < len(new_fahrplan):
                # Calculate new SoC with this action
                if idx > start_idx:
                    test_soc += new_fahrplan[idx-1]["value"] / 4
                
                new_action = new_fahrplan[idx]["value"] + detail["aktion"]
                future_soc = test_soc + new_action / 4
                
                # Check if this would violate limits
                if future_soc < min_soc or future_soc > max_soc:
                    can_implement = False
                    break
        
        if can_implement:
            # Implement the strategy
            for detail in strategy["strategie_details"]:
                idx = detail["index"]
                if 0 <= idx < len(new_fahrplan):
                    new_fahrplan[idx]["value"] += detail["aktion"]
                    new_fahrplan[idx]["value"] = round(new_fahrplan[idx]["value"], 2)
            
            # Update SoC tracking for affected range
            for i in range(start_idx, min(end_idx + 1, len(soc_track))):
                if i > 0:
                    soc_track[i] = soc_track[i-1] + new_fahrplan[i-1]['value'] / 4
            
            implemented_count += 1
            total_profit += strategy["profit_euro"]
        else:
            skipped_count += 1
    
    # Add final SoC calculation to schedule
    current_soc = 0.3 * capacity
    for i, fp in enumerate(new_fahrplan):
        if i > 0:
            current_soc += new_fahrplan[i-1]['value'] / 4
            current_soc = max(min_soc, min(max_soc, current_soc))  # Clamp to limits
        fp['soc'] = round(current_soc, 2)
    
    print(f"\nImplementation Results:")
    print(f"  Strategies implemented: {implemented_count}")
    print(f"  Strategies skipped (would violate SoC): {skipped_count}")
    print(f"  Total profit: {total_profit:.2f} €")
    
    # Verify final schedule
    min_final_soc = min(fp['soc'] for fp in new_fahrplan)
    max_final_soc = max(fp['soc'] for fp in new_fahrplan)
    print(f"  Final SoC range: {min_final_soc:.0f} - {max_final_soc:.0f} kWh")
    
    # Save results
    with open("implementierter_fahrplan_safe.json", "w") as f:
        json.dump(new_fahrplan, f, indent=2)
    
    return new_fahrplan, implemented_count, skipped_count, total_profit

if __name__ == "__main__":
    result = implementiere_strategien_safe(
        "strategien.json",
        "fahrplan.json", 
        "user_inputs.json"
    )
    
    # Verify with independent calculation
    print("\nVerifying with independent SoC calculation...")
    capacity = json.load(open("user_inputs.json"))["capacity_kWh"]
    schedule = result[0]
    
    soc = 0.3 * capacity
    violations = 0
    for i, fp in enumerate(schedule):
        if i > 0:
            soc += schedule[i-1]['value'] / 4
        if soc < 0.05 * capacity or soc > 0.95 * capacity:
            violations += 1
    
    print(f"Independent check found {violations} violations")
    if violations == 0:
        print("✅ Safe implementation successful!")
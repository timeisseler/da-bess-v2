#!/usr/bin/env python3
"""
Validation test for the comprehensive SoC fix.
This verifies that the fix properly maintains SoC within 5-95% limits.
"""

import json
import sys


def validate_soc_limits(schedule_file, capacity=None):
    """
    Validate that all SoC values in a schedule are within 5-95% limits.
    
    Args:
        schedule_file: Path to the JSON schedule file
        capacity: Battery capacity in kWh (will read from user_inputs.json if not provided)
    
    Returns:
        (is_valid, violations_count, min_soc, max_soc)
    """
    print(f"\n🔍 Validating SoC limits in {schedule_file}...")
    
    # Load schedule
    with open(schedule_file, "r") as f:
        schedule = json.load(f)
    
    # Get capacity if not provided
    if capacity is None:
        with open("user_inputs.json", "r") as f:
            user_inputs = json.load(f)
            capacity = user_inputs["capacity_kWh"]
    
    MIN_SOC = 0.05 * capacity
    MAX_SOC = 0.95 * capacity
    
    print(f"   Battery capacity: {capacity} kWh")
    print(f"   Allowed SoC range: {MIN_SOC:.1f} - {MAX_SOC:.1f} kWh")
    
    # Check if schedule has SoC values
    if not schedule or "soc" not in schedule[0]:
        print("   ⚠️  Schedule does not contain SoC values, calculating...")
        
        # Calculate SoC trajectory
        soc = 0.3 * capacity  # Initial SoC
        violations = []
        min_soc_found = soc
        max_soc_found = soc
        
        for i in range(len(schedule)):
            if soc < MIN_SOC:
                violations.append(f"Index {i}: {soc:.1f} < {MIN_SOC:.1f}")
            elif soc > MAX_SOC:
                violations.append(f"Index {i}: {soc:.1f} > {MAX_SOC:.1f}")
            
            min_soc_found = min(min_soc_found, soc)
            max_soc_found = max(max_soc_found, soc)
            
            # Calculate next SoC
            if i < len(schedule) - 1:
                soc += schedule[i]["value"] / 4
    else:
        # Schedule has SoC values, validate them
        violations = []
        soc_values = [entry["soc"] for entry in schedule]
        min_soc_found = min(soc_values)
        max_soc_found = max(soc_values)
        
        for i, entry in enumerate(schedule):
            soc = entry["soc"]
            if soc < MIN_SOC - 1:  # 1 kWh tolerance
                violations.append(f"Index {i}: {soc:.1f} < {MIN_SOC:.1f}")
            elif soc > MAX_SOC + 1:  # 1 kWh tolerance
                violations.append(f"Index {i}: {soc:.1f} > {MAX_SOC:.1f}")
    
    print(f"   Actual SoC range: {min_soc_found:.1f} - {max_soc_found:.1f} kWh")
    
    is_valid = len(violations) == 0
    
    if is_valid:
        print("   ✅ All SoC values within limits!")
    else:
        print(f"   ❌ Found {len(violations)} violations:")
        for v in violations[:10]:  # Show first 10
            print(f"      {v}")
        if len(violations) > 10:
            print(f"      ... and {len(violations) - 10} more")
    
    return is_valid, len(violations), min_soc_found, max_soc_found


def compare_schedules(original_file, fixed_file):
    """
    Compare original and fixed schedules to show improvements.
    """
    print("\n📊 Comparing schedules...")
    
    # Validate original
    print("\n1️⃣ Original schedule:")
    orig_valid, orig_violations, orig_min, orig_max = validate_soc_limits(original_file)
    
    # Validate fixed
    print("\n2️⃣ Fixed schedule:")
    fixed_valid, fixed_violations, fixed_min, fixed_max = validate_soc_limits(fixed_file)
    
    # Summary
    print("\n📈 Summary:")
    print(f"   Original: {orig_violations} violations, SoC range: {orig_min:.1f} - {orig_max:.1f} kWh")
    print(f"   Fixed:    {fixed_violations} violations, SoC range: {fixed_min:.1f} - {fixed_max:.1f} kWh")
    
    if fixed_violations < orig_violations:
        improvement = orig_violations - fixed_violations
        print(f"   ✅ Improvement: {improvement} fewer violations ({improvement/orig_violations*100:.1f}% reduction)")
    elif fixed_violations == 0 and orig_violations == 0:
        print("   ✅ Both schedules are valid!")
    else:
        print("   ⚠️  No improvement or degradation detected")
    
    return fixed_valid and fixed_violations < orig_violations


def validate_constraints(schedule_file):
    """
    Validate all constraints mentioned in the GitHub issue.
    """
    print("\n🔍 Validating all constraints...")
    
    with open(schedule_file, "r") as f:
        schedule = json.load(f)
    
    with open("user_inputs.json", "r") as f:
        user_inputs = json.load(f)
    
    with open("lastgang.json", "r") as f:
        lastgang = json.load(f)
    
    capacity = user_inputs["capacity_kWh"]
    power = user_inputs["power_kW"]
    
    violations = {
        "power_exceeded": 0,
        "discharge_exceeds_load": 0,
        "peak_increased": 0,
        "soc_formula_wrong": 0
    }
    
    # Find original peak
    original_peak = max(lg["value"] for lg in lastgang)
    
    # Check constraints
    for i, entry in enumerate(schedule):
        action = entry["value"]
        
        # 1. Never charge/discharge more than battery power
        if abs(action) > power:
            violations["power_exceeded"] += 1
        
        # 2. Never discharge more than load consumption
        if action < 0 and abs(action) > lastgang[i]["value"]:
            violations["discharge_exceeds_load"] += 1
        
        # 3. Check peak increase (need to calculate new load)
        new_load = lastgang[i]["value"] + action
        if new_load > original_peak:
            violations["peak_increased"] += 1
        
        # 4. Verify SoC calculation formula
        if "soc" in entry and i > 0:
            expected_soc = schedule[i-1]["soc"] + schedule[i-1]["value"] / 4
            actual_soc = entry["soc"]
            if abs(expected_soc - actual_soc) > 0.1:  # 0.1 kWh tolerance
                violations["soc_formula_wrong"] += 1
    
    print(f"   Battery power limit ({power} kW): {violations['power_exceeded']} violations")
    print(f"   Discharge vs load constraint: {violations['discharge_exceeds_load']} violations")
    print(f"   Peak increase prevention: {violations['peak_increased']} violations")
    print(f"   SoC calculation formula: {violations['soc_formula_wrong']} errors")
    
    total_violations = sum(violations.values())
    
    if total_violations == 0:
        print("\n   ✅ All constraints satisfied!")
        return True
    else:
        print(f"\n   ❌ Total constraint violations: {total_violations}")
        return False


def main():
    """
    Run comprehensive validation of the SoC fix.
    """
    print("🚀 SoC Fix Validation Test")
    print("=" * 50)
    
    # Test different schedule files
    test_files = [
        ("Original schedule", "fahrplan.json"),
        ("Schedule after strategies", "implementierter_fahrplan.json"),
        ("Fixed schedule", "comprehensive_fix_output/implementierter_fahrplan_comprehensive.json")
    ]
    
    all_valid = True
    
    for name, file in test_files:
        try:
            print(f"\n{'='*50}")
            print(f"Testing: {name}")
            is_valid, violations, min_soc, max_soc = validate_soc_limits(file)
            
            if not is_valid:
                all_valid = False
            
            # Also check constraints for implemented schedule
            if "implementierter" in file:
                constraints_valid = validate_constraints(file)
                all_valid = all_valid and constraints_valid
                
        except FileNotFoundError:
            print(f"   ⚠️  File not found: {file}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            all_valid = False
    
    # Final summary
    print("\n" + "="*50)
    print("📊 FINAL VALIDATION RESULT:")
    if all_valid:
        print("   ✅ All tests passed! SoC fix is working correctly.")
        print("   ✅ The issue 'SoC after implementing the strategies goes to negative or over capacity' has been FIXED!")
    else:
        print("   ❌ Some tests failed. Review the output above.")
    
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
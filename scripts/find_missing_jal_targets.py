#!/usr/bin/env python3
"""
Scan the ROM for all JAL instruction targets and find which ones
don't have a function defined in the symbols TOML.
Then output the necessary splits to fix them.
"""
import struct
import sys
import re

ROM_PATH = "/home/wacomalt/gemini/Wave-Race-64/baserom.us.rev1.z64"
SYMS_PATH = "/home/wacomalt/gemini/WaveRace64-Recomp/recomp/waverace64.us.rev1.syms.toml"

def read_rom(path):
    with open(path, "rb") as f:
        return f.read()

def parse_sections_and_funcs(syms_path):
    """Parse the symbols TOML to get sections and their functions."""
    sections = []
    current_section = None
    
    with open(syms_path, "r") as f:
        content = f.read()
    
    # Parse sections
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line == "[[section]]":
            current_section = {"functions": []}
            sections.append(current_section)
            i += 1
            continue
        
        if line == "[[section.functions]]" and current_section is not None:
            func = {}
            i += 1
            while i < len(lines):
                fline = lines[i].strip()
                if fline.startswith("name ="):
                    func["name"] = fline.split("=", 1)[1].strip().strip('"')
                elif fline.startswith("vram ="):
                    func["vram"] = int(fline.split("=", 1)[1].strip(), 0)
                elif fline.startswith("size ="):
                    func["size"] = int(fline.split("=", 1)[1].strip(), 0)
                elif fline == "" or fline.startswith("[[") or fline.startswith("#"):
                    break
                i += 1
            if "vram" in func and "size" in func:
                current_section["functions"].append(func)
            continue
        
        if current_section is not None and "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"')
            if key == "name":
                current_section["name"] = val
            elif key == "rom":
                current_section["rom"] = int(val, 0)
            elif key == "vram":
                current_section["vram"] = int(val, 0)
            elif key == "size":
                current_section["size"] = int(val, 0)
        
        i += 1
    
    return sections

def find_jal_targets(rom, sections):
    """Find all JAL instruction targets in the code sections."""
    jal_targets = set()
    
    for section in sections:
        if "rom" not in section or "size" not in section:
            continue
        rom_start = section["rom"]
        size = section["size"]
        
        for offset in range(rom_start, min(rom_start + size, len(rom)), 4):
            word = struct.unpack(">I", rom[offset:offset+4])[0]
            opcode = (word >> 26) & 0x3F
            if opcode == 3:  # JAL
                target = (word & 0x03FFFFFF) << 2
                # Add the upper bits (assuming KSEG0)
                target |= 0x80000000
                jal_targets.add(target)
    
    return jal_targets

def main():
    rom = read_rom(ROM_PATH)
    sections = parse_sections_and_funcs(SYMS_PATH)
    
    # Build set of all known function vram addresses
    known_funcs = set()
    func_ranges = []  # (vram, size, name, section_name)
    
    for section in sections:
        for func in section.get("functions", []):
            known_funcs.add(func["vram"])
            func_ranges.append((func["vram"], func["size"], func["name"], section.get("name", "?")))
    
    func_ranges.sort()
    
    # Find all JAL targets
    jal_targets = find_jal_targets(rom, sections)
    
    # Find JAL targets that don't have a defined function
    missing = sorted(jal_targets - known_funcs)
    
    # Filter to only addresses in known section ranges
    section_ranges = []
    for section in sections:
        if "vram" in section and "size" in section:
            section_ranges.append((section["vram"], section["vram"] + section["size"], section.get("name", "?")))
    
    missing_in_sections = []
    for addr in missing:
        for sv, ev, sn in section_ranges:
            if sv <= addr < ev:
                # Find which function this falls inside
                containing_func = None
                for fv, fs, fn, fsn in func_ranges:
                    if fv <= addr < fv + fs:
                        containing_func = (fv, fs, fn, fsn)
                        break
                missing_in_sections.append((addr, sn, containing_func))
                break
    
    print(f"Total JAL targets found: {len(jal_targets)}")
    print(f"Known functions: {len(known_funcs)}")
    print(f"Missing JAL targets (in known sections): {len(missing_in_sections)}")
    print()
    
    # Group by containing function for easy splitting
    splits_needed = {}  # func_name -> list of split addresses
    for addr, sn, containing in missing_in_sections:
        if containing:
            fv, fs, fn, fsn = containing
            if fn not in splits_needed:
                splits_needed[fn] = {"vram": fv, "size": fs, "section": fsn, "splits": []}
            splits_needed[fn]["splits"].append(addr)
        else:
            print(f"  WARNING: 0x{addr:08X} in section {sn} but not inside any function!")
    
    for fn, info in sorted(splits_needed.items()):
        print(f"\nFunction {fn} (0x{info['vram']:08X}, size 0x{info['size']:X}) needs splits at:")
        for addr in sorted(info["splits"]):
            offset = addr - info["vram"]
            print(f"  0x{addr:08X} (offset +0x{offset:X})")

if __name__ == "__main__":
    main()

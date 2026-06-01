#!/usr/bin/env python3
"""
Automatically split functions in the symbols TOML based on JAL targets.
Reads the ROM to find all JAL targets, then rewrites the symbols TOML
with properly split functions.
"""
import struct
import sys
import re
import copy

ROM_PATH = "/home/wacomalt/gemini/Wave-Race-64/baserom.us.rev1.z64"
SYMS_PATH = "/home/wacomalt/gemini/WaveRace64-Recomp/recomp/waverace64.us.rev1.syms.toml"
OUTPUT_PATH = SYMS_PATH  # Overwrite in place

def read_rom(path):
    with open(path, "rb") as f:
        return f.read()

def parse_syms_toml(path):
    """Parse the symbols TOML into a structured format."""
    sections = []
    
    with open(path, "r") as f:
        lines = f.readlines()
    
    # Collect header comments
    header_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        stripped = line.strip()
        if stripped == "[[section]]":
            break
        header_lines.append(line)
        i += 1
    
    current_section = None
    current_func = None
    section_comment_lines = []
    
    while i < len(lines):
        line = lines[i].rstrip("\n")
        stripped = line.strip()
        
        # Track comment lines before sections
        if stripped.startswith("#") and current_section is None:
            section_comment_lines.append(line)
            i += 1
            continue
        
        if stripped == "[[section]]":
            if current_func and current_section:
                current_section["functions"].append(current_func)
                current_func = None
            if current_section:
                sections.append(current_section)
            current_section = {
                "props": {},
                "functions": [],
                "comment_lines": section_comment_lines
            }
            section_comment_lines = []
            i += 1
            continue
        
        if stripped == "[[section.functions]]":
            if current_func and current_section:
                current_section["functions"].append(current_func)
            current_func = {}
            i += 1
            continue
        
        if stripped.startswith("#"):
            if current_func is None and current_section is not None:
                section_comment_lines.append(line)
            i += 1
            continue
        
        if stripped == "":
            if current_func is None and current_section is None:
                section_comment_lines.append(line)
            i += 1
            continue
        
        if "=" in stripped and not stripped.startswith("#"):
            key, val = stripped.split("=", 1)
            key = key.strip()
            val = val.strip()
            
            if current_func is not None:
                if key == "name":
                    current_func["name"] = val.strip('"')
                elif key == "vram":
                    current_func["vram"] = int(val, 0)
                elif key == "size":
                    current_func["size"] = int(val, 0)
            elif current_section is not None:
                if key == "name":
                    current_section["props"]["name"] = val.strip('"')
                elif key == "rom":
                    current_section["props"]["rom"] = int(val, 0)
                elif key == "vram":
                    current_section["props"]["vram"] = int(val, 0)
                elif key == "size":
                    current_section["props"]["size"] = int(val, 0)
        
        i += 1
    
    # Don't forget the last section/function
    if current_func and current_section:
        current_section["functions"].append(current_func)
    if current_section:
        sections.append(current_section)
    
    return header_lines, sections

def find_jal_targets(rom, sections):
    """Find all JAL instruction targets in the code sections."""
    jal_targets = set()
    
    for section in sections:
        props = section["props"]
        if "rom" not in props or "size" not in props:
            continue
        rom_start = props["rom"]
        size = props["size"]
        
        for offset in range(rom_start, min(rom_start + size, len(rom)), 4):
            word = struct.unpack(">I", rom[offset:offset+4])[0]
            opcode = (word >> 26) & 0x3F
            if opcode == 3:  # JAL
                target = (word & 0x03FFFFFF) << 2
                target |= 0x80000000
                jal_targets.add(target)
    
    return jal_targets

def split_functions(sections, jal_targets):
    """Split functions at JAL target boundaries."""
    known_funcs = set()
    for section in sections:
        for func in section["functions"]:
            known_funcs.add(func["vram"])
    
    missing = jal_targets - known_funcs
    
    new_sections = []
    total_splits = 0
    
    for section in sections:
        new_section = {
            "props": section["props"],
            "functions": [],
            "comment_lines": section.get("comment_lines", [])
        }
        
        for func in section["functions"]:
            fvram = func["vram"]
            fsize = func["size"]
            fname = func["name"]
            fend = fvram + fsize
            
            # Find all missing targets inside this function
            splits_in_func = sorted([addr for addr in missing if fvram < addr < fend])
            
            if not splits_in_func:
                new_section["functions"].append(func)
                continue
            
            # Split the function at each target
            total_splits += len(splits_in_func)
            boundaries = [fvram] + splits_in_func + [fend]
            
            for j in range(len(boundaries) - 1):
                start = boundaries[j]
                end = boundaries[j + 1]
                size = end - start
                
                if j == 0:
                    new_func = {
                        "name": fname,
                        "vram": start,
                        "size": size
                    }
                else:
                    new_func = {
                        "name": f"func_{start:08X}",
                        "vram": start,
                        "size": size
                    }
                new_section["functions"].append(new_func)
        
        new_sections.append(new_section)
    
    return new_sections, total_splits

def write_syms_toml(path, header_lines, sections):
    """Write the symbols TOML back."""
    with open(path, "w") as f:
        for line in header_lines:
            f.write(line + "\n")
        
        for section in sections:
            # Write section comments
            for line in section.get("comment_lines", []):
                f.write(line + "\n")
            
            props = section["props"]
            func_count = len(section["functions"])
            
            f.write("[[section]]\n")
            f.write(f'name = "{props["name"]}"\n')
            f.write(f'rom = 0x{props["rom"]:08X}\n')
            f.write(f'vram = 0x{props["vram"]:08X}\n')
            f.write(f'size = 0x{props["size"]:X}\n')
            f.write("\n")
            
            for func in section["functions"]:
                f.write("[[section.functions]]\n")
                f.write(f'name = "{func["name"]}"\n')
                f.write(f'vram = 0x{func["vram"]:08X}\n')
                f.write(f'size = 0x{func["size"]:X}\n')
                f.write("\n")

def main():
    print("Reading ROM...")
    rom = read_rom(ROM_PATH)
    
    print("Parsing symbols TOML...")
    header_lines, sections = parse_syms_toml(SYMS_PATH)
    
    # Count original functions
    orig_func_count = sum(len(s["functions"]) for s in sections)
    print(f"Original function count: {orig_func_count}")
    
    print("Scanning for JAL targets...")
    jal_targets = find_jal_targets(rom, sections)
    print(f"JAL targets found: {len(jal_targets)}")
    
    print("Splitting functions...")
    new_sections, total_splits = split_functions(sections, jal_targets)
    
    new_func_count = sum(len(s["functions"]) for s in new_sections)
    print(f"New function count: {new_func_count} (added {total_splits} splits)")
    
    print(f"Writing output to {OUTPUT_PATH}...")
    write_syms_toml(OUTPUT_PATH, header_lines, new_sections)
    
    print("Done!")

if __name__ == "__main__":
    main()

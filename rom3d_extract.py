import os
import sys
import csv
import json
from struct import unpack_from, iter_unpack
from lzss import decompress
from midi import get_track_name

# Usage notes:
# First argument: Rom_3D file
# Second argument: directory to extract to

with open(sys.argv[1], "rb") as full_file:
    full_bytes = full_file.read()

subdir = ""
if len(sys.argv) > 2:
    subdir = sys.argv[2]+"/"
    os.makedirs(subdir, exist_ok=True)

# <L is format code for unsigned long
file_count = unpack_from("<L", full_bytes, 0)[0]
file_entries = full_bytes[4:4+16*file_count]

files_metadata = []

var1s, block_ptrs, full_types, var4s = zip(*iter_unpack("<LLLL", file_entries))
midi_files = 0
bmd_files = 0
type_4_files = 0
other_files = 0
for i in range(file_count):
    full_type = full_types[i]
    filetype = full_type % 128
    type_high = full_type // 128
    block_ptr = block_ptrs[i]
    next_ptr = block_ptrs[i+1] if i+1 < file_count else len(full_bytes)
    block = full_bytes[block_ptr:next_ptr]
    filename = None
    filetype_metadata = None
    
    match filetype:
        case 0 | 2 | 3 | 5:
            # Generic file (at least for now)
            filename = str(block_ptr)+f".{filetype}.bin"
            with open(subdir+filename, "wb") as outfile:
                outfile.write(block)
            other_files += 1
        case 1:
            # BMD file
            model_count = unpack_from("<L", block, 0)[0]
            index = 4+4*model_count
            hashes_bytes = block[4:index]
            hashes = [x[0] for x in iter_unpack("<L", hashes_bytes)]
            order = [x for x in block[index:index+model_count]]
            index += model_count + (4 - model_count%4 if model_count%4 != 0 else 0)
            index += 4 # Decompressed size, ignore
            output_bytes = decompress(block[index:])
            filename = str(block_ptr)+".bmd"
            with open(subdir+filename, "wb") as outfile:
                outfile.write(output_bytes)
            filetype_metadata = {
                "hashes": [hex(h) for h in hashes],
                "order": order
            }
            bmd_files += 1
        case 4:
            # Level info file
            record_count = unpack_from("<L", block, 0)[0]
            index = 4+4*record_count # Skip over offsets - not needed
            records = []
            for j in range(record_count):
                key = unpack_from("<L", block, index)[0]
                entry_count = unpack_from("<L", block, index+4)[0]
                index += 8 + 4*entry_count # Skip over offsets - not needed
                entries_raw = iter_unpack("<LLLL", block[index:index+(16*entry_count)])
                index += 16*entry_count
                records.append({
                    "id": hex(key),
                    "entries": [{
                        "type": hex(e[0]),
                        "refA": hex(e[1]),
                        "refB": hex(e[2]),
                        "aux": hex(e[3])
                    } for e in entries_raw]
                })
            filename = str(block_ptr)+f".{filetype}.bin"
            with open(subdir+filename, "wb") as outfile:
                outfile.write(block)
            filetype_metadata = {
                "records": records
            }
            type_4_files += 1
        case 6:
            # MIDI file
            output_bytes = decompress(block[4:])
            track_name = get_track_name(output_bytes)
            filename = (track_name if track_name != None else block_ptr)+".mid"
            with open(subdir+filename, "wb") as outfile:
                outfile.write(output_bytes)
            filetype_metadata = {
                "track_name": track_name
            }
            midi_files += 1
        case _:
            # Unexpected type
            print("Warning: unexpected filetype number "+filetype)
            filename = str(block_ptr)+".bin"
            with open(subdir+filename, "wb") as outfile:
                outfile.write(block)
            other_files += 1
    
    files_metadata.append({
        "filename": filename,
        "filetype": filetype,
        "type_high": type_high,
        "length": len(block),
        "id": hex(var1s[i]),
        "var4": hex(var4s[i]),
        "filetype_metadata": filetype_metadata
    })

with open("rom3d_metadata.json", "w", encoding="utf-8") as file:
    json.dump(files_metadata, file, ensure_ascii=False, indent="\t")

print(f"Extracted {bmd_files} BMD files, {midi_files} MIDI files, {type_4_files} Type 4 files, and {other_files} other files.")
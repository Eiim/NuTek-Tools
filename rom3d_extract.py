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
sbnk_swar_files = 0
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
        case 0 | 2 | 3:
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
        case 5:
            # SBNK + SWAR + extra header metadata
            #print(str(block_ptr)+".bin (index "+str(i)+")")
            filename = str(block_ptr)
            filenames = []
            delta = var4s[i] // 2
            metadata_size = (next_ptr - block_ptr) - delta
            offs = 0
            meta_list_count = unpack_from("<L", block, offs)[0]
            offs += 4
            unk_list_1 = []
            for j in range(meta_list_count):
                var = unpack_from("<L", block, offs)[0]
                unk_list_1.append(var)
                offs += 4
            #print("unk_list_1:"+str(unk_list_1))
            unk_list_2 = []
            for j in range(meta_list_count):
                var1 = unpack_from("<L", block, offs)[0]
                var2 = unpack_from("<L", block, offs+4)[0]
                unk_list_2.append({
                    "var1": var1,
                    "var2": var2})
                offs += 8
            #print("unk_list_2:"+str(unk_list_2))
            if ((block_ptr+offs) % 32 != 0):
                offs += 32 - ((block_ptr+offs) % 32) # align to 32-byte boundary
            #print(f"offs={offs}")
            #print("lz_archive_length_or_whatever = "+str(unpack_from("<L", block, offs)[0]))
            is_lz_compressed = False
            if (offs + 4 == metadata_size):
                # then it's probably lz compressed?
                is_lz_compressed = True
                offs += 4 # lz archive length or whatever
            #print(f"is_lz_compressed = {is_lz_compressed}")
            arc_file_bytes = []
            if (is_lz_compressed):
                #print("writing \""+subdir+filename+".bin.lz\"")
                filenames.append(filename+".bin.lz")
                with open(subdir+filename+".bin.lz", "wb") as outfile:
                    outfile.write(block[offs:])
                arc_file_bytes = decompress(block[offs:])
            else:
                arc_file_bytes = block[offs:]
            #print("writing \""+subdir+filename+".bin\"")
            filenames.append(filename+".bin")
            with open(subdir+filename+".bin", "wb") as outfile:
                outfile.write(arc_file_bytes)
            # now parse the metadata and extract the sound files within this archive/container
            offs = 0
            sound_file_count = unpack_from("<L", arc_file_bytes, offs)[0]
            #print(f"sound_file_count = {sound_file_count}")
            offs += 4
            sound_file_ptrs = []
            for j in range(sound_file_count):
                ptr = unpack_from("<L", arc_file_bytes, offs)[0]
                sound_file_ptrs.append(ptr)
                offs += 4
            #print("sound_file_ptrs = "+str(sound_file_ptrs))
            for j in range(sound_file_count):
                sf_ptr = sound_file_ptrs[j]
                next_sf_ptr = sound_file_ptrs[j+1] if j+1 < sound_file_count else len(arc_file_bytes)
                sf_siz = next_sf_ptr - sf_ptr
                # i've only ever seen this be "SBNK" and "SWAR"
                sf_magic = unpack_from("4s", arc_file_bytes, sf_ptr)[0]
                sf_magic_str = sf_magic.decode('ascii', errors='ignore')
                #sf_ext = sanitize_filename(sf_magic_str, replacement_text="_")
                #if ((sf_ext == "_") or (sf_ext == "____")): # i forget which
                #    sf_ext = "bin"
                #else:
                #    sf_ext = sf_ext.lower()
                sf_ext = ""
                known_sf_ext = {
                    "SWAR": "swar",
                    "SBNK": "sbnk",
                }
                sf_ext = known_sf_ext.get(sf_magic_str, "bin")
                sf_filename = filename+f"_file_{j}."+sf_ext
                #print("writing \""+subdir+sf_filename+"\"")
                filenames.append(sf_filename)
                with open(subdir+sf_filename, "wb") as outfile:
                    outfile.write(arc_file_bytes[sf_ptr:next_sf_ptr])
            filetype_metadata = {
                "filenames": filenames,
                "unk_list_1": unk_list_1,
                "unk_list_2": unk_list_2,
                "is_lz_compressed": is_lz_compressed,
                "sound_file_count": sound_file_count,
                "sound_file_ptrs": sound_file_ptrs,
            }
            sbnk_swar_files += 1
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

print(f"Extracted {bmd_files} BMD files, {midi_files} MIDI files, {type_4_files} Type 4 files, {sbnk_swar_files} sound archive files, and {other_files} other files.")
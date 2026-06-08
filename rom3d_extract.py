import os
import sys
import csv
from struct import unpack_from, iter_unpack
from lzss import decompress
from midi import get_track_name

with open(sys.argv[1], "rb") as full_file:
    full_bytes = full_file.read()

subdir = ""
if len(sys.argv) > 2:
    subdir = sys.argv[2]+"/"
    os.makedirs(subdir, exist_ok=True)

# <L is format code for unsigned long
file_count = unpack_from("<L", full_bytes, 0)[0]
file_entries = full_bytes[4:4+16*file_count]

with open("results.csv", "w", newline="") as csv_file:
    result_csv = csv.writer(csv_file)
    result_csv.writerow(["filename","filetype","type_high","address","orig_length","var1","var4"])
    var1s, block_ptrs, full_types, var4s = zip(*iter_unpack("<LLLL", file_entries))
    midi_files = 0
    bmd_files = 0
    other_files = 0
    for i in range(file_count):
        full_type = full_types[i]
        filetype = full_type % 128
        type_high = full_type // 128
        block_ptr = block_ptrs[i]
        next_ptr = block_ptrs[i+1] if i+1 < file_count else len(full_bytes)
        block = full_bytes[block_ptr:next_ptr]
        filename = None
        
        match filetype:
            case 0 | 2 | 3 | 4 | 5:
                # Generic file (at least for now)
                filename = str(block_ptr)+".bin"
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
                with open(subdir+filename+".info", "w") as outfile:
                    outfile.write("Hashes: "+str(hashes)+"\n")
                    outfile.write("Order: "+str(order))
                bmd_files += 1
            case 6:
                # MIDI file
                output_bytes = decompress(block[4:])
                track_name = get_track_name(output_bytes)
                filename = (track_name if track_name != None else block_ptr)+".mid"
                with open(subdir+filename, "wb") as outfile:
                    outfile.write(output_bytes)
                midi_files += 1
            case _:
                # Unexpected type
                print("Warning: unexpected filetype number "+filetype)
                filename = str(block_ptr)+".bin"
                with open(subdir+filename, "wb") as outfile:
                    outfile.write(block)
                other_files += 1
        
        result_csv.writerow([filename,filetype,type_high,block_ptr,len(block),var1s[i],var4s[i]])
    
    print(f"Extracted {bmd_files} BMD files, {midi_files} MIDI files, and {other_files} other files.")
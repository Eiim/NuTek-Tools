import json

with open("rom3d_metadata.json") as f:
	files = json.load(f)

csv_out = "type_4_id,type_4_filename,record_id,model_id,type,refA,aux\n"

for f in files:
    if f["filetype"] == 4:
        for r in f["filetype_metadata"]["records"]:
            for e in r["entries"]:
                csv_out += f"{f['id']},{f['filename']},{r['id']},{e['refB']},{e['type']},{e['refA']},{e['aux']}\n"

with open("type_4s.csv", "w") as f:
    f.write(csv_out)
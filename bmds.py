import json

with open("rom3d_metadata.json") as f:
	files = json.load(f)

csv_out = "bmd_id,bmd_file,model_id,index\n"

for f in files:
    if f["filetype"] == 1:
        fm = f["filetype_metadata"]
        for i in range(len(fm["hashes"])):
            csv_out += f["id"]+","+f["filename"]+","+fm["hashes"][i]+","+str(fm["order"][i])+"\n"

with open("bmds.csv", "w") as f:
    f.write(csv_out)
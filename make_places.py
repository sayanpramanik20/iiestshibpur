import os
import csv
import xml.etree.ElementTree as ET

folder = os.path.dirname(os.path.abspath(__file__))
root = ET.parse(os.path.join(folder, "map.osm")).getroot()

pos = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in root.iter("node")}
places = []

def tags(el):
    return {t.get("k"): t.get("v") for t in el.findall("tag")}

for n in root.findall("node"):                      # named points
    t = tags(n)
    if "name" in t and "highway" not in t:
        places.append((t["name"], *pos[n.get("id")]))

for w in root.findall("way"):                       # named buildings / areas
    t = tags(w)
    if "name" in t and "highway" not in t:
        pts = [pos[r.get("ref")] for r in w.findall("nd") if r.get("ref") in pos]
        if pts:
            places.append((t["name"],
                           sum(p[0] for p in pts) / len(pts),
                           sum(p[1] for p in pts) / len(pts)))

with open(os.path.join(folder, "places.csv"), "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["name", "lat", "lon"])
    wr.writerows(places)
print(len(places), "named places saved")
import os
import math
import csv
import collections
import xml.etree.ElementTree as ET

folder = os.path.dirname(os.path.abspath(__file__))

# ---- map of our campus ----
MIN_LAT, MAX_LAT = 22.5530, 22.5581
MIN_LON, MAX_LON = 88.3001, 88.3113
# ---------------------

# road types a car can use (walking paths, steps, etc. are skipped)
DRIVABLE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
            "residential", "service", "living_street", "road",
            "motorway_link", "trunk_link", "primary_link", "secondary_link",
            "tertiary_link"}


def haversine(a, b):
    R = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def tags(el):
    return {t.get("k"): t.get("v") for t in el.findall("tag")}


root = ET.parse(os.path.join(folder, "map.osm")).getroot()
pos = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in root.iter("node")}

# ---------- edges from roads ----------
edge = {}          # (u, v) -> (length, oneway, road_name)
for w in root.findall("way"):
    t = tags(w)
    if t.get("highway") not in DRIVABLE:
        continue
    refs = [r.get("ref") for r in w.findall("nd") if r.get("ref") in pos]
    oneway = t.get("oneway", "no")
    if t.get("junction") == "roundabout" or t.get("highway") in ("motorway", "motorway_link"):
        if oneway == "no":
            oneway = "yes"
    name = t.get("name", "")
    for a, b in zip(refs, refs[1:]):
        if a == b:
            continue
        d = haversine(pos[a], pos[b])
        if oneway in ("yes", "true", "1"):
            pairs = [(a, b)]
        elif oneway == "-1":
            pairs = [(b, a)]
        else:
            pairs = [(a, b), (b, a)]
        for p in pairs:
            edge[p] = (d, oneway != "no", name)

# ---------- crop to the campus box ----------
def inside(n):
    la, lo = pos[n]
    return MIN_LAT <= la <= MAX_LAT and MIN_LON <= lo <= MAX_LON

edge = {k: v for k, v in edge.items() if inside(k[0]) and inside(k[1])}

# ---------- keep the largest connected piece ----------
adj = collections.defaultdict(set)
for u, v in edge:
    adj[u].add(v)
    adj[v].add(u)
seen, best = set(), []
for s in adj:
    if s in seen:
        continue
    stack, comp = [s], []
    seen.add(s)
    while stack:
        x = stack.pop()
        comp.append(x)
        for y in adj[x]:
            if y not in seen:
                seen.add(y)
                stack.append(y)
    if len(comp) > len(best):
        best = comp
keep = set(best)
edge = {k: v for k, v in edge.items() if k[0] in keep and k[1] in keep}

# ---------- write nodes.csv and edges.csv ----------
with open(os.path.join(folder, "nodes.csv"), "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["node_id", "lat", "lon"])
    for n in sorted(keep):
        wr.writerow([n, pos[n][0], pos[n][1]])

with open(os.path.join(folder, "edges.csv"), "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["from_node", "to_node", "length_m", "oneway", "road_name"])
    for (u, v), (d, ow, nm) in edge.items():
        wr.writerow([u, v, d, ow, nm])

print(len(keep), "nodes,", len(edge), "edges saved")

# ---------- named places inside the box ----------
places = []
for n in root.findall("node"):
    t = tags(n)
    if "name" in t and "highway" not in t and inside(n.get("id")):
        places.append((t["name"], *pos[n.get("id")]))
for w in root.findall("way"):
    t = tags(w)
    if "name" in t and "highway" not in t:
        pts = [pos[r.get("ref")] for r in w.findall("nd") if r.get("ref") in pos]
        if pts:
            la = sum(p[0] for p in pts) / len(pts)
            lo = sum(p[1] for p in pts) / len(pts)
            if MIN_LAT <= la <= MAX_LAT and MIN_LON <= lo <= MAX_LON:
                places.append((t["name"], la, lo))

with open(os.path.join(folder, "places.csv"), "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["name", "lat", "lon"])
    wr.writerows(places)
print(len(places), "named places saved")
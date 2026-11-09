import os
import time
import math
import random
import numpy as np
import pandas as pd
import folium
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

INF = float("inf")
folder = os.path.dirname(os.path.abspath(__file__))

# -: Load dataset :-
nodes_df = pd.read_csv(os.path.join(folder, "nodes.csv"))
edges_df = pd.read_csv(os.path.join(folder, "edges.csv"))
has_names = "road_name" in edges_df.columns

coords = {int(r.node_id): (r.lat, r.lon) for r in nodes_df.itertuples()}

_len = {}
road_of = {}
for r in edges_df.itertuples():
    u, v = int(r.from_node), int(r.to_node)
    if u != v and u in coords and v in coords:
        if (u, v) not in _len or r.length_m < _len[(u, v)]:
            _len[(u, v)] = float(r.length_m)
            nm = getattr(r, "road_name", "") if has_names else ""
            road_of[(u, v)] = nm if isinstance(nm, str) else ""

edges = list(_len.keys())                 # edge i = (u, v)
length = [_len[e] for e in edges]         # real road length in metres
edge_id = {e: i for i, e in enumerate(edges)}

adj = {n: [] for n in coords}
for u, v in edges:
    adj[u].append(v)


# -: Geometry helpers :-
def dist_m(lat1, lon1, lat2, lon2):
    dy = (lat1 - lat2) * 111000
    dx = (lon1 - lon2) * 111000 * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


def nearest_node(lat, lon):
    return min(coords, key=lambda n: (coords[n][0] - lat) ** 2 + (coords[n][1] - lon) ** 2)



# -: Extra road names you added by hand (optional file) :-
extra_roads_file = os.path.join(folder, "extra_roads.csv")
if os.path.exists(extra_roads_file):
    rdf = pd.read_csv(extra_roads_file).dropna(subset=["name"])
    for (u, v) in edges:
        mla = (coords[u][0] + coords[v][0]) / 2
        mlo = (coords[u][1] + coords[v][1]) / 2
        for r in rdf.itertuples():
            if dist_m(mla, mlo, r.lat, r.lon) < 30:
                road_of[(u, v)] = str(r.name)
                break

# -: Named places :-
place_pts = []
places_file = os.path.join(folder, "places.csv")
if os.path.exists(places_file):
    pdf = pd.read_csv(places_file).dropna(subset=["name"])
    place_pts = [(str(r.name), r.lat, r.lon) for r in pdf.itertuples()]

# -: Extra places added :-
extra_places_file = os.path.join(folder, "extra_places.csv")
if os.path.exists(extra_places_file):
    xdf = pd.read_csv(extra_places_file).dropna(subset=["name"])
    place_pts += [(str(r.name), r.lat, r.lon) for r in xdf.itertuples()]

# one entry per place name -> nearest road node
place_list = sorted({nm: nearest_node(la, lo) for nm, la, lo in place_pts}.items())

# readable label for every node: nearest place within 100 m, else road name
node_label = {}
for n, (la, lo) in coords.items():
    best, bd = None, 100
    for nm, pla, plo in place_pts:
        d = dist_m(la, lo, pla, plo)
        if d < bd:
            best, bd = nm, d
    if best:
        node_label[n] = f"near {best}"
    else:
        road = next((road_of[(n, v)] for v in adj[n] if road_of.get((n, v))), "")
        node_label[n] = f"on {road}" if road else "on an unnamed road"


def label(n):
    return node_label[n]


def describe_route(path):
    """Collapse the node list into road names with real distances."""
    steps = []
    for a, b in zip(path, path[1:]):
        road = road_of.get((a, b)) or "unnamed road"
        d = length[edge_id[(a, b)]]
        if steps and steps[-1][0] == road:
            steps[-1][1] += d
        else:
            steps.append([road, d])
    return " -> ".join(f"{r} ({d:.0f} m)" for r, d in steps)


# -: Bellman-Ford (edge list) :-
def bellman_ford(src, w):
    dist = {n: INF for n in coords}
    parent = {n: -1 for n in coords}
    dist[src] = 0
    for _ in range(len(coords) - 1):
        changed = False
        for i, (u, v) in enumerate(edges):
            if dist[u] != INF and dist[u] + w[i] < dist[v]:
                dist[v] = dist[u] + w[i]
                parent[v] = u
                changed = True
        if not changed:
            break
    return dist, parent


def solve(w, frm, dest):
    """Shortest path from 'frm' to 'dest'. Returns (distance, path)."""
    dist, parent = bellman_ford(frm, w)
    if dist[dest] == INF:
        return INF, []
    path, v = [], dest
    while v != -1:
        path.append(v)
        v = parent[v]
    return dist[dest], path[::-1]


def mark_on_path(path):
    on_path = [False] * len(edges)
    for a, b in zip(path, path[1:]):
        on_path[edge_id[(a, b)]] = True
    return on_path


# Choosing start and destination :-
def reachable_from(src):
    seen, stack = {src}, [src]
    while stack:
        for v in adj[stack.pop()]:
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return seen


def pick_points():
    """Show the road map, click A then B, return the nearest nodes."""
    segs = [[(coords[u][1], coords[u][0]), (coords[v][1], coords[v][0])]
            for u, v in edges]
    while True:
        fig, ax = plt.subplots(figsize=(8, 10))
        ax.add_collection(LineCollection(segs, colors="gray", linewidths=0.8))
        ax.autoscale()
        ax.set_aspect("equal")
        ax.set_title("Click START (A) first, then DESTINATION (B)")

        pts = plt.ginput(2, timeout=0)
        plt.close(fig)

        if len(pts) < 2:
            print("You need to click two points. Try again.")
            continue

        src = nearest_node(pts[0][1], pts[0][0])
        dest = nearest_node(pts[1][1], pts[1][0])

        if src == dest:
            print("Start and destination are the same node. Click two different places.")
        elif dest not in reachable_from(src):
            print("B cannot be reached from A (one-way roads or a cut in the map). Click again.")
        else:
            return src, dest


def choose_place(prompt):
    while True:
        q = input(f"{prompt} (part of a name, '?' for all, Enter = click on map): ").strip().lower()
        if not q:
            return None
        hits = place_list if q == "?" else [p for p in place_list if q in p[0].lower()]
        if not hits:
            print("No place matches. Try another word.")
            continue
        for i, (nm, _) in enumerate(hits[:20], 1):
            print(f"  {i}. {nm}")
        if len(hits) > 20:
            print(f"  ... {len(hits) - 20} more, type a longer name to narrow down")
        s = input("Enter the number: ").strip()
        if s.isdigit() and 1 <= int(s) <= min(20, len(hits)):
            return hits[int(s) - 1][1]


def pick_by_name():
    if not place_list:
        print("No places.csv found, so click on the map instead.")
        return pick_points()
    while True:
        a = choose_place("Start A")
        if a is None:
            return pick_points()
        b = choose_place("Destination B")
        if b is None:
            return pick_points()
        if a == b:
            print("Start and destination are the same place.")
        elif b not in reachable_from(a):
            print("B cannot be reached from A. Choose again.")
        else:
            return a, b


# -: Map output :-
def save_map(planned, travelled, reroutes, filename):
    m = folium.Map(location=coords[travelled[0]], zoom_start=16)
    pts = lambda p: [coords[n] for n in p]
    folium.PolyLine(pts(planned), weight=4, color="gray", dash_array="8",
                    tooltip="Original shortest path").add_to(m)
    folium.PolyLine(pts(travelled), weight=6, color="blue",
                    tooltip="Route actually travelled").add_to(m)
    folium.Marker(coords[travelled[0]], popup=f"Start {label(travelled[0])}",
                  icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(coords[travelled[-1]], popup=f"Destination {label(travelled[-1])}",
                  icon=folium.Icon(color="red")).add_to(m)
    for n in reroutes:
        folium.Marker(coords[n], popup=f"Rerouted {label(n)}",
                      icon=folium.Icon(color="orange", icon="warning-sign")).add_to(m)
    full = os.path.join(folder, filename)
    m.save(full)
    return full



# -: Live animated view :-
def make_live(src, dest, planned, factor, min_f, max_f):
    """Open a window: roads coloured by traffic, with the traveller moving on it."""
    plt.ion()
    fig, ax = plt.subplots(figsize=(11, 8))
    off = 0.000012                      # small side offset so two-way roads show both lanes
    segs = []
    for u, v in edges:
        (la1, lo1), (la2, lo2) = coords[u], coords[v]
        dx, dy = lo2 - lo1, la2 - la1
        n = math.hypot(dx, dy) or 1
        ox_, oy_ = dy / n * off, -dx / n * off
        segs.append([(lo1 + ox_, la1 + oy_), (lo2 + ox_, la2 + oy_)])
    lc = LineCollection(segs, cmap="RdYlGn_r", linewidths=2.2)
    lc.set_array(np.array(factor))
    lc.set_clim(min_f, max_f)
    ax.add_collection(lc)
    ax.autoscale()
    ax.set_aspect(1 / math.cos(math.radians(coords[src][0])))
    ax.set_xticks([])
    ax.set_yticks([])
    cb = fig.colorbar(lc, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("Traffic factor (1 = free road, 3 = heavy traffic)")

    xy = lambda p: ([coords[n][1] for n in p], [coords[n][0] for n in p])
    ax.plot(*xy(planned), "--", color="black", lw=1.3, label="Original plan")
    travelled_ln, = ax.plot([], [], color="blue", lw=4, label="Travelled")
    remaining_ln, = ax.plot([], [], color="magenta", lw=2.5, label="Remaining route")
    ax.scatter(*[[coords[src][1]], [coords[src][0]]], s=140, c="limegreen",
               edgecolors="black", zorder=5, label="Start A")
    ax.scatter(*[[coords[dest][1]], [coords[dest][0]]], s=220, c="red", marker="*",
               edgecolors="black", zorder=5, label="Destination B")
    reroute_sc = ax.scatter([], [], s=130, c="orange", marker="^", edgecolors="black",
                            zorder=6, label="Rerouted here")
    car, = ax.plot([], [], "o", color="white", mec="black", ms=11, zorder=7, label="Traveller")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    return dict(fig=fig, ax=ax, lc=lc, trav=travelled_ln, rem=remaining_ln,
                rer=reroute_sc, car=car, xy=xy)


def update_live(L, cur, visited, path, reroutes, factor, title):
    if not plt.fignum_exists(L["fig"].number):
        return
    L["lc"].set_array(np.array(factor))
    L["trav"].set_data(*L["xy"](visited))
    L["rem"].set_data(*L["xy"](path))
    L["car"].set_data([coords[cur][1]], [coords[cur][0]])
    if reroutes:
        L["rer"].set_offsets([[coords[n][1], coords[n][0]] for n in reroutes])
    L["ax"].set_title(title, fontsize=10)
    L["fig"].canvas.draw_idle()


def live_pause(L, seconds):
    if plt.fignum_exists(L["fig"].number):
        plt.pause(max(seconds, 0.001))
    else:
        time.sleep(seconds)


def main():
    print(f"Loaded {len(coords)} nodes, {len(edges)} edges, {len(place_list)} named places")

    src, dest = pick_by_name()
    print(f"\nFrom {label(src)} to {label(dest)}")

    interval = float(input("Seconds per step (weights change every step): "))

    # Traffic factor: weight = real length x factor. Drifts every step.
    min_f, max_f, max_step = 1.0, 3.0, 0.3

    choice, trip_no = "y", 0
    while choice.lower() == "y":
        trip_no += 1
        print(f"\n=: Trip {trip_no} :=")

        factor = [random.uniform(min_f, max_f) for _ in edges]
        w = [length[i] * factor[i] for i in range(len(edges))]

        cur, travelled_cost, bf_runs = src, 0.0, 1
        remaining, path = solve(w, cur, dest)

        planned = list(path)
        visited, reroutes = [cur], []
        on_path = mark_on_path(path)

        print(f"Start {label(cur)}. Shortest trip cost = {remaining:.0f}")
        print("Route:", describe_route(path))

        L = make_live(src, dest, planned, factor, min_f, max_f)
        update_live(L, cur, visited, path, reroutes, factor,
                    f"Trip {trip_no}: start {label(cur)} -> {label(dest)}")
        status = "Plan ready"

        while cur != dest:
            live_pause(L, interval)

            # 1. weights change while we are travelling
            problem_ahead = False
            for i in range(len(edges)):
                nf = min(max_f, max(min_f, factor[i] + random.uniform(-max_step, max_step)))
                delta = nf - factor[i]
                factor[i] = nf
                w[i] = length[i] * nf
                if on_path[i] and delta > 0:
                    problem_ahead = True          # our road got worse
                if not on_path[i] and delta < 0:
                    problem_ahead = True          # another road got better

            print(f"\n--- Now {label(cur)} ---")

            # 2. stop here and recompute from the CURRENT node only if needed
            if problem_ahead:
                old_path = list(path)
                remaining, path = solve(w, cur, dest)
                bf_runs += 1
                on_path = mark_on_path(path)
                if path != old_path:
                    reroutes.append(cur)
                    status = "PROBLEM AHEAD - rerouted"
                    print(f"Problem ahead! Stopped {label(cur)} and rerouted.")
                else:
                    print("Weights changed, but this path is still the best.")
                    status = "Weights changed - same route still best"
                print(f"Best trip cost from here to {label(dest)} = {remaining:.0f}")
                print("Route:", describe_route(path))
            else:
                remaining = sum(w[edge_id[(a, b)]] for a, b in zip(path, path[1:]))
                print(f"Road ahead is fine. Trip cost left = {remaining:.0f}")
                status = "Road ahead is fine"

            # 3. move one step along the path
            nxt = path[1]
            travelled_cost += w[edge_id[(cur, nxt)]]
            path.pop(0)
            cur = nxt
            visited.append(cur)
            on_path = mark_on_path(path)
            print(f"Moved {label(cur)}", flush=True)
            update_live(L, cur, visited, path, reroutes, factor,
                        f"Trip {trip_no} | {status} | now {label(cur)} | "
                        f"reroutes: {len(reroutes)} | algorithm runs: {bf_runs}")

        real_m = sum(length[edge_id[(a, b)]] for a, b in zip(visited, visited[1:]))
        print(f"\nReached {label(dest)}.")
        print(f"Total trip cost = {travelled_cost:.0f}, real distance = {real_m:.0f} m")
        print(f"algorithm ran {bf_runs} times on this trip.")
        print(f"Map saved: {save_map(planned, visited, reroutes, f'trip{trip_no}.html')}")
        if plt.fignum_exists(L["fig"].number):
            update_live(L, cur, visited, path, reroutes, factor,
                        f"Trip {trip_no} finished at {label(dest)} | reroutes: {len(reroutes)} | "
                        f"algorithm runs: {bf_runs} | real distance: {real_m:.0f} m")
            png = os.path.join(folder, f"trip{trip_no}.png")
            L["fig"].savefig(png, dpi=150)
            print(f"Picture saved: {png}")
            plt.pause(0.5)

        choice = input("\nrun again (y/n) ")
        if plt.fignum_exists(L["fig"].number):
            plt.close(L["fig"])


if __name__ == "__main__":
    main()
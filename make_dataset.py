import os
import osmnx as ox
import matplotlib.pyplot as plt

folder = os.path.dirname(os.path.abspath(__file__))
ox.settings.cache_folder = os.path.join(folder, "cache")

G = ox.graph_from_xml(os.path.join(folder, "map.osm"),
                      bidirectional=False,
                      simplify=False,
                      retain_all=True)

nodes, edges = ox.graph_to_gdfs(G)

nodes = nodes.reset_index()[["osmid", "y", "x"]]
nodes.columns = ["node_id", "lat", "lon"]

edges = edges.reset_index()
if "name" not in edges.columns:
    edges["name"] = ""
edges["name"] = edges["name"].apply(
    lambda x: x[0] if isinstance(x, list) and x else ("" if x is None or x != x else x))
edges = edges[["u", "v", "length", "oneway", "name"]]
edges.columns = ["from_node", "to_node", "length_m", "oneway", "road_name"]

nodes.to_csv(os.path.join(folder, "nodes.csv"), index=False)
edges.to_csv(os.path.join(folder, "edges.csv"), index=False)
print(len(nodes), "nodes,", len(edges), "edges saved")

ox.plot_graph(G, node_size=5)   # quick check of the new map
plt.show()
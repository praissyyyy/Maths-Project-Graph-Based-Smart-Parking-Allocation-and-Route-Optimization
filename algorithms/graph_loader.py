"""
Graph Loader Module for Gandhipuram, Coimbatore Road Network.
Handles downloading, cleaning, saving, and loading the road network graph.
"""

import os
import time
import logging
import networkx as nx
import osmnx as ox

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Default study area parameters
STUDY_POINT = (11.0182714, 76.9677744)  # Latitude, Longitude of Gandhipuram, Coimbatore
STUDY_RADIUS = 1400  # meters
DEFAULT_GRAPHML_PATH = os.path.join(
    os.path.abspath(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "gandhipuram_road_network.graphml"
)


def clean_graph_attributes(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """
    Ensure all node and edge attributes are serializable and have valid numeric lengths.
    Converts list attributes to strings if needed for GraphML export.
    """
    for u, v, k, data in G.edges(keys=True, data=True):
        # Ensure length attribute exists and is a float
        if 'length' not in data or data['length'] is None:
            # Fallback estimation using coordinates
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            dist = ox.distance.great_circle(
                u_data.get('y', 0), u_data.get('x', 0),
                v_data.get('y', 0), v_data.get('x', 0)
            )
            data['length'] = float(dist if dist > 0 else 10.0)
        else:
            try:
                data['length'] = float(data['length'])
            except (ValueError, TypeError):
                data['length'] = 10.0

        # Handle list or non-serializable edge attributes for GraphML
        for attr_key, attr_val in list(data.items()):
            if isinstance(attr_val, list):
                data[attr_key] = ", ".join(map(str, attr_val))

    for node, data in G.nodes(data=True):
        if 'x' in data:
            data['x'] = float(data['x'])
        if 'y' in data:
            data['y'] = float(data['y'])
        for attr_key, attr_val in list(data.items()):
            if isinstance(attr_val, list):
                data[attr_key] = ", ".join(map(str, attr_val))

    return G


def get_clean_digraph(multi_g: nx.MultiDiGraph) -> nx.DiGraph:
    """
    Convert MultiDiGraph to a clean DiGraph for routing algorithms.
    If multiple edges exist between u and v, retain the minimum length edge.
    """
    G = nx.DiGraph()
    for n, d in multi_g.nodes(data=True):
        G.add_node(n, x=float(d.get('x', 0.0)), y=float(d.get('y', 0.0)), **{k: v for k, v in d.items() if k not in ('x', 'y')})

    for u, v, k, d in multi_g.edges(keys=True, data=True):
        length = float(d.get('length', 10.0))
        if G.has_edge(u, v):
            if length < G[u][v]['length']:
                G[u][v]['length'] = length
                G[u][v]['weight'] = length
                G[u][v].update(d)
        else:
            edge_data = dict(d)
            edge_data['length'] = length
            edge_data['weight'] = length
            G.add_edge(u, v, **edge_data)

    return G


def download_road_network(
    point: tuple = STUDY_POINT,
    dist: int = STUDY_RADIUS,
    save_path: str = DEFAULT_GRAPHML_PATH,
    max_retries: int = 3
) -> nx.MultiDiGraph:
    """
    Download drivable road network from OpenStreetMap around the target point.
    Saves to GraphML and returns the graph.
    """
    logger.info(f"Downloading road network for coordinates {point} with radius {dist}m...")
    
    ox.settings.use_cache = True
    ox.settings.log_console = False

    endpoints = [
        "https://overpass-api.de/api",
        "https://overpass.kumi.systems/api",
        "https://maps.mail.ru/osm/tools/overpass/api"
    ]

    last_err = None
    for attempt in range(max_retries):
        for endpoint in endpoints:
            try:
                ox.settings.overpass_endpoint = endpoint
                logger.info(f"Attempt {attempt + 1}: querying Overpass endpoint {endpoint}...")
                G = ox.graph_from_point(point, dist=dist, network_type="drive", simplify=True)
                if G is not None and len(G) > 0:
                    logger.info(f"Successfully downloaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
                    G = clean_graph_attributes(G)
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    ox.save_graphml(G, filepath=save_path)
                    logger.info(f"Saved road network to {save_path}")
                    return G
            except Exception as e:
                logger.warning(f"Failed query to {endpoint}: {e}")
                last_err = e
                time.sleep(2)

    raise RuntimeError(f"Could not download road network from OpenStreetMap after retries: {last_err}")


def load_or_fetch_road_network(filepath: str = DEFAULT_GRAPHML_PATH) -> tuple[nx.MultiDiGraph, nx.DiGraph]:
    """
    Load the road network from GraphML if available, else download it.
    Returns (MultiDiGraph, DiGraph).
    """
    if os.path.exists(filepath):
        logger.info(f"Loading existing road network from {filepath}...")
        try:
            raw_g = nx.read_graphml(filepath)
            # Standardize attributes into a clean DiGraph
            di_g = nx.DiGraph()
            for n, d in raw_g.nodes(data=True):
                node_d = dict(d)
                node_d['x'] = float(node_d.get('x', 0.0))
                node_d['y'] = float(node_d.get('y', 0.0))
                di_g.add_node(n, **node_d)

            for u, v, d in raw_g.edges(data=True):
                length = float(d.get('length', 10.0))
                if di_g.has_edge(u, v):
                    if length < di_g[u][v]['length']:
                        di_g[u][v]['length'] = length
                        di_g[u][v]['weight'] = length
                        di_g[u][v].update(d)
                else:
                    edge_d = dict(d)
                    edge_d['length'] = length
                    edge_d['weight'] = length
                    di_g.add_edge(u, v, **edge_d)

            logger.info(f"Loaded graph from file: {di_g.number_of_nodes()} nodes, {di_g.number_of_edges()} directed edges.")
            return raw_g, di_g
        except Exception as e:
            logger.warning(f"Failed to load GraphML file ({e}). Re-downloading...")

    multi_g = download_road_network(save_path=filepath)
    di_g = get_clean_digraph(multi_g)
    return multi_g, di_g


if __name__ == "__main__":
    multi_g, di_g = load_or_fetch_road_network()
    print(f"Road network ready. MultiDiGraph nodes={len(multi_g)}, edges={multi_g.number_of_edges()}")
    print(f"DiGraph nodes={len(di_g)}, edges={di_g.number_of_edges()}")

"""
Graph-Theoretic Analysis Module for Gandhipuram Road Network.
Calculates vertex/edge counts, degree statistics, connectivity, articulation points,
bridges, Eulerian characteristics, planarity, and exports academic visualizations.
"""

import os
import json
import logging
import networkx as nx
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)


def compute_graph_statistics(G: nx.DiGraph, output_dir: str = None) -> dict:
    """
    Computes rigorous graph-theoretic statistics for the directed road network G = (V, E).
    Also derives the underlying undirected graph G_undir for undirected topological properties
    such as articulation points, bridges, and planarity.
    """
    V_count = G.number_of_nodes()
    E_count = G.number_of_edges()

    # Degree metrics (In-degree, Out-degree, Total degree)
    in_degrees = [d for _, d in G.in_degree()]
    out_degrees = [d for _, d in G.out_degree()]
    total_degrees = [d for _, d in G.degree()]

    avg_in_degree = float(np.mean(in_degrees)) if in_degrees else 0.0
    avg_out_degree = float(np.mean(out_degrees)) if out_degrees else 0.0
    avg_degree = float(np.mean(total_degrees)) if total_degrees else 0.0
    min_degree = int(np.min(total_degrees)) if total_degrees else 0
    max_degree = int(np.max(total_degrees)) if total_degrees else 0

    # Density for directed graph: D = |E| / (|V|*(|V|-1))
    density = nx.density(G)

    # Connected Components (Weakly and Strongly connected)
    weak_components = list(nx.weakly_connected_components(G))
    strong_components = list(nx.strongly_connected_components(G))
    num_weak_cc = len(weak_components)
    num_strong_cc = len(strong_components)

    largest_wcc = max(weak_components, key=len) if weak_components else set()
    largest_scc = max(strong_components, key=len) if strong_components else set()

    largest_wcc_size = len(largest_wcc)
    largest_scc_size = len(largest_scc)

    # Undirected representation for structural cut vertices and bridges
    # G_undir collapses multi/anti-parallel edges into simple undirected edges
    G_undir = G.to_undirected()

    articulation_points = list(nx.articulation_points(G_undir))
    bridges = list(nx.bridges(G_undir))

    # Eulerian properties
    is_eulerian_directed = nx.is_eulerian(G)
    is_semi_eulerian = nx.is_semieulerian(G) if hasattr(nx, 'is_semieulerian') else False

    # Planarity check on undirected graph representation
    is_planar, embedding = nx.check_planarity(G_undir)

    # Compile comprehensive statistical summary
    stats = {
        "vertices_count": V_count,
        "directed_edges_count": E_count,
        "undirected_edges_count": G_undir.number_of_edges(),
        "average_degree": round(avg_degree, 4),
        "average_in_degree": round(avg_in_degree, 4),
        "average_out_degree": round(avg_out_degree, 4),
        "min_degree": min_degree,
        "max_degree": max_degree,
        "density": round(density, 6),
        "weakly_connected_components_count": num_weak_cc,
        "strongly_connected_components_count": num_strong_cc,
        "largest_weakly_connected_component_nodes": largest_wcc_size,
        "largest_strongly_connected_component_nodes": largest_scc_size,
        "articulation_points_count": len(articulation_points),
        "bridges_count": len(bridges),
        "is_eulerian_directed": is_eulerian_directed,
        "is_semi_eulerian": is_semi_eulerian,
        "is_planar_undirected": is_planar,
        "study_area": "Gandhipuram, Coimbatore, Tamil Nadu, India",
        "description": "Rigorous graph-theoretic characterization of urban road network"
    }

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "graph_statistics.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=4)
        logger.info(f"Saved graph statistics JSON to {json_path}")

    return stats


def generate_graph_visualizations(G: nx.DiGraph, output_dir: str):
    """
    Generate professional figures:
    1. Road Network Graph
    2. Degree Distribution
    3. Connected Components
    4. Articulation Points and Bridges
    """
    os.makedirs(output_dir, exist_ok=True)
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 11})

    G_undir = G.to_undirected()
    pos = {node: (data.get('x', 0), data.get('y', 0)) for node, data in G.nodes(data=True)}

    # 1. Road Network Spatial Graph
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    for u, v in G.edges():
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                    color="#1E3A8A", alpha=0.5, linewidth=0.8)
    xs = [coord[0] for coord in pos.values()]
    ys = [coord[1] for coord in pos.values()]
    ax.scatter(xs, ys, color="#3B82F6", s=12, alpha=0.7, edgecolors="none", zorder=3)
    ax.set_title("Gandhipuram Road Network Graph $G = (V, E)$\nDirected Urban Road Topology", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude (°E)", fontweight="medium")
    ax.set_ylabel("Latitude (°N)", fontweight="medium")
    ax.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, "road_network_graph.png"))
    plt.close(fig)

    # 2. Degree Distribution (In, Out, Total)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    in_deg = [d for _, d in G.in_degree()]
    out_deg = [d for _, d in G.out_degree()]
    tot_deg = [d for _, d in G.degree()]

    bins = np.arange(0, max(tot_deg) + 2) - 0.5
    ax.hist([in_deg, out_deg, tot_deg], bins=bins, color=["#0284C7", "#10B981", "#6366F1"],
            label=["In-degree", "Out-degree", "Total degree"], alpha=0.85, rwidth=0.8)
    ax.set_title("Degree Distribution of Gandhipuram Road Network", fontsize=13, fontweight="bold")
    ax.set_xlabel("Node Degree ($k$)")
    ax.set_ylabel("Frequency (Count of Intersections)")
    ax.set_xticks(range(0, max(tot_deg) + 1))
    ax.legend(frameon=True)
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, "degree_distribution.png"))
    plt.close(fig)

    # 3. Connected Components Visualization
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    scc = list(nx.strongly_connected_components(G))
    palette = sns.color_palette("tab10", len(scc[:8]))

    for u, v in G.edges():
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], color="#CBD5E1", lw=0.6, zorder=1)

    for i, comp in enumerate(scc[:8]):
        comp_xs = [pos[n][0] for n in comp if n in pos]
        comp_ys = [pos[n][1] for n in comp if n in pos]
        color = palette[i % len(palette)]
        ax.scatter(comp_xs, comp_ys, s=18, color=color, label=f"SCC {i+1} ({len(comp)} nodes)", zorder=2)

    ax.set_title("Strongly Connected Components in Directed Road Network", fontsize=13, fontweight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend(loc="upper right", frameon=True, fontsize=9)
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, "connected_components.png"))
    plt.close(fig)

    # 4. Articulation Points and Bridges
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    for u, v in G_undir.edges():
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], color="#94A3B8", lw=0.7, zorder=1)

    # Highlight bridges
    bridges = list(nx.bridges(G_undir))
    for u, v in bridges:
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], color="#DC2626", lw=2.2, zorder=3)

    # Highlight articulation points
    art_points = list(nx.articulation_points(G_undir))
    art_xs = [pos[n][0] for n in art_points if n in pos]
    art_ys = [pos[n][1] for n in art_points if n in pos]
    ax.scatter(art_xs, art_ys, s=40, color="#EF4444", marker="^", edgecolors="black", linewidth=0.8,
               label=f"Articulation Points (n={len(art_points)})", zorder=4)

    # Dummy line for bridge legend
    ax.plot([], [], color="#DC2626", lw=2, label=f"Bridges (n={len(bridges)})")

    ax.set_title("Topological Vulnerabilities: Articulation Points & Bridges\nCritical Road Bottlenecks for Network Flow", fontsize=13, fontweight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend(loc="upper right", frameon=True)
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, "articulation_points_bridges.png"))
    plt.close(fig)

    logger.info(f"Saved all 4 graph-theoretic visualizations to {output_dir}")

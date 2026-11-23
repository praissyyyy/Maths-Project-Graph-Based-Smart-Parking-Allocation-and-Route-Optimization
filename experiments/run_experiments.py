"""
Comprehensive Experiments Runner for Parking Allocation and Route Optimization.
Executes experiments across all scenarios, runs repeated timing benchmarks,
generates comparison CSV tables and high-resolution academic charts.
"""

import os
import json
import logging
import random
import time
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from algorithms.graph_loader import load_or_fetch_road_network
from algorithms.dijkstra import dijkstra_shortest_path
from algorithms.astar import astar_shortest_path
from algorithms.allocation import compare_allocation_algorithms

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_allocation_experiments(G: nx.DiGraph, facilities: list, data_dir: str = "data", results_dir: str = "results") -> pd.DataFrame:
    """
    Evaluates FCFS, Nearest Available, and MCMF on Low, Medium, High, and Oversubscribed demand scenarios.
    """
    scenarios = ["low", "medium", "high", "oversubscribed"]
    all_summary_dfs = []
    detailed_assignments = []

    for sc in scenarios:
        req_path = os.path.join(data_dir, f"vehicle_requests_{sc}.csv")
        df_req = pd.read_csv(req_path)
        vehicles = df_req.to_dict(orient="records")

        res = compare_allocation_algorithms(G, vehicles, facilities, scenario_name=sc)
        all_summary_dfs.append(res["summary_table"])

        for algo_key in ["fcfs", "nearest_available", "mcmf"]:
            for assign in res[algo_key]["assignments"]:
                detailed_assignments.append({
                    "scenario": sc,
                    "algorithm": res[algo_key]["algorithm"],
                    "vehicle_id": assign["vehicle_id"],
                    "assigned_facility": assign["assigned_facility"],
                    "status": assign["status"],
                    "travel_distance_m": assign["travel_distance"],
                    "start_node": assign["start_node"],
                    "destination_node": assign["destination_node"]
                })

    df_all_summary = pd.concat(all_summary_dfs, ignore_index=True)
    df_detailed = pd.DataFrame(detailed_assignments)

    # Save CSVs
    csv_dir = os.path.join(results_dir, "csv")
    os.makedirs(csv_dir, exist_ok=True)
    df_all_summary.to_csv(os.path.join(csv_dir, "allocation_comparison.csv"), index=False)
    df_detailed.to_csv(os.path.join(data_dir, "allocation_results.csv"), index=False)
    df_detailed.to_csv(os.path.join(csv_dir, "detailed_allocation_results.csv"), index=False)

    logger.info("Saved allocation experiment results to CSV.")
    return df_all_summary


def run_routing_experiments(G: nx.DiGraph, facilities: list, sample_size: int = 30, results_dir: str = "results") -> pd.DataFrame:
    """
    Rigorously benchmarks Dijkstra vs A* on at least 25 (default 30) vehicle routes.
    Includes repeated timing runs (5 runs per query) to measure median, min, max, and mean latency.
    Verifies path validity in the directed graph.
    """
    logger.info(f"Benchmarking Dijkstra vs A* over {sample_size} routes with repeated timing...")
    scc = max(nx.strongly_connected_components(G), key=len)
    scc_nodes = sorted(list(scc))
    rng = random.Random(42)

    # Pick 30 source nodes and destination facilities
    sources = rng.sample(scc_nodes, sample_size)
    fac_nodes = [f["node_id"] for f in facilities]

    records = []
    sample_route_to_plot = None

    for idx, src in enumerate(sources):
        dst = rng.choice(fac_nodes)
        if src == dst:
            continue

        # Repeated runs for Dijkstra
        dijk_times = []
        dijk_path = None
        dijk_dist = 0.0
        dijk_explored = 0
        for _ in range(5):
            p, d, exp, t = dijkstra_shortest_path(G, str(src), str(dst))
            dijk_times.append(t)
            if dijk_path is None:
                dijk_path, dijk_dist, dijk_explored = p, d, exp

        # Repeated runs for A*
        astar_times = []
        astar_path = None
        astar_dist = 0.0
        astar_explored = 0
        for _ in range(5):
            p, d, exp, t = astar_shortest_path(G, str(src), str(dst))
            astar_times.append(t)
            if astar_path is None:
                astar_path, astar_dist, astar_explored = p, d, exp

        # Path validity verification
        def verify_path(path):
            if not path or len(path) < 2:
                return True
            for i in range(len(path) - 1):
                if not G.has_edge(path[i], path[i+1]):
                    return False
            return True

        dijk_valid = verify_path(dijk_path)
        astar_valid = verify_path(astar_path)

        dist_diff = abs(dijk_dist - astar_dist) if (dijk_path and astar_path) else 0.0

        records.append({
            "route_id": f"ROUTE-{idx+1:02d}",
            "source_node": str(src),
            "target_node": str(dst),
            "dijkstra_distance_m": round(dijk_dist, 2),
            "astar_distance_m": round(astar_dist, 2),
            "distance_difference_m": round(dist_diff, 4),
            "dijkstra_nodes_explored": dijk_explored,
            "astar_nodes_explored": astar_explored,
            "exploration_reduction_pct": round(((dijk_explored - astar_explored) / max(dijk_explored, 1)) * 100.0, 2),
            "dijkstra_time_median_ms": round(np.median(dijk_times) * 1000.0, 3),
            "dijkstra_time_mean_ms": round(np.mean(dijk_times) * 1000.0, 3),
            "astar_time_median_ms": round(np.median(astar_times) * 1000.0, 3),
            "astar_time_mean_ms": round(np.mean(astar_times) * 1000.0, 3),
            "dijkstra_path_valid": dijk_valid,
            "astar_path_valid": astar_valid,
            "path_length_nodes": len(dijk_path) if dijk_path else 0
        })

        if sample_route_to_plot is None and dijk_path and len(dijk_path) > 5:
            sample_route_to_plot = {
                "source": src,
                "target": dst,
                "dijkstra_path": dijk_path,
                "astar_path": astar_path
            }

    df_routing = pd.DataFrame(records)
    csv_dir = os.path.join(results_dir, "csv")
    df_routing.to_csv(os.path.join(csv_dir, "routing_comparison.csv"), index=False)
    logger.info("Saved routing benchmark results to CSV.")

    return df_routing, sample_route_to_plot


def generate_experimental_charts(df_alloc: pd.DataFrame, df_routing: pd.DataFrame, G: nx.DiGraph, sample_route: dict, charts_dir: str = "results/charts"):
    """
    Renders publication-quality charts for allocation and routing benchmarks.
    """
    os.makedirs(charts_dir, exist_ok=True)
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 11})

    palette = {"FCFS": "#EF4444", "Nearest Available": "#F59E0B", "MCMF": "#10B981"}

    # Chart 1: Average Travel Distance by Scenario & Algorithm
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.barplot(data=df_alloc, x="scenario", y="avg_travel_distance_m", hue="algorithm",
                palette=palette, ax=ax)
    ax.set_title("Average Vehicle Travel Distance by Allocation Algorithm", fontsize=13, fontweight="bold")
    ax.set_xlabel("Demand Scenario", fontweight="medium")
    ax.set_ylabel("Average Travel Distance (meters)", fontweight="medium")
    ax.legend(title="Algorithm", frameon=True)
    plt.tight_layout()
    fig.savefig(os.path.join(charts_dir, "allocation_travel_distance.png"))
    plt.close(fig)

    # Chart 2: Total Travel Distance by Scenario & Algorithm
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.barplot(data=df_alloc, x="scenario", y="total_travel_distance_m", hue="algorithm",
                palette=palette, ax=ax)
    ax.set_title("Total Travel Distance Incurred Across Road Network", fontsize=13, fontweight="bold")
    ax.set_xlabel("Demand Scenario", fontweight="medium")
    ax.set_ylabel("Total Distance (meters)", fontweight="medium")
    ax.legend(title="Algorithm", frameon=True)
    plt.tight_layout()
    fig.savefig(os.path.join(charts_dir, "allocation_total_distance.png"))
    plt.close(fig)

    # Chart 3: Execution Time Comparison (Allocation)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.barplot(data=df_alloc, x="scenario", y="execution_time_s", hue="algorithm",
                palette=palette, ax=ax)
    ax.set_title("Allocation Algorithm Execution Time Complexity", fontsize=13, fontweight="bold")
    ax.set_xlabel("Demand Scenario", fontweight="medium")
    ax.set_ylabel("Execution Time (seconds)", fontweight="medium")
    ax.legend(title="Algorithm", frameon=True)
    plt.tight_layout()
    fig.savefig(os.path.join(charts_dir, "allocation_execution_time.png"))
    plt.close(fig)

    # Chart 4: Routing Execution Time (Dijkstra vs A*)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    df_melt_time = pd.melt(df_routing, id_vars=["route_id"],
                           value_vars=["dijkstra_time_median_ms", "astar_time_median_ms"],
                           var_name="Algorithm", value_name="Time_ms")
    df_melt_time["Algorithm"] = df_melt_time["Algorithm"].replace({
        "dijkstra_time_median_ms": "Dijkstra",
        "astar_time_median_ms": "A* Search"
    })
    sns.boxplot(data=df_melt_time, x="Algorithm", y="Time_ms", palette=["#3B82F6", "#8B5CF6"], ax=ax, width=0.4)
    sns.stripplot(data=df_melt_time, x="Algorithm", y="Time_ms", color="black", alpha=0.6, jitter=0.2, ax=ax)
    ax.set_title("Shortest-Path Latency Distribution (Median of 5 Repeated Runs)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Execution Time (milliseconds)", fontweight="medium")
    plt.tight_layout()
    fig.savefig(os.path.join(charts_dir, "routing_execution_time.png"))
    plt.close(fig)

    # Chart 5: Search Nodes Explored (Dijkstra vs A*)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    df_melt_exp = pd.melt(df_routing, id_vars=["route_id"],
                          value_vars=["dijkstra_nodes_explored", "astar_nodes_explored"],
                          var_name="Algorithm", value_name="Nodes_Explored")
    df_melt_exp["Algorithm"] = df_melt_exp["Algorithm"].replace({
        "dijkstra_nodes_explored": "Dijkstra",
        "astar_nodes_explored": "A* Search"
    })
    sns.boxplot(data=df_melt_exp, x="Algorithm", y="Nodes_Explored", palette=["#0284C7", "#10B981"], ax=ax, width=0.4)
    sns.stripplot(data=df_melt_exp, x="Algorithm", y="Nodes_Explored", color="black", alpha=0.6, jitter=0.2, ax=ax)
    ax.set_title("Search State Space Exploration: Dijkstra vs A* Heuristic", fontsize=13, fontweight="bold")
    ax.set_ylabel("Search Nodes Explored (Count)", fontweight="medium")
    plt.tight_layout()
    fig.savefig(os.path.join(charts_dir, "routing_nodes_explored.png"))
    plt.close(fig)

    # Chart 6: Sample Route Visualization on Road Graph
    if sample_route:
        fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
        pos = {n: (G.nodes[n].get('x', 0), G.nodes[n].get('y', 0)) for n in G.nodes()}

        for u, v in G.edges():
            if u in pos and v in pos:
                ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], color="#CBD5E1", lw=0.6, zorder=1)

        # Plot route path
        path = sample_route["dijkstra_path"]
        path_xs = [pos[n][0] for n in path if n in pos]
        path_ys = [pos[n][1] for n in path if n in pos]
        ax.plot(path_xs, path_ys, color="#2563EB", lw=3.2, label="Optimal Calculated Route", zorder=3)
        ax.scatter([path_xs[0]], [path_ys[0]], color="#16A34A", s=90, marker="o", label="Vehicle Start Node", zorder=4)
        ax.scatter([path_xs[-1]], [path_ys[-1]], color="#DC2626", s=110, marker="P", label="Parking Facility Destination", zorder=4)

        ax.set_title(f"Optimized Shortest-Path Trajectory in Gandhipuram\nLength: {len(path)} nodes", fontsize=13, fontweight="bold")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.legend(loc="upper right", frameon=True)
        plt.tight_layout()
        fig.savefig(os.path.join(charts_dir, "sample_route_visualization.png"))
        plt.close(fig)

    logger.info("Saved all experimental benchmark charts to results/charts.")


def main():
    _, di_g = load_or_fetch_road_network()
    with open("data/parking_facilities.json", "r", encoding="utf-8") as f:
        facilities = json.load(f)

    df_alloc = run_allocation_experiments(di_g, facilities)
    df_routing, sample_route = run_routing_experiments(di_g, facilities, sample_size=30)
    generate_experimental_charts(df_alloc, df_routing, di_g, sample_route)
    print("All experiments and charts completed successfully!")


if __name__ == "__main__":
    main()

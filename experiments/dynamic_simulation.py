"""
Dynamic Parking Availability Simulation Module.
Simulates discrete arrival events, occupancy updates, vehicle departures,
reallocation under varying demand, and records timeline state metrics.
"""

import os
import json
import logging
import random
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from algorithms.graph_loader import load_or_fetch_road_network
from algorithms.fcfs import run_fcfs_allocation
from algorithms.nearest_available import run_nearest_available_allocation
from algorithms.mcmf import run_mcmf_allocation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_dynamic_parking_simulation(
    G: nx.DiGraph,
    base_facilities: list,
    results_dir: str = "results"
) -> dict:
    """
    Executes an 8-stage dynamic parking simulation:
    Stage 1: Initial occupancy (50 occupied, 100 available)
    Stage 2: First batch of vehicle arrivals (30 requests)
    Stage 3: Occupancy updates post-Batch 1
    Stage 4: Simulated departures (15 parked vehicles leave)
    Stage 5: Availability updates post-departure
    Stage 6: Second batch of vehicle requests (40 requests)
    Stage 7: Multi-algorithm comparative reallocation (FCFS, Nearest, MCMF)
    Stage 8: Final parking occupancy and convergence

    Saves timeline metrics to CSV and renders a multi-facility timeline chart.
    """
    logger.info("Initializing dynamic parking simulation...")
    scc = max(nx.strongly_connected_components(G), key=len)
    scc_nodes = sorted(list(scc))
    rng = random.Random(777)

    # Initialize facility states
    # Total capacity = 30 per facility, Initial occupied = 10, Initial available = 20
    fac_states = {}
    for f in base_facilities:
        f_id = f["facility_id"]
        fac_states[f_id] = {
            "facility_id": f_id,
            "facility_name": f["facility_name"],
            "node_id": f["node_id"],
            "total_capacity": f["total_capacity"],
            "occupied": f["initial_occupied"],
            "available": f["available_spaces"]
        }

    timeline_records = []

    def record_stage(stage_num: int, timestamp: str, event_desc: str):
        total_occ = sum(fac_states[f]["occupied"] for f in fac_states)
        total_avail = sum(fac_states[f]["available"] for f in fac_states)
        row = {
            "stage": stage_num,
            "timestamp": timestamp,
            "event_description": event_desc,
            "total_occupied": total_occ,
            "total_available": total_avail
        }
        for f_id in sorted(fac_states.keys()):
            row[f"{f_id}_occupied"] = fac_states[f_id]["occupied"]
            row[f"{f_id}_available"] = fac_states[f_id]["available"]
            row[f"{f_id}_util_pct"] = round((fac_states[f_id]["occupied"] / fac_states[f_id]["total_capacity"]) * 100.0, 1)
        timeline_records.append(row)

    # Stage 1: Initial State
    record_stage(1, "09:00 AM", "Initial Parking State (Simulated Baseline)")

    # Stage 2 & 3: First Batch Arrivals (30 vehicles)
    batch1_vehicles = []
    for i in range(1, 31):
        src_node = rng.choice(scc_nodes)
        batch1_vehicles.append({
            "vehicle_id": f"SIM-B1-{i:02d}",
            "start_node": str(src_node),
            "vehicle_type": rng.choice(["Sedan", "SUV", "Hatchback"])
        })

    # Prepare facility list for allocation
    fac_list_1 = [
        {
            "facility_id": f_id,
            "node_id": fac_states[f_id]["node_id"],
            "total_capacity": fac_states[f_id]["total_capacity"],
            "initial_occupied": fac_states[f_id]["occupied"],
            "available_spaces": fac_states[f_id]["available"]
        }
        for f_id in sorted(fac_states.keys())
    ]

    # Run allocation for batch 1 using Nearest Available
    res_b1 = run_nearest_available_allocation(G, batch1_vehicles, fac_list_1)
    for assign in res_b1["assignments"]:
        f_id = assign["assigned_facility"]
        if f_id and fac_states[f_id]["available"] > 0:
            fac_states[f_id]["occupied"] += 1
            fac_states[f_id]["available"] -= 1

    record_stage(2, "09:30 AM", "Batch 1 Arrivals (30 vehicles requested, assigned via Nearest Available)")
    record_stage(3, "10:00 AM", "Occupancy Settled Post-Batch 1 Arrivals")

    # Stage 4 & 5: Simulated Departures (15 vehicles depart across facilities)
    departures_per_fac = {"P1": 3, "P2": 4, "P3": 2, "P4": 4, "P5": 2}
    for f_id, dep_count in departures_per_fac.items():
        actual_dep = min(dep_count, fac_states[f_id]["occupied"])
        fac_states[f_id]["occupied"] -= actual_dep
        fac_states[f_id]["available"] += actual_dep

    record_stage(4, "10:30 AM", "Simulated Departures (-15 parked vehicles leave slots)")
    record_stage(5, "11:00 AM", "Availability Updated Post-Departure (Freed 15 slots)")

    # Stage 6 & 7: Batch 2 Arrivals (40 vehicles) under Three Algorithms Reallocation
    batch2_vehicles = []
    for i in range(1, 41):
        src_node = rng.choice(scc_nodes)
        batch2_vehicles.append({
            "vehicle_id": f"SIM-B2-{i:02d}",
            "start_node": str(src_node),
            "vehicle_type": rng.choice(["Sedan", "SUV", "Hatchback"])
        })

    fac_list_2 = [
        {
            "facility_id": f_id,
            "node_id": fac_states[f_id]["node_id"],
            "total_capacity": fac_states[f_id]["total_capacity"],
            "initial_occupied": fac_states[f_id]["occupied"],
            "available_spaces": fac_states[f_id]["available"]
        }
        for f_id in sorted(fac_states.keys())
    ]

    # Compare algorithms for Batch 2
    b2_fcfs = run_fcfs_allocation(G, batch2_vehicles, fac_list_2)
    b2_near = run_nearest_available_allocation(G, batch2_vehicles, fac_list_2)
    b2_mcmf = run_mcmf_allocation(G, batch2_vehicles, fac_list_2)

    # Apply MCMF allocation as primary system logic for Batch 2
    for assign in b2_mcmf["assignments"]:
        f_id = assign["assigned_facility"]
        if f_id and fac_states[f_id]["available"] > 0:
            fac_states[f_id]["occupied"] += 1
            fac_states[f_id]["available"] -= 1

    record_stage(6, "11:30 AM", "Batch 2 Vehicle Requests (40 vehicles received)")
    record_stage(7, "12:00 PM", "Optimal Dynamic Reallocation (MCMF algorithm applied)")
    record_stage(8, "12:30 PM", "Final Parking Occupancy State (Steady State)")

    # Save to CSV
    df_timeline = pd.DataFrame(timeline_records)
    csv_dir = os.path.join(results_dir, "csv")
    os.makedirs(csv_dir, exist_ok=True)
    df_timeline.to_csv(os.path.join(csv_dir, "dynamic_simulation_timeline.csv"), index=False)

    # Render Timeline Chart
    charts_dir = os.path.join(results_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 10})

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), dpi=300, sharex=True)

    stages = [f"S{r['stage']}\n{r['timestamp']}" for r in timeline_records]

    # Top plot: Aggregate System Occupancy vs Available
    ax1.plot(stages, df_timeline["total_occupied"], marker='o', color="#DC2626", lw=2.5, label="Total Occupied Slots")
    ax1.plot(stages, df_timeline["total_available"], marker='s', color="#16A34A", lw=2.5, label="Total Available Slots")
    ax1.axhline(150, color="#1E3A8A", linestyle="--", alpha=0.7, label="System Capacity Limit (150)")
    ax1.set_title("System-Wide Dynamic Parking Availability Timeline (Simulated Events)", fontsize=13, fontweight="bold")
    ax1.set_ylabel("Number of Slots", fontweight="medium")
    ax1.legend(loc="center right", frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Bottom plot: Individual Facility Occupancy Trajectories
    colors = ["#2563EB", "#7C3AED", "#DB2777", "#D97706", "#059669"]
    for idx, f in enumerate(sorted(fac_states.keys())):
        ax2.plot(stages, df_timeline[f"{f}_occupied"], marker='^', color=colors[idx % len(colors)],
                 lw=1.8, label=f"{f} Occupancy (Cap: 30)")

    ax2.set_title("Individual Facility Dynamic Utilization Profiles", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Simulation Stage & Time Window", fontweight="medium")
    ax2.set_ylabel("Occupied Slots", fontweight="medium")
    ax2.set_ylim(0, 32)
    ax2.legend(loc="upper left", ncol=3, frameon=True, fontsize=9)
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    chart_path = os.path.join(charts_dir, "dynamic_parking_timeline.png")
    fig.savefig(chart_path)
    plt.close(fig)

    logger.info(f"Saved dynamic simulation timeline chart to {chart_path}")

    return {
        "timeline_df": df_timeline,
        "batch2_comparison": {
            "FCFS": {
                "assigned": b2_fcfs["assigned_count"],
                "total_dist": b2_fcfs["total_travel_distance_m"],
                "avg_dist": b2_fcfs["avg_travel_distance_m"]
            },
            "Nearest_Available": {
                "assigned": b2_near["assigned_count"],
                "total_dist": b2_near["total_travel_distance_m"],
                "avg_dist": b2_near["avg_travel_distance_m"]
            },
            "MCMF": {
                "assigned": b2_mcmf["assigned_count"],
                "total_dist": b2_mcmf["total_travel_distance_m"],
                "avg_dist": b2_mcmf["avg_travel_distance_m"]
            }
        }
    }


if __name__ == "__main__":
    _, di_g = load_or_fetch_road_network()
    with open("data/parking_facilities.json", "r", encoding="utf-8") as f:
        facs = json.load(f)
    sim_res = run_dynamic_parking_simulation(di_g, facs)
    print("Dynamic Parking Simulation Complete. Batch 2 Results:", sim_res["batch2_comparison"])

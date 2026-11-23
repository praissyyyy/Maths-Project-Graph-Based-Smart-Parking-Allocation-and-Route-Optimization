"""
Data Generator Module for Simulated Parking Facilities and Vehicle Requests.
Generates reproducible academic datasets for Gandhipuram, Coimbatore.
"""

import os
import json
import logging
import random
from datetime import datetime, timedelta
import pandas as pd
import networkx as nx
import numpy as np

from algorithms.graph_loader import load_or_fetch_road_network

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FACILITY_DEFINITIONS = [
    {
        "facility_id": "P1",
        "facility_name": "P1 - Cross Cut Road Commercial Parking",
        "target_coords": (11.0175, 76.9650),
        "description": "Multi-tier commercial parking hub serving Cross Cut Road retail district.",
        "capacity": 30,
        "initial_occupied": 10,
        "initial_available": 20
    },
    {
        "facility_id": "P2",
        "facility_name": "P2 - 100 Feet Road Multi-Level Parking",
        "target_coords": (11.0230, 76.9690),
        "description": "Modern automated facility on 100 Feet Road commercial corridor.",
        "capacity": 30,
        "initial_occupied": 10,
        "initial_available": 20
    },
    {
        "facility_id": "P3",
        "facility_name": "P3 - Bharathiar Road Express Parking",
        "target_coords": (11.0140, 76.9685),
        "description": "Transit parking adjacent to Bharathiar Road and central junction.",
        "capacity": 30,
        "initial_occupied": 10,
        "initial_available": 20
    },
    {
        "facility_id": "P4",
        "facility_name": "P4 - Dr. Nanjappa Road Central Parking",
        "target_coords": (11.0185, 76.9720),
        "description": "High-volume parking complex serving Gandhipuram Central Bus Stand zone.",
        "capacity": 30,
        "initial_occupied": 10,
        "initial_available": 20
    },
    {
        "facility_id": "P5",
        "facility_name": "P5 - Sathy Road Highway Transit Parking",
        "target_coords": (11.0250, 76.9630),
        "description": "Northbound peripheral transit parking off Sathyamangalam National Highway.",
        "capacity": 30,
        "initial_occupied": 10,
        "initial_available": 20
    }
]


def find_nearest_node(G: nx.DiGraph, target_lat: float, target_lon: float, candidate_nodes: set = None) -> tuple:
    """
    Finds node in G with minimum Euclidean/great-circle distance to target coordinates.
    """
    nodes_to_search = candidate_nodes if candidate_nodes else G.nodes()
    best_node = None
    min_dist_sq = float('inf')

    for node in nodes_to_search:
        data = G.nodes[node]
        lat = data.get('y', 0.0)
        lon = data.get('x', 0.0)
        dist_sq = (lat - target_lat) ** 2 + (lon - target_lon) ** 2
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            best_node = node

    best_lat = G.nodes[best_node].get('y', 0.0)
    best_lon = G.nodes[best_node].get('x', 0.0)
    return best_node, best_lat, best_lon


def generate_parking_facilities(G: nx.DiGraph, output_dir: str = "data") -> list[dict]:
    """
    Generates 5 simulated parking facilities snapped to the road graph.
    Saves data/parking_facilities.csv, data/parking_facilities.json, and data/parking_slots.csv.
    """
    os.makedirs(output_dir, exist_ok=True)
    # Ensure facilities belong to largest strongly connected component so every vehicle can route
    scc = max(nx.strongly_connected_components(G), key=len)
    logger.info(f"Using largest strongly connected component with {len(scc)} nodes for facility snapping.")

    facilities = []
    all_slots = []

    for defn in FACILITY_DEFINITIONS:
        target_lat, target_lon = defn["target_coords"]
        node_id, lat, lon = find_nearest_node(G, target_lat, target_lon, candidate_nodes=scc)

        facility_record = {
            "facility_id": defn["facility_id"],
            "facility_name": defn["facility_name"],
            "node_id": str(node_id),
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "total_capacity": defn["capacity"],
            "initial_occupied": defn["initial_occupied"],
            "available_spaces": defn["initial_available"],
            "description": defn["description"]
        }

        # Generate 30 slots per facility
        slots = []
        for s_idx in range(1, defn["capacity"] + 1):
            slot_number = f"{defn['facility_id']}-S{s_idx:02d}"
            # First 10 slots are occupied initially, remaining 20 are available
            status = "occupied" if s_idx <= defn["initial_occupied"] else "available"
            slot_record = {
                "slot_id": f"{defn['facility_id']}_{s_idx:02d}",
                "facility_id": defn["facility_id"],
                "slot_number": slot_number,
                "initial_status": status
            }
            slots.append(slot_record)
            all_slots.append(slot_record)

        facility_record["slots"] = slots
        facilities.append(facility_record)

    # Save facilities JSON and CSV
    json_path = os.path.join(output_dir, "parking_facilities.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(facilities, f, indent=4)

    # Simplified facilities CSV (without nested slots list)
    flat_facilities = [{k: v for k, v in f.items() if k != "slots"} for f in facilities]
    df_fac = pd.DataFrame(flat_facilities)
    df_fac.to_csv(os.path.join(output_dir, "parking_facilities.csv"), index=False)

    # Slots CSV
    df_slots = pd.DataFrame(all_slots)
    df_slots.to_csv(os.path.join(output_dir, "parking_slots.csv"), index=False)

    logger.info(f"Generated {len(facilities)} parking facilities and {len(all_slots)} slots in {output_dir}")
    return facilities


def generate_vehicle_requests(G: nx.DiGraph, output_dir: str = "data") -> dict[str, pd.DataFrame]:
    """
    Generates simulated vehicle requests for Low (10), Medium (25), High (45), and
    Oversubscribed (110) scenarios using reproducible fixed seeds.
    """
    os.makedirs(output_dir, exist_ok=True)
    scc = max(nx.strongly_connected_components(G), key=len)
    scc_nodes = sorted(list(scc))  # Deterministic list order

    scenarios = {
        "low": {"count": 10, "seed": 42},
        "medium": {"count": 25, "seed": 101},
        "high": {"count": 45, "seed": 202},
        "oversubscribed": {"count": 110, "seed": 303}
    }

    vehicle_types = ["Sedan", "SUV", "Hatchback", "Compact"]
    scenario_dfs = {}
    all_requests = []
    base_time = datetime(2026, 11, 19, 9, 0, 0)

    for sc_name, sc_config in scenarios.items():
        rng = random.Random(sc_config["seed"])
        requests = []
        count = sc_config["count"]

        # Select random nodes from SCC
        selected_nodes = rng.choices(scc_nodes, k=count)

        for i, node in enumerate(selected_nodes, 1):
            v_id = f"VEH-{sc_name.upper()[:3]}-{i:03d}"
            v_type = rng.choice(vehicle_types)
            lat = G.nodes[node].get('y', 0.0)
            lon = G.nodes[node].get('x', 0.0)
            
            # Stagger request timestamps by 1-3 minutes
            req_time = base_time + timedelta(seconds=i * 75 + rng.randint(-15, 15))
            # Estimated arrival 15-30 minutes later
            arr_time = req_time + timedelta(minutes=rng.randint(15, 30))

            req_dict = {
                "vehicle_id": v_id,
                "scenario": sc_name,
                "start_node": str(node),
                "start_lat": round(lat, 7),
                "start_lon": round(lon, 7),
                "vehicle_type": v_type,
                "request_time": req_time.strftime("%Y-%m-%d %H:%M:%S"),
                "requested_arrival_time": arr_time.strftime("%Y-%m-%d %H:%M:%S")
            }
            requests.append(req_dict)
            all_requests.append(req_dict)

        df_sc = pd.DataFrame(requests)
        df_sc.to_csv(os.path.join(output_dir, f"vehicle_requests_{sc_name}.csv"), index=False)
        scenario_dfs[sc_name] = df_sc

    # Combined dataset
    df_all = pd.DataFrame(all_requests)
    df_all.to_csv(os.path.join(output_dir, "vehicle_requests.csv"), index=False)

    logger.info(f"Generated vehicle request datasets for all scenarios in {output_dir}")
    return scenario_dfs


if __name__ == "__main__":
    _, di_g = load_or_fetch_road_network()
    generate_parking_facilities(di_g)
    generate_vehicle_requests(di_g)
    print("Facility and Vehicle Data Generation Complete.")

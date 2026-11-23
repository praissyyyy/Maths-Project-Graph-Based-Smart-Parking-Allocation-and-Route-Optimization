"""
First-Come, First-Served (FCFS) Parking Allocation Algorithm.
Sequentially allocates vehicles to the first facility with available capacity in defined order.
"""

import time
import networkx as nx
from typing import List, Dict, Any
from algorithms.dijkstra import dijkstra_shortest_path


def run_fcfs_allocation(
    G: nx.DiGraph,
    vehicles: List[Dict[str, Any]],
    facilities: List[Dict[str, Any]],
    facility_order: List[str] = None
) -> Dict[str, Any]:
    """
    Executes FCFS parking allocation.

    Args:
        G: Directed road graph.
        vehicles: List of vehicle request dictionaries.
        facilities: List of facility dictionaries with capacity and available_spaces.
        facility_order: Optional ordering of facility IDs. Defaults to ['P1', 'P2', 'P3', 'P4', 'P5'].

    Returns:
        Dictionary containing allocations, metrics, execution time, and facility states.
    """
    start_time = time.perf_counter()

    if facility_order is None:
        facility_order = [f["facility_id"] for f in facilities]

    # Map facilities for quick lookup
    fac_map = {f["facility_id"]: dict(f) for f in facilities}
    # Track dynamic remaining capacity
    remaining_capacity = {f_id: fac_map[f_id]["available_spaces"] for f_id in facility_order}
    total_capacity = {f_id: fac_map[f_id]["total_capacity"] for f_id in facility_order}
    initial_occupied = {f_id: fac_map[f_id]["initial_occupied"] for f_id in facility_order}

    assignments = []
    total_travel_distance = 0.0
    assigned_count = 0
    unassigned_count = 0

    for veh in vehicles:
        v_id = veh["vehicle_id"]
        start_node = str(veh["start_node"])
        assigned_facility_id = None
        route_dist = 0.0
        route_path = []

        # Find first facility in defined order with remaining capacity
        for f_id in facility_order:
            if remaining_capacity[f_id] > 0:
                assigned_facility_id = f_id
                remaining_capacity[f_id] -= 1
                break

        if assigned_facility_id is not None:
            dest_node = str(fac_map[assigned_facility_id]["node_id"])
            path, dist, _, _ = dijkstra_shortest_path(G, start_node, dest_node)
            route_dist = dist if path else 0.0
            route_path = path if path else []
            total_travel_distance += route_dist
            assigned_count += 1
            status = "Assigned"
        else:
            status = "Unassigned"
            unassigned_count += 1

        assignments.append({
            "vehicle_id": v_id,
            "assigned_facility": assigned_facility_id,
            "status": status,
            "travel_distance": round(route_dist, 2),
            "start_node": start_node,
            "destination_node": fac_map[assigned_facility_id]["node_id"] if assigned_facility_id else None,
            "path": route_path
        })

    exec_time = time.perf_counter() - start_time
    total_vehicles = len(vehicles)
    avg_travel_distance = (total_travel_distance / assigned_count) if assigned_count > 0 else 0.0
    success_rate = (assigned_count / total_vehicles * 100.0) if total_vehicles > 0 else 0.0

    # Facility utilization calculation
    facility_utilization = {}
    for f_id in facility_order:
        assigned_to_f = sum(1 for a in assignments if a["assigned_facility"] == f_id)
        current_occupied = initial_occupied[f_id] + assigned_to_f
        util_pct = (current_occupied / total_capacity[f_id]) * 100.0
        facility_utilization[f_id] = {
            "initial_occupied": initial_occupied[f_id],
            "newly_assigned": assigned_to_f,
            "current_occupied": current_occupied,
            "total_capacity": total_capacity[f_id],
            "remaining_available": remaining_capacity[f_id],
            "utilization_pct": round(util_pct, 2)
        }

    return {
        "algorithm": "FCFS",
        "total_vehicles": total_vehicles,
        "assigned_count": assigned_count,
        "unassigned_count": unassigned_count,
        "success_rate_pct": round(success_rate, 2),
        "total_travel_distance_m": round(total_travel_distance, 2),
        "avg_travel_distance_m": round(avg_travel_distance, 2),
        "execution_time_s": round(exec_time, 6),
        "facility_utilization": facility_utilization,
        "assignments": assignments
    }

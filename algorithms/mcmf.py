"""
Minimum-Cost Maximum-Flow (MCMF) Parking Allocation Algorithm.
Formulates parking allocation as a capacity-constrained flow optimization network
solved via NetworkX Min-Cost Flow / Network Simplex.
"""

import time
import networkx as nx
from typing import List, Dict, Any
from algorithms.dijkstra import dijkstra_shortest_path


def run_mcmf_allocation(
    G: nx.DiGraph,
    vehicles: List[Dict[str, Any]],
    facilities: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Executes Minimum-Cost Maximum-Flow parking allocation.

    Mathematical Formulation:
        Minimize: sum_i sum_j (c_ij * x_ij)
        Subject to:
            sum_j x_ij <= 1,  for all vehicles i
            sum_i x_ij <= A_j, for all facilities j
            x_ij in {0, 1}
    where c_ij is shortest-path travel distance from vehicle i to facility j,
    and A_j is remaining capacity of facility j.

    Returns:
        Dictionary containing allocations, metrics, execution time, and facility states.
    """
    start_time = time.perf_counter()

    fac_map = {f["facility_id"]: dict(f) for f in facilities}
    total_capacity = {f["facility_id"]: f["total_capacity"] for f in facilities}
    initial_occupied = {f["facility_id"]: f["initial_occupied"] for f in facilities}
    available_capacities = {f["facility_id"]: f["available_spaces"] for f in facilities}

    total_vehicles = len(vehicles)
    total_available_slots = sum(available_capacities.values())
    target_flow = min(total_vehicles, total_available_slots)

    # 1. Precompute shortest paths and travel costs between each vehicle and facility
    cost_matrix = {}
    path_matrix = {}

    for veh in vehicles:
        v_id = veh["vehicle_id"]
        start_node = str(veh["start_node"])
        cost_matrix[v_id] = {}
        path_matrix[v_id] = {}

        for f in facilities:
            f_id = f["facility_id"]
            dest_node = str(f["node_id"])
            path, dist, _, _ = dijkstra_shortest_path(G, start_node, dest_node)
            cost_matrix[v_id][f_id] = dist if path is not None else 1e7
            path_matrix[v_id][f_id] = path if path is not None else []

    # 2. Build Flow Network F = (V_flow, E_flow)
    F = nx.DiGraph()
    source_node = "SOURCE"
    sink_node = "SINK"

    # Set supply / demand on source and sink
    F.add_node(source_node, demand=-target_flow)
    F.add_node(sink_node, demand=target_flow)

    # Vehicle nodes
    for veh in vehicles:
        v_id = veh["vehicle_id"]
        v_flow_node = f"V_{v_id}"
        F.add_node(v_flow_node, demand=0)
        # Source to Vehicle (capacity = 1, cost = 0)
        F.add_edge(source_node, v_flow_node, capacity=1, weight=0)

    # Facility nodes
    for f in facilities:
        f_id = f["facility_id"]
        f_flow_node = f"F_{f_id}"
        F.add_node(f_flow_node, demand=0)
        # Facility to Sink (capacity = A_j, cost = 0)
        F.add_edge(f_flow_node, sink_node, capacity=available_capacities[f_id], weight=0)

    # Vehicle to Facility edges (capacity = 1, cost = rounded integer meters for exact simplex)
    for veh in vehicles:
        v_id = veh["vehicle_id"]
        v_flow_node = f"V_{v_id}"
        for f in facilities:
            f_id = f["facility_id"]
            f_flow_node = f"F_{f_id}"
            cost = int(round(cost_matrix[v_id][f_id]))
            F.add_edge(v_flow_node, f_flow_node, capacity=1, weight=cost)

    # 3. Solve Min-Cost Flow
    flow_dict = {}
    if target_flow > 0:
        try:
            flow_dict = nx.min_cost_flow(F, weight="weight", capacity="capacity")
        except Exception as e:
            # Fallback to network_simplex or handle infeasibility
            cost, flow_dict = nx.network_simplex(F)

    # 4. Extract vehicle assignments
    assignments = []
    total_travel_distance = 0.0
    assigned_count = 0
    unassigned_count = 0

    assigned_facilities_counts = {f_id: 0 for f_id in available_capacities}

    for veh in vehicles:
        v_id = veh["vehicle_id"]
        v_flow_node = f"V_{v_id}"
        assigned_facility_id = None

        if v_flow_node in flow_dict:
            for neighbor, flow_val in flow_dict[v_flow_node].items():
                if flow_val > 0.5 and neighbor.startswith("F_"):
                    assigned_facility_id = neighbor[2:]  # Extract facility_id
                    break

        if assigned_facility_id is not None:
            route_dist = cost_matrix[v_id][assigned_facility_id]
            route_path = path_matrix[v_id][assigned_facility_id]
            total_travel_distance += route_dist
            assigned_count += 1
            assigned_facilities_counts[assigned_facility_id] += 1
            status = "Assigned"
            dest_node = fac_map[assigned_facility_id]["node_id"]
        else:
            route_dist = 0.0
            route_path = []
            status = "Unassigned"
            unassigned_count += 1
            dest_node = None

        assignments.append({
            "vehicle_id": v_id,
            "assigned_facility": assigned_facility_id,
            "status": status,
            "travel_distance": round(route_dist, 2),
            "start_node": str(veh["start_node"]),
            "destination_node": dest_node,
            "path": route_path
        })

    exec_time = time.perf_counter() - start_time
    avg_travel_distance = (total_travel_distance / assigned_count) if assigned_count > 0 else 0.0
    success_rate = (assigned_count / total_vehicles * 100.0) if total_vehicles > 0 else 0.0

    facility_utilization = {}
    for f in facilities:
        f_id = f["facility_id"]
        assigned_to_f = assigned_facilities_counts[f_id]
        current_occupied = initial_occupied[f_id] + assigned_to_f
        remaining_avail = available_capacities[f_id] - assigned_to_f
        util_pct = (current_occupied / total_capacity[f_id]) * 100.0
        facility_utilization[f_id] = {
            "initial_occupied": initial_occupied[f_id],
            "newly_assigned": assigned_to_f,
            "current_occupied": current_occupied,
            "total_capacity": total_capacity[f_id],
            "remaining_available": remaining_avail,
            "utilization_pct": round(util_pct, 2)
        }

    return {
        "algorithm": "MCMF",
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

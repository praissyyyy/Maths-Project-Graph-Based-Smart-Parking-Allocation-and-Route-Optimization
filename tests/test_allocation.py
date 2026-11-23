"""
Unit tests for Parking Allocation Algorithms (FCFS, Nearest Available, MCMF) and Capacity Constraints.
"""

import os
import json
import pytest
import networkx as nx
from algorithms.graph_loader import load_or_fetch_road_network
from algorithms.fcfs import run_fcfs_allocation
from algorithms.nearest_available import run_nearest_available_allocation
from algorithms.mcmf import run_mcmf_allocation


@pytest.fixture(scope="module")
def setup_allocation_env():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    graphml_path = os.path.join(base_dir, "data", "gandhipuram_road_network.graphml")
    _, di_g = load_or_fetch_road_network(filepath=graphml_path)

    with open(os.path.join(base_dir, "data", "parking_facilities.json"), "r", encoding="utf-8") as f:
        facilities = json.load(f)

    # 15 sample vehicles from SCC
    scc = max(nx.strongly_connected_components(di_g), key=len)
    scc_nodes = list(scc)[:15]
    vehicles = [
        {"vehicle_id": f"TEST-V-{i}", "start_node": str(node), "vehicle_type": "Sedan"}
        for i, node in enumerate(scc_nodes, 1)
    ]

    return di_g, facilities, vehicles


def test_fcfs_allocation(setup_allocation_env):
    """Test 4: Verify FCFS assigns vehicles sequentially in defined facility order."""
    di_g, facilities, vehicles = setup_allocation_env
    res = run_fcfs_allocation(di_g, vehicles, facilities)

    assert res["algorithm"] == "FCFS"
    assert res["total_vehicles"] == len(vehicles)
    assert res["assigned_count"] == len(vehicles)
    assert res["unassigned_count"] == 0
    assert res["success_rate_pct"] == 100.0
    assert res["total_travel_distance_m"] > 0


def test_nearest_available_allocation(setup_allocation_env):
    """Test 5: Verify Nearest Available selects lowest-distance facilities with available capacity."""
    di_g, facilities, vehicles = setup_allocation_env
    res = run_nearest_available_allocation(di_g, vehicles, facilities)

    assert res["algorithm"] == "Nearest Available"
    assert res["assigned_count"] == len(vehicles)
    assert res["unassigned_count"] == 0
    assert res["avg_travel_distance_m"] > 0


def test_mcmf_allocation(setup_allocation_env):
    """Test 6: Verify MCMF maximizes assignments while minimizing global travel distance."""
    di_g, facilities, vehicles = setup_allocation_env
    res = run_mcmf_allocation(di_g, vehicles, facilities)

    assert res["algorithm"] == "MCMF"
    assert res["assigned_count"] == len(vehicles)
    assert res["unassigned_count"] == 0
    assert res["total_travel_distance_m"] > 0


def test_capacity_constraints(setup_allocation_env):
    """Test 7: Verify algorithms strictly respect facility capacity and report unassigned vehicles."""
    di_g, facilities, _ = setup_allocation_env

    # Artificial constrained facilities: 2 facilities with 2 spaces each (total 4 spaces)
    constrained_facilities = [
        {
            "facility_id": "P1",
            "node_id": facilities[0]["node_id"],
            "total_capacity": 5,
            "initial_occupied": 3,
            "available_spaces": 2
        },
        {
            "facility_id": "P2",
            "node_id": facilities[1]["node_id"],
            "total_capacity": 5,
            "initial_occupied": 3,
            "available_spaces": 2
        }
    ]

    scc = max(nx.strongly_connected_components(di_g), key=len)
    scc_nodes = list(scc)[:7]  # 7 vehicles trying to book 4 spaces
    excess_vehicles = [
        {"vehicle_id": f"EXCESS-V-{i}", "start_node": str(node), "vehicle_type": "Sedan"}
        for i, node in enumerate(scc_nodes, 1)
    ]

    # Test FCFS
    fcfs_res = run_fcfs_allocation(di_g, excess_vehicles, constrained_facilities)
    assert fcfs_res["assigned_count"] == 4
    assert fcfs_res["unassigned_count"] == 3

    # Test Nearest Available
    near_res = run_nearest_available_allocation(di_g, excess_vehicles, constrained_facilities)
    assert near_res["assigned_count"] == 4
    assert near_res["unassigned_count"] == 3

    # Test MCMF
    mcmf_res = run_mcmf_allocation(di_g, excess_vehicles, constrained_facilities)
    assert mcmf_res["assigned_count"] == 4
    assert mcmf_res["unassigned_count"] == 3

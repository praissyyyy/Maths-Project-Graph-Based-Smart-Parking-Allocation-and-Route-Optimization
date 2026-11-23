"""
Unified Parking Allocation Framework.
Orchestrates FCFS, Nearest Available, and MCMF across demand scenarios and exports comparisons.
"""

import os
import json
import logging
from typing import List, Dict, Any
import pandas as pd
import networkx as nx

from algorithms.fcfs import run_fcfs_allocation
from algorithms.nearest_available import run_nearest_available_allocation
from algorithms.mcmf import run_mcmf_allocation

logger = logging.getLogger(__name__)


def compare_allocation_algorithms(
    G: nx.DiGraph,
    vehicles: List[Dict[str, Any]],
    facilities: List[Dict[str, Any]],
    scenario_name: str = "custom"
) -> Dict[str, Any]:
    """
    Executes FCFS, Nearest Available, and MCMF on the same vehicle batch and facilities.
    Returns structured results and comparative summary table.
    """
    logger.info(f"Running allocation comparison for scenario '{scenario_name}' ({len(vehicles)} vehicles)...")

    fcfs_res = run_fcfs_allocation(G, vehicles, facilities)
    near_res = run_nearest_available_allocation(G, vehicles, facilities)
    mcmf_res = run_mcmf_allocation(G, vehicles, facilities)

    summary_rows = []
    for res in [fcfs_res, near_res, mcmf_res]:
        summary_rows.append({
            "scenario": scenario_name,
            "algorithm": res["algorithm"],
            "total_vehicles": res["total_vehicles"],
            "assigned_vehicles": res["assigned_count"],
            "unassigned_vehicles": res["unassigned_count"],
            "allocation_success_rate_pct": res["success_rate_pct"],
            "avg_travel_distance_m": res["avg_travel_distance_m"],
            "total_travel_distance_m": res["total_travel_distance_m"],
            "execution_time_s": res["execution_time_s"]
        })

    df_summary = pd.DataFrame(summary_rows)

    return {
        "scenario": scenario_name,
        "fcfs": fcfs_res,
        "nearest_available": near_res,
        "mcmf": mcmf_res,
        "summary_table": df_summary
    }

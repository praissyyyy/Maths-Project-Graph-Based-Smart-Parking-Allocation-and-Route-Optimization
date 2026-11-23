"""
Interactive Map and Shortest-Path Route Optimization Routes.
Provides GIS Leaflet map visualization and backend Dijkstra/A* routing API.
"""

from flask import Blueprint, render_template, request, jsonify, current_app
import networkx as nx
from models.parking import ParkingFacility
from algorithms.dijkstra import dijkstra_shortest_path
from algorithms.astar import astar_shortest_path

map_bp = Blueprint('map', __name__)


def find_nearest_graph_node(G: nx.DiGraph, lat: float, lon: float) -> str:
    """Finds closest node in the road network to arbitrary coordinates."""
    best_node = None
    min_dist_sq = float('inf')

    for node in G.nodes():
        node_lat = G.nodes[node].get('y', 0.0)
        node_lon = G.nodes[node].get('x', 0.0)
        dist_sq = (node_lat - lat) ** 2 + (node_lon - lon) ** 2
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            best_node = node

    return str(best_node)


@map_bp.route('/map')
def interactive_map():
    """Interactive Leaflet map for Gandhipuram road network and parking facilities."""
    facilities = ParkingFacility.query.all()
    facility_list = [f.to_dict() for f in facilities]

    # Predefined landmark starting points in Gandhipuram for easy testing
    starting_points = [
        {"name": "Cross Cut Road North Entrance", "lat": 11.0210, "lon": 76.9645},
        {"name": "Gandhipuram Central Bus Stand", "lat": 11.0178, "lon": 76.9698},
        {"name": "100 Feet Road Commercial Hub", "lat": 11.0255, "lon": 76.9712},
        {"name": "Bharathiar Road South Junction", "lat": 11.0132, "lon": 76.9665},
        {"name": "Sathyamangalam Highway Circle", "lat": 11.0268, "lon": 76.9615}
    ]

    return render_template(
        'map.html',
        facilities=facility_list,
        starting_points=starting_points,
        study_center={"lat": 11.0182714, "lon": 76.9677744}
    )


@map_bp.route('/api/route', methods=['GET', 'POST'])
def calculate_route():
    """
    Computes shortest-path route on the Gandhipuram road network graph.
    Returns path geometry coordinates, distance, nodes explored, and execution time.
    """
    data = request.get_json(silent=True) or request.args

    facility_id = data.get('facility_id', 'P1')
    algo_name = data.get('algorithm', 'A*').strip()

    try:
        start_lat = float(data.get('start_lat', 11.0210))
        start_lon = float(data.get('start_lon', 76.9645))
    except (ValueError, TypeError):
        start_lat, start_lon = 11.0210, 76.9645

    facility = ParkingFacility.query.get(facility_id)
    if not facility:
        return jsonify({"status": "error", "message": "Facility not found"}), 404

    di_g = current_app.config.get('ROAD_GRAPH')
    if di_g is None:
        return jsonify({"status": "error", "message": "Road network graph is not loaded"}), 500

    # Locate nearest start and target nodes
    start_node = find_nearest_graph_node(di_g, start_lat, start_lon)
    target_node = str(facility.node_id)

    # Run chosen algorithm
    if algo_name.lower() in ['dijkstra', 'dijkstras']:
        path, distance, explored, exec_time = dijkstra_shortest_path(di_g, start_node, target_node)
        algo_label = "Dijkstra's Algorithm"
    else:
        path, distance, explored, exec_time = astar_shortest_path(di_g, start_node, target_node)
        algo_label = "A* Search Algorithm"

    if not path:
        return jsonify({
            "status": "error",
            "message": "No valid route could be found in the directed road graph."
        }), 400

    # Extract [latitude, longitude] polyline sequence for Leaflet
    coordinates = []
    for node in path:
        lat = di_g.nodes[node].get('y', 0.0)
        lon = di_g.nodes[node].get('x', 0.0)
        coordinates.append([lat, lon])

    return jsonify({
        "status": "success",
        "algorithm": algo_label,
        "facility_id": facility.facility_id,
        "facility_name": facility.facility_name,
        "distance_meters": round(distance, 2),
        "distance_km": round(distance / 1000.0, 3),
        "execution_time_ms": round(exec_time * 1000.0, 3),
        "nodes_explored": explored,
        "path_node_count": len(path),
        "coordinates": coordinates,
        "start_point": [start_lat, start_lon],
        "destination_point": [facility.latitude, facility.longitude]
    })

from src.database import supabase
from flask import jsonify, request
import osmnx as ox
import os

graph_path = "sg_bus_network.graphml"  
G = ox.load_graphml(graph_path)



def get_all_flood_events():
    response = supabase.table('flood_events').select('*').execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200

def get_flood_event_by_id():
    flood_event_ids_param = request.args.get('flood_event_ids')
    if not flood_event_ids_param:
        return jsonify({'error': 'flood_event_ids parameter is required'}), 400
    
    try:
        flood_event_ids = [int(id.strip()) for id in flood_event_ids_param.split(',')]
    except ValueError:
        return jsonify({'error': 'flood_event_ids must be a comma-separated list of integers'}), 400

    result = []
    try:
        # Load the graph once, not inside the loop (better performance)
        G = ox.load_graphml("sg_bus_network.graphml")

        for flood_event_id in flood_event_ids:
            # Fetch flood event
            response = supabase.table('flood_events').select('*').eq('flood_id', flood_event_id).execute()
            if not response.data or len(response.data) == 0:
                continue  

            flood_event = response.data[0]
            flood_lat = flood_event.get('geom').get('coordinates')[1]
            flood_lon = flood_event.get('geom').get('coordinates')[0]

            # Find nearest road segment
            nearest_edge = ox.distance.nearest_edges(G, X=[flood_lon], Y=[flood_lat])
            u, v, key = nearest_edge[0]
            edge_data = G.get_edge_data(u, v, key)

            # Get road length in meters
            road_length_m = edge_data.get('length', 0)

            # Convert speed from km/h to m/s
            speed_50_kmh = 50 * 1000 / 3600  # 50 km/h = 13.89 m/s
            speed_20_kmh = 20 * 1000 / 3600  # 20 km/h = 5.56 m/s

            # Calculate travel time in seconds
            time_50_kmh_sec = road_length_m / speed_50_kmh if speed_50_kmh > 0 else None
            time_20_kmh_sec = road_length_m / speed_20_kmh if speed_20_kmh > 0 else None

            # Convert to minutes for easier interpretation
            time_50_kmh_min = round(time_50_kmh_sec / 60, 2) if time_50_kmh_sec else None
            time_20_kmh_min = round(time_20_kmh_sec / 60, 2) if time_20_kmh_sec else None

            result.append({
                'flood_id': flood_event_id,
                'road_name': edge_data.get('name', 'Unknown'),
                'road_type': edge_data.get('highway', 'Unknown'),
                'length_m': round(road_length_m, 2),
                'time_50kmh_min': time_50_kmh_min,
                'time_20kmh_min': time_20_kmh_min,
                'time_travel_delay_min': time_20_kmh_min - time_50_kmh_min if time_50_kmh_min and time_20_kmh_min else None,
                'geometry': str(edge_data.get('geometry'))
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not result:
        return jsonify({'error': 'Flood event(s) not found'}), 404

    return jsonify(result), 200


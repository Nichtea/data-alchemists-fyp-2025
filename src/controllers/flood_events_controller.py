from src.database import supabase
from flask import jsonify, request
import osmnx as ox
import os

# Load road network from GraphML file
graph_path = "sg_bus_network.graphml"  # or sg_car_network.graphml
G = ox.load_graphml(graph_path)



def get_all_flood_events():
    response = supabase.table('flood_events').select('*').execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200

def get_flood_event_by_id(flood_event_id):
    try:
        response = supabase.table('flood_events').select('*').eq('flood_id', flood_event_id).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Flood event not found'}), 404
    
    flood_event = response.data[0]
    flood_lat = flood_event.get('geom').get('coordinates')[1]
    flood_lon = flood_event.get('geom').get('coordinates')[0]

    # Load road network
    G = ox.load_graphml("sg_bus_network.graphml")
    nearest_edge = ox.distance.nearest_edges(G, X=[flood_lon], Y=[flood_lat])

    # Correctly unpack the first result
    u, v, key = nearest_edge[0]  
    edge_data = G.get_edge_data(u, v, key)

    return jsonify({
        'road_name': edge_data.get('name', 'Unknown'),
        'road_type': edge_data.get('highway', 'Unknown'),
        'length_m': edge_data.get('length', None),
        'geometry': str(edge_data.get('geometry'))
    }), 200


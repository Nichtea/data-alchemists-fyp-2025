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
        for flood_event_id in flood_event_ids:
            response = supabase.table('flood_events').select('*').eq('flood_id', flood_event_id).execute()
            if not response.data or len(response.data) == 0:
                continue  

            flood_event = response.data[0]
            flood_lat = flood_event.get('geom').get('coordinates')[1]
            flood_lon = flood_event.get('geom').get('coordinates')[0]
            
            G = ox.load_graphml("sg_bus_network.graphml")
            nearest_edge = ox.distance.nearest_edges(G, X=[flood_lon], Y=[flood_lat])
            u, v, key = nearest_edge[0]
            edge_data = G.get_edge_data(u, v, key)

            result.append({
                'flood_id': flood_event_id,
                'road_name': edge_data.get('name', 'Unknown'),
                'road_type': edge_data.get('highway', 'Unknown'),
                'length_m': edge_data.get('length', None),
                'geometry': str(edge_data.get('geometry'))
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not result:
        return jsonify({'error': 'Flood event(s) not found'}), 404

    return jsonify(result), 200

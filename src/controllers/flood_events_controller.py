from src.database import supabase
from flask import jsonify, request
import osmnx as ox
import os
from collections import Counter
import pandas as pd
import json
from shapely import wkb

flood_events_df = pd.read_csv("flood_events_rows.csv")
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
        df = pd.read_csv("flood_events_rows.csv")
        G = ox.load_graphml("sg_bus_network.graphml")

        for flood_event_id in flood_event_ids:
            flood_event_row = df[df['flood_id'] == flood_event_id]
            if flood_event_row.empty:
                continue  

            try:
                geom_str = flood_event_row.iloc[0]['geom']
                geom = wkb.loads(bytes.fromhex(geom_str)) 
                flood_lat = geom.y
                flood_lon = geom.x
            except Exception as e:
                return jsonify({'error': f"Could not parse geom for flood_id {flood_event_id}: {e}"}), 500

            nearest_edge = ox.distance.nearest_edges(G, X=[flood_lon], Y=[flood_lat])
            u, v, key = nearest_edge[0]
            edge_data = G.get_edge_data(u, v, key)

            road_length_m = edge_data.get('length', 0)

            speed_50_kmh = 50 * 1000 / 3600
            speed_20_kmh = 20 * 1000 / 3600

            time_50_kmh_sec = road_length_m / speed_50_kmh if speed_50_kmh > 0 else None
            time_20_kmh_sec = road_length_m / speed_20_kmh if speed_20_kmh > 0 else None

            time_50_kmh_min = round(time_50_kmh_sec / 60, 2) if time_50_kmh_sec else None
            time_20_kmh_min = round(time_20_kmh_sec / 60, 2) if time_20_kmh_sec else None

            result.append({
                'flood_id': flood_event_id,
                'road_name': edge_data.get('name', 'Unknown'),
                'road_type': edge_data.get('highway', 'Unknown'),
                'length_m': round(road_length_m, 2),
                'time_50kmh_min': time_50_kmh_min,
                'time_20kmh_min': time_20_kmh_min,
                'time_travel_delay_min': (time_20_kmh_min - time_50_kmh_min) if (time_50_kmh_min and time_20_kmh_min) else None,
                'geometry': str(edge_data.get('geometry'))
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not result:
        return jsonify({'error': 'Flood event(s) not found'}), 404

    return jsonify(result), 200

def get_flood_events_by_location():
    try:
        response = supabase.table('flood_events').select('flooded_location').execute()
        
        if not response.data:
            return jsonify({"error": "No flood events found"}), 404

        locations = [event['flooded_location'] for event in response.data if event.get('flooded_location')]
        location_counts = Counter(locations)
        sorted_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)

        result = [{loc: count} for loc, count in sorted_locations]

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


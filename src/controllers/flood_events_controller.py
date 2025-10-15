from src.database import supabase
from flask import jsonify, request, Blueprint
import osmnx as ox
import os
from collections import Counter
import pandas as pd
import json
from datetime import datetime
import requests
from shapely import wkb
from dotenv import load_dotenv

load_dotenv()

ONEMAP_API_KEY = os.getenv("ONEMAP_API_KEY") 
LTA_BUS_ARRIVAL_URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"
LTA_API_KEY = os.getenv("LTA_API_KEY")
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
    
def get_buses_affected_by_floods():
    flood_id = request.args.get("flood_id")

    if not flood_id:
        return jsonify({"error": "flood_id parameter is required"}), 400

    try:
        flood_id = int(flood_id)
    except ValueError:
        return jsonify({"error": "flood_id must be an integer"}), 400

    row = flood_events_df[flood_events_df["flood_id"] == flood_id]
    if row.empty:
        return jsonify({"error": f"No record found for flood_id {flood_id}"}), 404

    latitude = row.iloc[0]["latitude"]
    longitude = row.iloc[0]["longitude"]

    if pd.isna(latitude) or pd.isna(longitude):
        return jsonify({"error": f"Missing coordinates for flood_id {flood_id}"}), 400

    onemap_url = f"https://www.onemap.gov.sg/api/public/nearbysvc/getNearestBusStops?latitude={latitude}&longitude={longitude}&radius_in_meters=1000"
    headers_onemap = {"Authorization": ONEMAP_API_KEY}

    try:
        onemap_resp = requests.get(onemap_url, headers=headers_onemap)
        onemap_resp.raise_for_status()
        onemap_data = onemap_resp.json()
        bus_stop_ids = [str(stop["id"]) for stop in onemap_data if "id" in stop]
    except Exception as e:
        return jsonify({"error": "Failed to fetch OneMap data", "details": str(e)}), 500

    if not bus_stop_ids:
        return jsonify({"flood_id": flood_id, "affected_bus_services": []}), 200

    affected_services = set() 
    headers_lta = {"AccountKey": LTA_API_KEY, "accept": "application/json"}

    for stop_id in bus_stop_ids:
        try:
            lta_resp = requests.get(f"{LTA_BUS_ARRIVAL_URL}?BusStopCode={stop_id}", headers=headers_lta)
            if lta_resp.status_code != 200:
                continue
            lta_data = lta_resp.json()

            services = lta_data.get("Services", [])
            for s in services:
                service_no = s.get("ServiceNo")
                if service_no:
                    affected_services.add(service_no)
        except Exception:
            continue 

    return jsonify({
        "flood_id": flood_id,
        "latitude": latitude,
        "longitude": longitude,
        "affected_bus_services": sorted(list(affected_services))
    }), 200

def get_flood_events_by_date_range():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date parameters are required"}), 400

    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    if start_date > end_date:
        return jsonify({"error": "start_date cannot be after end_date"}), 400

    try:
        flood_events_df['date'] = pd.to_datetime(flood_events_df['date'])
    except Exception:
        return jsonify({"error": "Could not parse flood_date column as datetime"}), 500

    filtered_df = flood_events_df[
        (flood_events_df['date'] >= start_date) &
        (flood_events_df['date'] <= end_date)
    ]

    if filtered_df.empty:
        return jsonify({"message": "No flood events found for the given date range"}), 200

    result = filtered_df.to_dict(orient='records')
    for item in result:
        geom_str = item['geom']
        geom = wkb.loads(bytes.fromhex(geom_str)) 
        flood_lat = geom.y
        flood_lon = geom.x
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

        item['road_name'] = edge_data.get('name', 'Unknown')
        item['road_type'] = edge_data.get('highway', 'Unknown')
        item['length_m'] = round(road_length_m, 2)
        item['time_50kmh_min'] = time_50_kmh_min
        item['time_20kmh_min'] = time_20_kmh_min
        item['time_travel_delay_min'] = (time_20_kmh_min - time_50_kmh_min) if (time_50_kmh_min and time_20_kmh_min) else None
        item['geometry'] = str(edge_data.get('geometry'))
        
    return jsonify(result), 200


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
import geopandas as gpd
from shapely import wkt
from shapely.geometry import LineString, Point


load_dotenv()

ONEMAP_API_KEY = os.getenv("ONEMAP_API_KEY") 
LTA_BUS_ARRIVAL_URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"
ONE_MAP_NEAREST_BUS_STOPS = "https://www.onemap.gov.sg/api/public/nearbysvc/getNearestBusStops"
LTA_API_KEY = os.getenv("LTA_API_KEY")
flood_events_df = pd.read_csv("flood_events_rows.csv")
graph_path = "sg_bus_network.graphml"  
G = ox.load_graphml(graph_path)

stops_path = "stops.txt"
stops_df = pd.read_csv(stops_path)
stops_gdf = gpd.GeoDataFrame(
    stops_df,
    geometry=gpd.points_from_xy(stops_df["stop_lon"], stops_df["stop_lat"]),
    crs="EPSG:4326"
).to_crs("EPSG:3414")

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
            flood_event_row = flood_events_df[flood_events_df['flood_id'] == flood_event_id]
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
        return jsonify({'error': 'flood_id parameter is required'}), 400
    
    try:
        flood_event_ids = [int(id.strip()) for id in flood_id.split(',')]
    except ValueError:
        return jsonify({'error': 'flood_id must be a comma-separated list of integers'}), 400

    all_results = []  

    try:
        for flood_event_id in flood_event_ids:
            flood_event_row = flood_events_df[flood_events_df['flood_id'] == flood_event_id]
            if flood_event_row.empty:
                print(f"⚠️ No flood record for ID {flood_event_id}")
                continue  

            try:
                geom_str = flood_event_row.iloc[0]['geom']
                geom = wkb.loads(bytes.fromhex(geom_str)) 
                flood_lat = geom.y
                flood_lon = geom.x
            except Exception as e:
                return jsonify({'error': f"Could not parse geom for flood_id {flood_event_id}: {e}"}), 500

            print(f"\nFlood ID {flood_event_id}: ({flood_lat}, {flood_lon})")
            print("Graph CRS:", G.graph.get('crs'))

            flood_point = gpd.GeoDataFrame(
                geometry=[Point(flood_lon, flood_lat)],
                crs="EPSG:4326"
            )
            if "crs" in G.graph and G.graph["crs"]:
                flood_point = flood_point.to_crs(G.graph["crs"])
            else:
                print("Warning: Graph CRS not defined; assuming EPSG:4326")

            flood_x = flood_point.geometry.x.iloc[0]
            flood_y = flood_point.geometry.y.iloc[0]

            try:
                nearest_edge = ox.distance.nearest_edges(G, X=[flood_x], Y=[flood_y])
            except Exception as e:
                print(f"Error finding nearest edge for flood_id {flood_event_id}: {e}")
                continue

            print("Nearest edge found:", nearest_edge)

            u, v, key = nearest_edge[0]
            edge_data = G.get_edge_data(u, v, key)
            print(f"Edge data keys: {list(edge_data.keys()) if edge_data else 'None'}")

            geom_obj = edge_data.get('geometry') if edge_data else None

            if geom_obj is None or str(geom_obj).lower() == "none":
                u_data = G.nodes[u]
                v_data = G.nodes[v]
                if "x" in u_data and "y" in u_data and "x" in v_data and "y" in v_data:
                    flood_line = LineString([(u_data["x"], u_data["y"]), (v_data["x"], v_data["y"])])
                    print(f"Edge {u}-{v} missing geometry; reconstructed from nodes.")
                else:
                    print(f"Edge {u}-{v} missing coordinates, skipping.")
                    continue
            else:
                flood_line = geom_obj
                print(f"Using real geometry for edge {u}-{v}")

            distance_threshold_m = 20
            flood_gdf = gpd.GeoDataFrame(geometry=[flood_line], crs="EPSG:4326").to_crs("EPSG:3414")
            flood_buffer = flood_gdf.buffer(distance_threshold_m)

            candidate_stops = stops_gdf[stops_gdf.geometry.within(flood_buffer.unary_union)]
            print(f"Candidate stops near flood {flood_event_id}: {len(candidate_stops)}")

            stops_list = [
                {
                    "stop_code": row["stop_code"],
                    "stop_name": row["stop_name"],
                    "stop_lat": row["stop_lat"],
                    "stop_lon": row["stop_lon"],
                    "distance_m": round(flood_gdf.distance(row.geometry).min(), 2)
                }
                for _, row in candidate_stops.iterrows()
            ]

            affected_services = set() 
            headers_lta = {"AccountKey": LTA_API_KEY, "accept": "application/json"}

            for item in stops_list:
                stop_id = item["stop_code"]
                try:
                    lta_resp = requests.get(
                        f"{LTA_BUS_ARRIVAL_URL}?BusStopCode={stop_id}",
                        headers=headers_lta
                    )
                    if lta_resp.status_code != 200:
                        continue
                    lta_data = lta_resp.json()
                    for s in lta_data.get("Services", []):
                        service_no = s.get("ServiceNo")
                        if service_no:
                            affected_services.add(service_no)
                except Exception as e:
                    print(f"Error querying LTA for stop {stop_id}: {e}")
                    continue

            all_results.append({
                "flood_id": flood_event_id,
                "affected_bus_services": sorted(list(affected_services)),
                "candidate_stops": stops_list  
            })

        return jsonify({"results": all_results}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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


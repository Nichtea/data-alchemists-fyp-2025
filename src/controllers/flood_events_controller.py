from pathlib import Path
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
from shapely import wkb
from shapely.geometry import LineString, Point, mapping
import pickle


load_dotenv()
ROOT_DIR = Path(__file__).resolve().parents[2]
ONEMAP_API_KEY = os.getenv("ONEMAP_API_KEY") 
LTA_BUS_ARRIVAL_URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"
ONE_MAP_NEAREST_BUS_STOPS = "https://www.onemap.gov.sg/api/public/nearbysvc/getNearestBusStops"
LTA_API_KEY = os.getenv("LTA_API_KEY")
flood_events_df = pd.read_csv(ROOT_DIR/"flood_events_rows.csv")
graph_path = ROOT_DIR / "SG_bus_network.graphml"
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

    try:
        valid_floods = flood_events_df[flood_events_df['flood_id'].isin(flood_event_ids)]
        if valid_floods.empty:
            return jsonify({'error': 'Flood event(s) not found'}), 404
        
        flood_data = []
        for _, row in valid_floods.iterrows():
            try:
                geom = wkb.loads(bytes.fromhex(row['geom']))
                flood_data.append({
                    'flood_id': row['flood_id'],
                    'lat': geom.y,
                    'lon': geom.x
                })
            except Exception as e:
                return jsonify({'error': f"Could not parse geom for flood_id {row['flood_id']}: {e}"}), 500

        if not flood_data:
            return jsonify({'error': 'Could not parse geometries'}), 500

        lats = [d['lat'] for d in flood_data]
        lons = [d['lon'] for d in flood_data]
        nearest_edges = ox.distance.nearest_edges(G, X=lons, Y=lats)

        speed_50_ms = 50 * 1000 / 3600
        speed_20_ms = 20 * 1000 / 3600

        result = []
        for i, data in enumerate(flood_data):
            try:
                u, v, key = nearest_edges[i]
                edge_data = G.get_edge_data(u, v, key)

                road_name = edge_data.get('name', 'Unknown')
                road_type = edge_data.get('highway', 'Unknown')
                road_length_m = edge_data.get('length', 0)

                time_50_kmh_min = round((road_length_m / speed_50_ms) / 60, 2)
                time_20_kmh_min = round((road_length_m / speed_20_ms) / 60, 2)

                geometry = edge_data.get('geometry')
                if geometry is None:
                    u_node = G.nodes[u]
                    v_node = G.nodes[v]
                    geometry = LineString([
                        (u_node['x'], u_node['y']),
                        (v_node['x'], v_node['y'])
                    ])
                    print(f"Reconstructed geometry for edge ({u}, {v}, {key}) on {road_name}")

                result.append({
                    'flood_id': data['flood_id'],
                    'road_name': road_name,
                    'road_type': road_type,
                    'length_m': round(road_length_m, 2),
                    'time_50kmh_min': time_50_kmh_min,
                    'time_20kmh_min': time_20_kmh_min,
                    'time_travel_delay_min': round(time_20_kmh_min - time_50_kmh_min, 2),
                    'geometry': geometry.wkt 
                })
            except Exception as e:
                print(f"Warning: could not process flood_id {data['flood_id']}: {e}")
                continue

        if not result:
            return jsonify({'error': 'Could not process any flood events'}), 500

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_flood_events_by_location():
    try:
        if flood_events_df.empty or 'flooded_location' not in flood_events_df.columns:
            return jsonify({"error": "No flood events found or missing 'flooded_location' column"}), 404

        locations = flood_events_df['flooded_location'].dropna().tolist()
        locations = [loc for loc in locations if str(loc).strip() != '']

        location_counts = Counter(locations)
        sorted_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)

        location_coords = {}
        for loc, _ in sorted_locations:
            matching_row = flood_events_df[flood_events_df['flooded_location'] == loc].iloc[0]
            
            if 'geom' in matching_row and pd.notna(matching_row['geom']):
                try:
                    geom_str = matching_row['geom']
                    geom = wkb.loads(bytes.fromhex(geom_str))
                    location_coords[loc] = (geom.y, geom.x)  # (lat, lon)
                except Exception as e:
                    print(f"Warning: could not parse geom for {loc}: {e}")

        if location_coords:
            lats = [coord[0] for coord in location_coords.values()]
            lons = [coord[1] for coord in location_coords.values()]
            locs_list = list(location_coords.keys())
            
            nearest_edges = ox.distance.nearest_edges(G, X=lons, Y=lats)
            
            result = []
            for i, loc in enumerate(locs_list):
                count = location_counts[loc]
                lat, lon = location_coords[loc]
                
                try:
                    u, v, key = nearest_edges[i]
                    edge_data = G.get_edge_data(u, v, key)
                    road_length_m = edge_data.get('length', 0)

                    speed_50_kmh = 50 * 1000 / 3600  # m/s
                    speed_20_kmh = 20 * 1000 / 3600  # m/s

                    time_50_kmh_min = round((road_length_m / speed_50_kmh) / 60, 2)
                    time_20_kmh_min = round((road_length_m / speed_20_kmh) / 60, 2)

                    result.append({
                        "location": loc,
                        "count": count,
                        "latitude": lat,
                        "longitude": lon,
                        "road_length": road_length_m,
                        'time_50kmh_min': time_50_kmh_min,
                        'time_20kmh_min': time_20_kmh_min,
                        'time_travel_delay_min': round(time_20_kmh_min - time_50_kmh_min, 2)
                    })
                except Exception as e:
                    print(f"Warning: could not process edge for {loc}: {e}")
        else:
            result = []

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
        valid_floods = flood_events_df[flood_events_df['flood_id'].isin(flood_event_ids)]
        
        if valid_floods.empty:
            return jsonify({"results": []}), 200
        
        flood_coords = []
        flood_ids_valid = []
        
        for _, row in valid_floods.iterrows():
            try:
                geom = wkb.loads(bytes.fromhex(row['geom']))
                flood_coords.append((geom.y, geom.x))  # (lat, lon)
                flood_ids_valid.append(row['flood_id'])
            except Exception as e:
                print(f"Could not parse geom for flood_id {row['flood_id']}: {e}")
        
        if not flood_coords:
            return jsonify({"results": []}), 200
        
        lats, lons = zip(*flood_coords)
        flood_points = gpd.GeoDataFrame(
            geometry=[Point(lon, lat) for lat, lon in flood_coords],
            crs="EPSG:4326"
        )
        
        if "crs" in G.graph and G.graph["crs"]:
            flood_points = flood_points.to_crs(G.graph["crs"])
        
        flood_xs = flood_points.geometry.x.tolist()
        flood_ys = flood_points.geometry.y.tolist()
        
        nearest_edges = ox.distance.nearest_edges(G, X=flood_xs, Y=flood_ys)
        
        distance_threshold_m = 20
        
        stops_gdf_3414 = stops_gdf.to_crs("EPSG:3414")
        
        headers_lta = {"AccountKey": LTA_API_KEY, "accept": "application/json"}
        
        for i, flood_event_id in enumerate(flood_ids_valid):
            print(f"\nFlood ID {flood_event_id}: ({lats[i]}, {lons[i]})")
            
            try:
                u, v, key = nearest_edges[i]
                edge_data = G.get_edge_data(u, v, key)
                
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
                
                flood_gdf = gpd.GeoDataFrame(geometry=[flood_line], crs="EPSG:4326").to_crs("EPSG:3414")
                flood_buffer = flood_gdf.buffer(distance_threshold_m).unary_union
                
                candidate_stops = stops_gdf_3414[stops_gdf_3414.geometry.within(flood_buffer)]
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
                stop_codes = [item["stop_code"] for item in stops_list]
                
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                def fetch_bus_services(stop_id):
                    try:
                        lta_resp = requests.get(
                            f"{LTA_BUS_ARRIVAL_URL}?BusStopCode={stop_id}",
                            headers=headers_lta,
                            timeout=5 
                        )
                        if lta_resp.status_code == 200:
                            lta_data = lta_resp.json()
                            return [s.get("ServiceNo") for s in lta_data.get("Services", []) if s.get("ServiceNo")]
                    except Exception as e:
                        print(f"Error querying LTA for stop {stop_id}: {e}")
                    return []
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = {executor.submit(fetch_bus_services, stop_id): stop_id for stop_id in stop_codes}
                    for future in as_completed(futures):
                        services = future.result()
                        affected_services.update(services)
                
                all_results.append({
                    "flood_id": flood_event_id,
                    "affected_bus_services": sorted(list(affected_services)),
                    "candidate_stops": stops_list
                })
                
            except Exception as e:
                print(f"Error processing flood_id {flood_event_id}: {e}")
                continue
        
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

    lats = []
    lons = []
    valid_indices = []
    
    for idx, row in filtered_df.iterrows():
        try:
            geom = wkb.loads(bytes.fromhex(row['geom']))
            lats.append(geom.y)
            lons.append(geom.x)
            valid_indices.append(idx)
        except Exception as e:
            print(f"Warning: could not parse geom at index {idx}: {e}")
    
    if valid_indices:
        nearest_edges = ox.distance.nearest_edges(G, X=lons, Y=lats)
        
        speed_50_ms = 50 * 1000 / 3600 
        speed_20_ms = 20 * 1000 / 3600  
        
        result = []
        for i, idx in enumerate(valid_indices):
            row = filtered_df.loc[idx]
            item = row.to_dict()
            
            try:
                u, v, key = nearest_edges[i]
                edge_data = G.get_edge_data(u, v, key)
                
                road_length_m = edge_data.get('length', 0)
                
                time_50_kmh_min = round((road_length_m / speed_50_ms) / 60, 2)
                time_20_kmh_min = round((road_length_m / speed_20_ms) / 60, 2)
                
                item['road_name'] = edge_data.get('name', 'Unknown')
                item['road_type'] = edge_data.get('highway', 'Unknown')
                item['length_m'] = round(road_length_m, 2)
                item['time_50kmh_min'] = time_50_kmh_min
                item['time_20kmh_min'] = time_20_kmh_min
                item['time_travel_delay_min'] = round(time_20_kmh_min - time_50_kmh_min, 2)
                item['geometry'] = str(edge_data.get('geometry'))
                
                result.append(item)
            except Exception as e:
                print(f"Warning: could not process edge at index {idx}: {e}")
    else:
        result = []
        
    return jsonify(result), 200

def get_critical_road_segments_near_flood():
    try:
        flood_id = request.args.get("flood_id")
        buffer_m = float(request.args.get("buffer_m", 50))

        if not flood_id:
            return jsonify({"error": "Missing flood_id"}), 400

        flood = flood_events_df[flood_events_df["flood_id"] == int(flood_id)]
        if flood.empty:
            return jsonify({"error": f"Flood {flood_id} not found"}), 404

        flood_point = wkb.loads(bytes.fromhex(flood.iloc[0]["geom"]))

        with open(f"Gcar_edge_closeness_centrality.pkl", "rb") as f:
            centrality_data = pickle.load(f)

        edges = ox.graph_to_gdfs(G, nodes=False).reset_index().to_crs(epsg=3414)
        edges["centrality"] = edges.apply(
            lambda r: centrality_data.get((r["u"], r["v"], r["key"]), 0), axis=1
        )

        flood_gdf = gpd.GeoDataFrame([{"geometry": flood_point}], crs="EPSG:4326").to_crs(epsg=3414)
        flood_buffer = flood_gdf.buffer(buffer_m).iloc[0]

        edges_sindex = edges.sindex
        matches = edges.iloc[list(edges_sindex.intersection(flood_buffer.bounds))]
        nearby_edges = matches[matches.intersects(flood_buffer)]

        if nearby_edges.empty:
            return jsonify({"message": "No critical roads near flood"}), 200

        nearby_edges["norm_centrality"] = nearby_edges["centrality"] / nearby_edges["centrality"].max()
        critical_subset = nearby_edges.sort_values(by="centrality", ascending=False).head(10)

        results = [{
            "road_name": row.get("name", "Unnamed Road"),
            "road_type": row.get("highway", "Unknown"),
            "length_m": round(row.get("length", 0), 2),
            "centrality_score": round(row.get("centrality", 0), 6),
            "geometry": mapping(row["geometry"])
        } for _, row in critical_subset.iterrows()]

        count_critical_segments = len(critical_subset)

        return jsonify({
            "flood_id": int(flood_id),
            "buffer_m": buffer_m,
            "flood_point": mapping(flood_point),
            "count_critical_segments": count_critical_segments,
            "critical_segments": results
        }), 200

    except FileNotFoundError:
        return jsonify({"error": "Centrality file not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def get_unique_flood_events_by_location():
    try:
        if flood_events_df.empty or 'flooded_location' not in flood_events_df.columns:
            return jsonify({"error": "No flood events found or missing 'flooded_location' column"}), 404

        unique_locations_df = flood_events_df[
            flood_events_df['flooded_location'].notna() &
            (flood_events_df['flooded_location'].str.strip() != '')
        ].drop_duplicates(subset=['flooded_location'], keep='first')

        if unique_locations_df.empty:
            return jsonify([]), 200

        flood_data = []
        for _, row in unique_locations_df.iterrows():
            try:
                geom = wkb.loads(bytes.fromhex(row['geom']))
                flood_data.append({
                    'flood_id': row['flood_id'],
                    'location': row['flooded_location'],
                    'lat': geom.y,
                    'lon': geom.x
                })
            except Exception as e:
                print(f"Warning: could not parse geom for flood_id {row['flood_id']}: {e}")

        if not flood_data:
            return jsonify([]), 200

        lats = [d['lat'] for d in flood_data]
        lons = [d['lon'] for d in flood_data]

        nearest_edges = ox.distance.nearest_edges(G, X=lons, Y=lats)

        speed_50_ms = 50 * 1000 / 3600  # m/s
        speed_20_ms = 20 * 1000 / 3600  # m/s
        speed_diff_per_meter = (1 / speed_20_ms - 1 / speed_50_ms) / 60 

        result = []
        for i, data in enumerate(flood_data):
            try:
                u, v, key = nearest_edges[i]
                edge_data = G.get_edge_data(u, v, key)
                road_length_m = edge_data.get('length', 0)

                time_travel_delay_min = round(road_length_m * speed_diff_per_meter, 2)

                result.append({
                    "flood_id": data['flood_id'],
                    "flooded_location": data['location'],
                    "latitude": data['lat'],
                    "longitude": data['lon'],
                    "time_travel_delay_min": time_travel_delay_min
                })

            except Exception as e:
                print(f"Warning: nearest edge error for flood_id {data['flood_id']}: {e}")

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
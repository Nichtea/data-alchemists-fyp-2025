from src.database import supabase
from flask import jsonify, request, Blueprint
import googlemaps
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
from src.utils.onemap_auth import get_valid_token

load_dotenv()

one_map_route = Blueprint('one_map_route', __name__)
ONEMAP_BASE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"
gmaps = googlemaps.Client(os.getenv("GOOGLE_MAPS_API_KEY"))

# def get_all_car_trips_flooded():
#     response = supabase.table('car_trips_flooded').select('*').execute()
#     if not response.data:  
#         return jsonify({"message": "No records found"}), 404

#     return jsonify(response.data), 200

# def get_car_trip_flooded_by_id():
#     car_trip_ids_param = request.args.get('car_trip_ids')  
#     if not car_trip_ids_param:
#         return jsonify({'error': 'car_trip_ids parameter is required'}), 400

#     try:
#         car_trip_ids = [int(id.strip()) for id in car_trip_ids_param.split(',')]
#     except ValueError:
#         return jsonify({'error': 'car_trip_ids must be a comma-separated list of integers'}), 400
    
#     try:
#         response = supabase.table('car_trips_flooded').select('*').in_('car_trip_id', car_trip_ids).execute()
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

#     if not response.data or len(response.data) == 0:
#         return jsonify({'error': 'Trips not found'}), 404

#     return jsonify(response.data), 200

# def get_all_car_trips_dry():
#     response = supabase.table("car_trips_dry").select("*").execute()
#     if not response.data:  
#         return jsonify({"message": "No records found"}), 404

#     return jsonify(response.data), 200
    
# def get_all_car_trips_dry_by_id():
#     car_trip_ids_param = request.args.get('car_trip_ids')  
#     if not car_trip_ids_param:
#         return jsonify({'error': 'car_trip_ids parameter is required'}), 400

#     try:
#         car_trip_ids = [int(id.strip()) for id in car_trip_ids_param.split(',')]
#     except ValueError:
#         return jsonify({'error': 'car_trip_ids must be a comma-separated list of integers'}), 400
    
#     try:
#         response = supabase.table('car_trips_dry').select('*').in_('car_trip_id', car_trip_ids).execute()
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

#     if not response.data or len(response.data) == 0:
#         return jsonify({'error': 'Trips not found'}), 404

#     return jsonify(response.data), 200

def get_all_car_trips_by_id():
    car_trip_ids_param = request.args.get('car_trip_ids')  
    if not car_trip_ids_param:
        return jsonify({'error': 'car_trip_ids parameter is required'}), 400

    try:
        car_trip_ids = [int(id.strip()) for id in car_trip_ids_param.split(',')]
    except ValueError:
        return jsonify({'error': 'car_trip_ids must be a comma-separated list of integers'}), 400
    
    try:
        response = supabase.table('car_trips').select('*').in_('car_trip_id', car_trip_ids).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Trips not found'}), 404

    return jsonify(response.data), 200

def get_onemap_car_route():
    start_address = request.args.get('start_address')
    end_address = request.args.get('end_address')
    if not start_address or not end_address:
        return jsonify({"error": "start_address and end_address are required"}), 400

    token = get_valid_token()
    if not token:
        return jsonify({"error": "OneMap API key missing. Could not retrieve OneMap token."}), 500

    try:
        from concurrent.futures import ThreadPoolExecutor
        
        def geocode_address(address):
            result = gmaps.geocode(address)
            if not result:
                return None
            return {
                'lat': result[0]['geometry']['location']['lat'],
                'lon': result[0]['geometry']['location']['lng']
            }
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_start = executor.submit(geocode_address, start_address)
            future_end = executor.submit(geocode_address, end_address)
            
            start_coords = future_start.result()
            end_coords = future_end.result()
        
        if not start_coords:
            return jsonify({"error": "Start address not found"}), 404
        if not end_coords:
            return jsonify({"error": "End address not found"}), 404
        
        start_lat, start_lon = start_coords['lat'], start_coords['lon']
        end_lat, end_lon = end_coords['lat'], end_coords['lon']
        
        print(f"Start: {start_lat}, {start_lon}; End: {end_lat}, {end_lon}")

        tolerance = 0.0018  # 180m radius
        
        def fetch_onemap():
            params = {
                "start": f"{start_lat},{start_lon}",
                "end": f"{end_lat},{end_lon}",
                "routeType": "drive"
            }
            headers = {"Authorization": token}
            response = requests.get(ONEMAP_BASE_URL, headers=headers, params=params, timeout=15)
            return response
        
        def fetch_supabase():
            return supabase.table("car_trips").select("*") \
                .gte("start_lat", start_lat - tolerance) \
                .lte("start_lat", start_lat + tolerance) \
                .gte("start_lon", start_lon - tolerance) \
                .lte("start_lon", start_lon + tolerance) \
                .gte("end_lat", end_lat - tolerance) \
                .lte("end_lat", end_lat + tolerance) \
                .gte("end_lon", end_lon - tolerance) \
                .lte("end_lon", end_lon + tolerance) \
                .execute()
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_onemap = executor.submit(fetch_onemap)
            future_supabase = executor.submit(fetch_supabase)
            
            response = future_onemap.result()
            supabase_response = future_supabase.result()
        
        if response.status_code != 200:
            return jsonify({
                "error": "OneMap API request failed",
                "status_code": response.status_code,
                "details": response.text
            }), response.status_code
        
        data = response.json()
        data['overall_route_status'] = "clear"
        
        if supabase_response.data and len(supabase_response.data) > 0:
            trip = supabase_response.data[0]
            data['overall_route_status'] = "flooded"
            data["time_travel_simulation"] = {
                "81kph_total_duration": trip.get("81kph_total_duration"),
                "72kph_total_duration": trip.get("72kph_total_duration"),
                "45kph_total_duration": trip.get("45kph_total_duration"),
                "20kph_total_duration": trip.get("20kph_total_duration"),
                "10kph_total_duration": trip.get("10kph_total_duration"),
                "5kph_total_duration": trip.get("5kph_total_duration"),
                "90kph_total_duration": trip.get("90kph_total_duration"),
            }
        
        return jsonify(data), 200

    except requests.exceptions.Timeout:
        return jsonify({"error": "OneMap API request timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500
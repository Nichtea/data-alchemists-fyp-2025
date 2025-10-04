from src.database import supabase
from flask import jsonify, request, Blueprint
import googlemaps
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

one_map_route = Blueprint('one_map_route', __name__)
ONEMAP_BASE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"
ONEMAP_API_KEY = os.getenv("ONEMAP_API_KEY") 
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

    start_location = gmaps.geocode(start_address)
    if not start_location:
        return jsonify({"error": "Start address not found"}), 404
    start_lat = start_location[0]['geometry']['location']['lat']
    start_lon = start_location[0]['geometry']['location']['lng']

    end_location = gmaps.geocode(end_address)
    if not end_location:
        return jsonify({"error": "End address not found"}), 404
    end_lat = end_location[0]['geometry']['location']['lat']
    end_lon = end_location[0]['geometry']['location']['lng']

    print(f"Start: {start_lat}, {start_lon}; End: {end_lat}, {end_lon}")

    if not (start_lat and start_lon and end_lat and end_lon):
        return jsonify({
            "error": "start_lat, start_lon, end_lat, and end_lon are required."
        }), 400

    if not ONEMAP_API_KEY:
        return jsonify({"error": "OneMap API key missing. Please set ONEMAP_API_KEY environment variable."}), 500

    params = {
        "start": f"{start_lat},{start_lon}",
        "end": f"{end_lat},{end_lon}",
        "routeType": "drive"
    }

    headers = {"Authorization": ONEMAP_API_KEY}

    try:
        response = requests.get(ONEMAP_BASE_URL, headers=headers, params=params, timeout=15)
        data = response.json()  

        if response.status_code != 200:
            return jsonify({
                "error": "OneMap API request failed",
                "status_code": response.status_code,
                "details": response.text
            }), response.status_code
        
        data['overall_route_status'] = "clear"

        tolerance = 0.0018  # 180m radius, adjust as needed
        supabase_response = supabase.table("car_trips").select("*") \
            .gte("start_lat", start_lat - tolerance) \
            .lte("start_lat", start_lat + tolerance) \
            .gte("start_lon", start_lon - tolerance) \
            .lte("start_lon", start_lon + tolerance) \
            .gte("end_lat", end_lat - tolerance) \
            .lte("end_lat", end_lat + tolerance) \
            .gte("end_lon", end_lon - tolerance) \
            .lte("end_lon", end_lon + tolerance) \
            .execute()

        if supabase_response.data and len(supabase_response.data) > 0:
            trip = supabase_response.data[0]  # take first match
            time_travel_simulation = {
                "81kph_total_duration": trip.get("81kph_total_duration"),
                "72kph_total_duration": trip.get("72kph_total_duration"),
                "45kph_total_duration": trip.get("45kph_total_duration"),
                "20kph_total_duration": trip.get("20kph_total_duration"),
                "10kph_total_duration": trip.get("10kph_total_duration"),
                "5kph_total_duration": trip.get("5kph_total_duration"),
                "90kph_total_duration": trip.get("90kph_total_duration"),
            }
            data['overall_route_status'] = "flooded"
            data["time_travel_simulation"] = time_travel_simulation

        return jsonify(data), 200

    except requests.exceptions.Timeout:
        return jsonify({"error": "OneMap API request timed out"}), 504

    except Exception as e:
        return jsonify({"error": str(e)}), 500
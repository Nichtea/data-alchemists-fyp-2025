from src.database import supabase
from flask import jsonify, request, Blueprint
import os
import requests
import json
import googlemaps
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

one_map_route = Blueprint('one_map_route', __name__)
ONEMAP_BASE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"
ONEMAP_API_KEY = os.getenv("ONEMAP_API_KEY") 
gmaps = googlemaps.Client(os.getenv("GOOGLE_MAPS_API_KEY"))

def get_bus_trip_segment_by_stop(start_stop, end_stop):
    try:
        response = supabase.table('bus_trip_segment').select('*').eq('origin_stop_id', start_stop).eq('destination_stop_id', end_stop).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Bus trip segment not found'}), 404

    return jsonify(response.data[0]), 200   


def get_onemap_route():
    start_address = request.args.get('start_address')
    end_address = request.args.get('end_address')
    if not start_address or not end_address:
        return jsonify({"error": "start_address and end_address are required"}), 400

    start_location = gmaps.geocode(start_address)
    if not start_location:
        return jsonify({"error": "Start address not found"}), 404
    start_lat_raw = start_location[0]['geometry']['location']['lat']
    start_lon_raw = start_location[0]['geometry']['location']['lng']

    end_location = gmaps.geocode(end_address)
    if not end_location:
        return jsonify({"error": "End address not found"}), 404
    end_lat_raw = end_location[0]['geometry']['location']['lat']
    end_lon_raw = end_location[0]['geometry']['location']['lng']

    start_lat = start_lat_raw
    start_lon = start_lon_raw
    end_lat = end_lat_raw
    end_lon = end_lon_raw

    date = request.args.get('date', datetime.today().strftime('%m-%d-%Y'))
    time = request.args.get('time', '07:00:00')  # Default 7 AM

    if not (start_lat and start_lon and end_lat and end_lon):
        return jsonify({
            "error": "start_lat, start_lon, end_lat, and end_lon are required."
        }), 400

    if not ONEMAP_API_KEY:
        return jsonify({"error": "OneMap API key missing. Please set ONEMAP_API_KEY environment variable."}), 500

    params = {
        "start": f"{start_lat},{start_lon}",
        "end": f"{end_lat},{end_lon}",
        "routeType": "pt",          # Public transport mode
        "date": date,
        "time": time,
        "mode": "BUS",          # Transit includes bus/train/mrt
        #"maxWalkDistance": "1000",  # Max walking distance in meters
        "numItineraries": "3"       # Number of route options to return
    }

    headers = {
        "Authorization": ONEMAP_API_KEY
    }

    try:
        response = requests.get(ONEMAP_BASE_URL, headers=headers, params=params, timeout=15)
        data = response.json()  
        for itinerary in data.get("plan", {}).get("itineraries", []):
            for leg in itinerary.get("legs", []):
                if leg.get("mode") == "BUS":
                    start_stop_id = leg.get("from", {}).get("stopCode")
                    end_stop_id = leg.get("to", {}).get("stopCode")
                    if start_stop_id and end_stop_id:
                        delay = get_bus_trip_segment_by_stop(start_stop_id, end_stop_id)
                        delay_str = delay[0].data.decode("utf-8")
                        delay_json = json.loads(delay_str)
                        leg['overall_bus_route_status'] = "clear"
                        if "error" not in delay_json:
                            leg["non_flooded_bus_duration"] = delay_json.get("non_flooded_bus_duration"),
                            leg["5kmh_flooded_bus_duration"]= delay_json.get('5kmh_flooded_bus_duration'),
                            leg["12kmh_flooded_bus_duration"]= delay_json.get('12kmh_flooded_bus_duration'),
                            leg["30kmh_flooded_bus_duration"]= delay_json.get('30kmh_flooded_bus_duration'),
                            leg["48kmh_flooded_bus_duration"]= delay_json.get('48kmh_flooded_bus_duration')
                            leg['overall_bus_route_status'] = "flooded"
                            print("Added time travel delay info")

        if response.status_code != 200:
            return jsonify({
                "error": "OneMap API request failed",
                "status_code": response.status_code,
                "details": response.text
            }), response.status_code

        return jsonify(data), 200

    except requests.exceptions.Timeout:
        return jsonify({"error": "OneMap API request timed out"}), 504

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get_all_bus_stops():
    response = supabase.table('bus_stops').select('*').execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200

def get_bus_stop_by_stop_code(stop_code):
    try:
        response = supabase.table('bus_stops').select('*').eq('stop_code', stop_code).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Bus stop not found'}), 404

    return jsonify(response.data[0]), 200

def get_all_bus_trip():
    response = supabase.table('bus_trip').select('*').execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200

def get_bus_trip_by_id(bus_trip_id):
    try:
        response = supabase.table('bus_trip').select('*').eq('bus_trip_id', bus_trip_id).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Bus trip not found'}), 404

    return jsonify(response.data[0]), 200

def get_all_bus_trip_segment():
    response = supabase.table('bus_trip_segment').select('*').execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200

def get_bus_trip_segment_by_id(bus_trip_id):
    try:
        response = supabase.table('bus_trip_segment').select('*').eq('bus_trip_id', bus_trip_id).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Bus trip segment not found'}), 404

    return jsonify(response.data[0]), 200

def get_bus_trip_segment_delay():
    start_stop = request.args.get('start_stop')
    end_stop = request.args.get('end_stop')

    if not start_stop or not end_stop:
        return jsonify({
            "error": "Missing required parameters: start_stop and end_stop are required."
        }), 400

    try:
        response = supabase.table("bus_trip_segment") \
            .select("*") \
            .eq("origin_stop_id", start_stop) \
            .eq("destination_stop_id", end_stop) \
            .limit(1) \
            .execute()

        if hasattr(response, 'error') and response.error:
            return jsonify({
                "error": response.error.message
            }), 500

        data = response.data

        if not data or len(data) == 0:
            return jsonify({
                "error": "No matching bus trip segment found for the given stops."
            }), 404
        
        segment = data[0]

        return jsonify({
            "start_stop": segment.get("origin_stop_id"),
            "end_stop": segment.get("destination_stop_id"),
            "non_flooded_bus_duration": segment.get("non_flooded_bus_duration"),
            "origin_stop_id": segment.get("origin_stop_id"),
            "destination_stop_id": segment.get("destination_stop_id"),
            "flooded_durations": {
                "5kmh": segment.get('5kmh_flooded_bus_duration'),
                "12kmh": segment.get('12kmh_flooded_bus_duration'),
                "30kmh": segment.get('30kmh_flooded_bus_duration'),
                "48kmh": segment.get('48kmh_flooded_bus_duration')
            },
            "delays": {
                "5kmh": segment.get('5kmh_flooded_bus_duration') - segment.get('non_flooded_bus_duration'),
                "12kmh": segment.get('12kmh_flooded_bus_duration') - segment.get('non_flooded_bus_duration'),
                "30kmh": segment.get('30kmh_flooded_bus_duration') - segment.get('non_flooded_bus_duration'),
                "48kmh": segment.get('48kmh_flooded_bus_duration') - segment.get('non_flooded_bus_duration')
            }
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


def get_bus_trip_delay():
    try:
        stop_id = request.args.get('stop_id')
        trip_end_area_code = request.args.get('trip_end_area_code')

        if not stop_id or not trip_end_area_code:
            return jsonify({"error": "stop_id and trip_end_area_code are required"}), 400

        stop_response = supabase.table('bus_stops').select('stop_lat, stop_lon').eq('stop_id', stop_id).execute()
        if not stop_response.data:
            return jsonify({"error": "Start bus stop not found"}), 404

        stop_lat = stop_response.data[0]['stop_lat']
        stop_lon = stop_response.data[0]['stop_lon']
        print(f"Start Stop - Lat: {stop_lat}, Lon: {stop_lon}")

        trips_response = supabase.table('bus_trip').select('*').eq('start_lat', stop_lat).eq('end_area_code', trip_end_area_code).execute()
        print(f"Trips Found: {len(trips_response.data) if trips_response.data else 0}")

        if not trips_response.data:
            return jsonify({"error": "No bus trips found for given criteria"}), 404

        trips = trips_response.data
        results = []

        for trip in trips:
            bus_trip_id = trip['bus_trip_id']

            segments_response = supabase.table('bus_trip_segment').select('*').eq('bus_trip_id', bus_trip_id).execute()
            segment_data = segments_response.data if segments_response.data else []

            trip_result = {
                "bus_trip_id": bus_trip_id,
                "start_lat": trip['start_lat'],
                "start_lon": trip['start_lon'],
                "end_lat": trip['end_lat'],
                "end_lon": trip['end_lon'],
                "non_flooded_total_duration": trip['non_flooded_total_duration'],
                "non_flooded_total_bus_duration": trip['non_flooded_total_bus_duration'],
                "flooded_total_durations": {
                    "5kmh": trip['5kmh_total_duration'],
                    "12kmh": trip['12kmh_total_duration'],
                    "30kmh": trip['30kmh_total_duration'],
                    "48kmh": trip['48kmh_total_duration']
                },
                "flooded_total_bus_durations": {
                    "5kmh": trip['5kmh_total_bus_duration'],
                    "12kmh": trip['12kmh_total_bus_duration'],
                    "30kmh": trip['30kmh_total_bus_duration'],
                    "48kmh": trip['48kmh_total_bus_duration']
                },
                "overall_total_delay": {
                    "5kmh": trip['5kmh_total_duration'] - trip['non_flooded_total_duration'],
                    "12kmh": trip['12kmh_total_duration'] - trip['non_flooded_total_duration'],
                    "30kmh": trip['30kmh_total_duration'] - trip['non_flooded_total_duration'],
                    "48kmh": trip['48kmh_total_duration'] - trip['non_flooded_total_duration']
                },
                "overall_bus_delay": {
                    "5kmh": trip['5kmh_total_bus_duration'] - trip['non_flooded_total_bus_duration'],
                    "12kmh": trip['12kmh_total_bus_duration'] - trip['non_flooded_total_bus_duration'],
                    "30kmh": trip['30kmh_total_bus_duration'] - trip['non_flooded_total_bus_duration'],
                    "48kmh": trip['48kmh_total_bus_duration'] - trip['non_flooded_total_bus_duration']
                },
                "segments": []
            }

            for seg in segment_data:
                trip_result["segments"].append({
                    "segment_id": seg['segment'],
                    "non_flooded_bus_duration": seg['non_flooded_bus_duration'],
                    "origin_stop_id": seg['origin_stop_id'],
                    "destination_stop_id": seg['destination_stop_id'],
                    "flooded_durations": {
                        "5kmh": seg['5kmh_flooded_bus_duration'],
                        "12kmh": seg['12kmh_flooded_bus_duration'],
                        "30kmh": seg['30kmh_flooded_bus_duration'],
                        "48kmh": seg['48kmh_flooded_bus_duration']
                    },
                    "delays": {
                        "5kmh": seg['5kmh_flooded_bus_duration'] - seg['non_flooded_bus_duration'],
                        "12kmh": seg['12kmh_flooded_bus_duration'] - seg['non_flooded_bus_duration'],
                        "30kmh": seg['30kmh_flooded_bus_duration'] - seg['non_flooded_bus_duration'],
                        "48kmh": seg['48kmh_flooded_bus_duration'] - seg['non_flooded_bus_duration']
                    }
                })

            results.append(trip_result)

        return jsonify({"trips": results}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def get_unique_end_area_codes():
    AREA_CODES = {
    "Ang Mo Kio": "AM",
    "Bedok": "BD",
    "Bukit Batok": "BK",
    "Boon Lay": "BL",
    "Bukit Merah": "BM",
    "Bukit Panjang": "BP",
    "Bishan": "BS",
    "Bukit Timah": "BT",
    "Changi": "CH",
    "Choa Chu Kang": "CK",
    "Clementi": "CL",
    "Downtown": "DT",
    "Gul Circle": "GL",
    "Hougang": "HG",
    "Jurong East": "JE",
    "Jurong West": "JW",
    "Kallang": "KL",
    "Loyang/Kembangan": "LK",
    "Mandai": "MD",
    "Marine Parade": "ME",
    "Marsiling": "MP",
    "Marsiling/Sembawang": "MS",
    "Muara": "MU",
    "Newton": "NT",
    "Novena": "NV",
    "Outram": "OR",
    "Other": "OT",
    "Punggol": "PG",
    "Pasir Laba": "PL",
    "Pioneer": "PN",
    "Pasir Ris": "PR",
    "Queenstown": "QT",
    "Raffles City/CBD": "RC",
    "Riverside": "RV",
    "Sembawang": "SB",
    "Seletar": "SE",
    "Siglap": "SG",
    "Sengkang": "SK",
    "Simei": "SL",
    "Serangoon": "SR",
    "Sungei Kadut": "SV",
    "Tampines": "TH",
    "Tengah": "TM",
    "Tanjong Pagar": "TN",
    "Toa Payoh": "TP",
    "Tuas": "TS",
    "West Coast": "WC",
    "Woodlands": "WD",
    "Yishun": "YS"
    }

    return jsonify(AREA_CODES), 200
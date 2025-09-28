from src.database import supabase
from flask import jsonify, request

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
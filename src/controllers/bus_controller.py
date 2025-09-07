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

def get_bus_trip_segment_by_id(segment_id):
    try:
        response = supabase.table('bus_trip_segment').select('*').eq('bus_trip_id', segment_id).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Bus trip segment not found'}), 404

    return jsonify(response.data[0]), 200
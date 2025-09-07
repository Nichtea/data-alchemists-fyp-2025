from src.database import supabase
from flask import jsonify, request

def get_all_car_trips_flooded():
    response = supabase.table('car_trips_flooded').select('*').execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200

def get_car_trip_flooded_by_id(car_trip_id):
    try:
        response = supabase.table('car_trips_flooded').select('*').eq('car_trip_id', car_trip_id).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Trip not found'}), 404

    return jsonify(response.data[0]), 200


def get_all_car_trips_dry():
    response = supabase.table("car_trips_dry").select("*").execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200
    
def get_all_car_trips_dry_by_id(car_trip_id):
    try:
        response = supabase.table('car_trips_flooded').select('*').eq('car_trip_id', car_trip_id).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Trip not found'}), 404

    return jsonify(response.data[0]), 200
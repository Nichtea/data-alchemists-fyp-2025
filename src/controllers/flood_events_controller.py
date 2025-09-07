from src.database import supabase
from flask import jsonify, request

def get_all_flood_events():
    response = supabase.table('flood_events').select('*').execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200

def get_flood_event_by_id(flood_event_id):
    try:
        response = supabase.table('flood_events').select('*').eq('flood_id', flood_event_id).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Flood event not found'}), 404

    return jsonify(response.data[0]), 200
from src.database import supabase
from flask import jsonify, request

def get_all_road_max_traffic_flow():
    response = supabase.table('road_max_traffic_flow').select('*').execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200

def get_road_max_traffic_flow_by_id(road_id):
    try:
        response = supabase.table('road_max_traffic_flow').select('*').eq('road_id', road_id).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Road not found'}), 404

    return jsonify(response.data[0]), 200
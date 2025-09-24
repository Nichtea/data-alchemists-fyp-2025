from src.database import supabase
from flask import jsonify, request

def get_all_road_max_traffic_flow():
    response = supabase.table('road_max_traffic_flow').select('*').execute()
    if not response.data:  
        return jsonify({"message": "No records found"}), 404

    return jsonify(response.data), 200

def get_road_max_traffic_flow_by_id():
    road_ids_param = request.args.get('road_ids')
    if not road_ids_param:
        return jsonify({'error': 'road_ids parameter is required'}), 400
    
    try:
        road_ids = [int(id.strip()) for id in road_ids_param.split(',')]
    except ValueError:
        return jsonify({'error': 'road_ids must be a comma-separated list of integers'}), 400

    try:
        response = supabase.table('road_max_traffic_flow').select('*').in_('road_id', road_ids).execute()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not response.data or len(response.data) == 0:
        return jsonify({'error': 'Road(s) not found'}), 404

    return jsonify(response.data), 200
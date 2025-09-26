from src.database import supabase
from flask import jsonify, request

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
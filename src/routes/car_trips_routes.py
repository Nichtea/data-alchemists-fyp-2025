from flask import Blueprint
from src.controllers.car_trips_controller import (
    get_all_car_trips_flooded,
    get_car_trip_flooded_by_id,
    get_all_car_trips_dry,
    get_all_car_trips_dry_by_id
)

car_trips_route = Blueprint('car_trips_route', __name__)

# @car_trips_route.route('/car_trips_flooded', methods=['GET'])
# def all_flooded_trips():
#     return get_all_car_trips_flooded()

@car_trips_route.route('/car_trips_flooded/', methods=['GET'])
def flooded_trip_by_id():
    """
    Get flooded car trips by list of car_trip_ids
    ---
    tags:
      - Car
    parameters:
      - name: car_trip_ids
        in: query
        type: string
        description: Comma separated list of car trip IDs (e.g., 1,2,3)
        required: true
    responses:
      200:
        description: List of flooded car trips matching car_trip_ids
        schema:
          type: array
          items: 
            type: object
        examples:
            application/json:
                  - car_trip_id: 253201
                    end_area_code: "NT"
                    end_lat: 1.30907436213629
                    end_lon: 103.837046750208
                    end_nodes_id: 240701697
                    end_region_code: "CR"
                    sim_total_duration: 765.218516342877
                    start_area_code: "BK"
                    start_lat: 1.3461312
                    start_lon: 103.7472412
                    start_nodes_id: 1743861070
                    start_region_code: "WR"
                  - car_trip_id: 253202
                    end_area_code: "NT"
                    end_lat: 1.30907436213629
                    end_lon: 103.837046750208
                    end_nodes_id: 240701697
                    end_region_code: "CR"
                    sim_total_duration: 765.239023786756
                    start_area_code: "SE"
                    start_lat: 1.3898248
                    start_lon: 103.8972386
                    start_nodes_id: 375766139
                    start_region_code: "NER"
      400:
        description: Missing or invalid car_trip_ids parameter
        schema:
          type: object
          properties:
            error:
              type: string
              example: "car_trip_ids is required"
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Database connection failed"
    """
    return get_car_trip_flooded_by_id()

# @car_trips_route.route('/car_trips_dry', methods=['GET'])
# def all_dry_trips():
#     return get_all_car_trips_dry()

@car_trips_route.route('/car_trips_dry/', methods=['GET'])
def dry_trip_by_id():
    """
    Get dry car trips by list of car_trip_ids
    ---
    tags:
      - Car
    parameters:
      - name: car_trip_ids
        in: query
        type: string
        description: Comma separated list of car trip IDs (e.g., 1,2,3)
        required: true
    responses:
      200:
        description: List of dry car trips matching car_trip_ids
        schema:
          type: array
          items: 
            type: object
        examples:
            application/json:
                  - car_trip_id: 253201
                    end_area_code: "NT"
                    end_lat: 1.30907436213629
                    end_lon: 103.837046750208
                    end_nodes_id: 240701697
                    end_region_code: "CR"
                    sim_total_duration: 765.218516342877
                    start_area_code: "BK"
                    start_lat: 1.3461312
                    start_lon: 103.7472412
                    start_nodes_id: 1743861070
                    start_region_code: "WR"
                  - car_trip_id: 253202
                    end_area_code: "NT"
                    end_lat: 1.30907436213629
                    end_lon: 103.837046750208
                    end_nodes_id: 240701697
                    end_region_code: "CR"
                    sim_total_duration: 765.239023786756
                    start_area_code: "SE"
                    start_lat: 1.3898248
                    start_lon: 103.8972386
                    start_nodes_id: 375766139
                    start_region_code: "NER"
      400:
        description: Missing or invalid car_trip_ids parameter
        schema:
          type: object
          properties:
            error:
              type: string
              example: "car_trip_ids is required"
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Database connection failed"
    """
    return get_all_car_trips_dry_by_id()

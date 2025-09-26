from flask import Blueprint
from src.controllers.car_trips_controller import (
    get_all_car_trips_by_id,
)

car_trips_route = Blueprint('car_trips_route', __name__)

# @car_trips_route.route('/car_trips_flooded', methods=['GET'])
# def all_flooded_trips():
#     return get_all_car_trips_flooded()

# @car_trips_route.route('/car_trips_flooded/', methods=['GET'])
# def flooded_trip_by_id():
#     """
#     Get flooded car trips by list of car_trip_ids
#     ---
#     tags:
#       - Car
#     parameters:
#       - name: car_trip_ids
#         in: query
#         type: string
#         description: Comma separated list of car trip IDs (e.g., 1,2,3)
#         required: true
#     responses:
#       200:
#         description: List of flooded car trips matching car_trip_ids
#         schema:
#           type: array
#           items: 
#             type: object
#         examples:
#             application/json:
#                   - car_trip_id: 253201
#                     end_area_code: "NT"
#                     end_lat: 1.30907436213629
#                     end_lon: 103.837046750208
#                     end_nodes_id: 240701697
#                     end_region_code: "CR"
#                     sim_total_duration: 765.218516342877
#                     start_area_code: "BK"
#                     start_lat: 1.3461312
#                     start_lon: 103.7472412
#                     start_nodes_id: 1743861070
#                     start_region_code: "WR"
#                   - car_trip_id: 253202
#                     end_area_code: "NT"
#                     end_lat: 1.30907436213629
#                     end_lon: 103.837046750208
#                     end_nodes_id: 240701697
#                     end_region_code: "CR"
#                     sim_total_duration: 765.239023786756
#                     start_area_code: "SE"
#                     start_lat: 1.3898248
#                     start_lon: 103.8972386
#                     start_nodes_id: 375766139
#                     start_region_code: "NER"
#       400:
#         description: Missing or invalid car_trip_ids parameter
#         schema:
#           type: object
#           properties:
#             error:
#               type: string
#               example: "car_trip_ids is required"
#       500:
#         description: Server error
#         schema:
#           type: object
#           properties:
#             error:
#               type: string
#               example: "Database connection failed"
#     """
#     return get_car_trip_flooded_by_id()

# @car_trips_route.route('/car_trips_dry', methods=['GET'])
# def all_dry_trips():
#     return get_all_car_trips_dry()

# @car_trips_route.route('/car_trips_dry/', methods=['GET'])
# def dry_trip_by_id():
#     """
#     Get dry car trips by list of car_trip_ids
#     ---
#     tags:
#       - Car
#     parameters:
#       - name: car_trip_ids
#         in: query
#         type: string
#         description: Comma separated list of car trip IDs (e.g., 1,2,3)
#         required: true
#     responses:
#       200:
#         description: List of dry car trips matching car_trip_ids
#         schema:
#           type: array
#           items: 
#             type: object
#         examples:
#             application/json:
#                   - car_trip_id: 253201
#                     end_area_code: "NT"
#                     end_lat: 1.30907436213629
#                     end_lon: 103.837046750208
#                     end_nodes_id: 240701697
#                     end_region_code: "CR"
#                     sim_total_duration: 765.218516342877
#                     start_area_code: "BK"
#                     start_lat: 1.3461312
#                     start_lon: 103.7472412
#                     start_nodes_id: 1743861070
#                     start_region_code: "WR"
#                   - car_trip_id: 253202
#                     end_area_code: "NT"
#                     end_lat: 1.30907436213629
#                     end_lon: 103.837046750208
#                     end_nodes_id: 240701697
#                     end_region_code: "CR"
#                     sim_total_duration: 765.239023786756
#                     start_area_code: "SE"
#                     start_lat: 1.3898248
#                     start_lon: 103.8972386
#                     start_nodes_id: 375766139
#                     start_region_code: "NER"
#       400:
#         description: Missing or invalid car_trip_ids parameter
#         schema:
#           type: object
#           properties:
#             error:
#               type: string
#               example: "car_trip_ids is required"
#       500:
#         description: Server error
#         schema:
#           type: object
#           properties:
#             error:
#               type: string
#               example: "Database connection failed"
#     """
#     return get_all_car_trips_dry_by_id()

@car_trips_route.route('/car_trips/', methods=['GET'])
def all_trips_by_id():
  """
    Get car trips by list of car_trip_ids
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
        description: List of car trips matching car_trip_ids
        schema:
          type: array
          items: 
            type: object
        examples:
          application/json:
            - 10kph_total_duration: 846.094561834224
              20kph_total_duration: 846.094561834224
              45kph_total_duration: 846.094561834224
              5kph_total_duration: 846.094561834224
              72kph_total_duration: 846.094561834224
              81kph_total_duration: 846.094561834224
              90kph_total_duration: 846.094561834224
              car_trip_id: 1
              end_area_code: "RV"
              end_lat: 1.2959214532978
              end_lon: 103.839648207666
              end_node_id: 74389915
              end_region_code: "CR"
              start_area_code: "TM"
              start_lat: 1.3347624
              start_lon: 103.9787666
              start_node_id: 25451915
              start_region_code: "ER"
            - 10kph_total_duration: 1328.11506274635
              20kph_total_duration: 1328.11506274635
              45kph_total_duration: 1328.11506274635
              5kph_total_duration: 1328.11506274635
              72kph_total_duration: 1328.11506274635
              81kph_total_duration: 1328.11506274635
              90kph_total_duration: 1328.11506274635
              car_trip_id: 2
              end_area_code: "CC"
              end_lat: 1.38455185352078
              end_lon: 103.780567652147
              end_node_id: 158014842
              end_region_code: "NR"
              start_area_code: "TM"
              start_lat: 1.3347624
              start_lon: 103.9787666
              start_node_id: 25451915
              start_region_code: "ER"

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
  return get_all_car_trips_by_id()
from flask import Blueprint
from src.controllers.bus_controller import (get_all_bus_stops, get_bus_stop_by_stop_code, get_all_bus_trip, get_bus_trip_by_id,get_all_bus_trip_segment, get_bus_trip_segment_by_id, get_bus_trip_delay)

bus_route = Blueprint('bus_route', __name__)

@bus_route.route('/bus_stops', methods=['GET'])
def all_bus_stops():
    """
    Get all bus stops
    ---
tags:
  - Bus
responses:
  200:
    description: Bus stop details
    schema:
      type: array
    examples:
      application/json:
        - geom: null
          stop_code: "98281"
          stop_id: "98281"
          stop_lat: 103.966171624349
          stop_lon: 1.35967915316721
          stop_name: "Estella Gdns"
          stop_desc: null
          wheelchair_boarding: "1"
        - geom: null
          stop_code: "59629"
          stop_id: "59629"
          stop_lat: 1.434758706
          stop_lon: 103.8439165
          stop_name: "Symphony Suites Condo"
          stop_url: null
          wheelchair_boarding: 1
  404:
    description: No bus stops found
    """
    return get_all_bus_stops()

@bus_route.route('/bus_stops/<string:stop_code>', methods=['GET'])
def bus_stop_by_stop_code(stop_code):
    """
    Get bus stop by stop code
    ---
    tags:
      - Bus
    parameters:
      - name: stop_code
        in: path
        type: string
        required: true
        description: Bus stop code
    responses:
      200:
        description: Bus stop details
        schema:
          type: object
        examples:
          application/json:
            geom: null
            stop_code: "98281"
            stop_id: "98281"
            stop_lat: 103.966171624349
            stop_lon: 1.35967915316721
            stop_name: "Estella Gdns"
            stop_desc: null
            wheelchair_boarding: "1"
      404:
        description: Bus stop not found
    """
    return get_bus_stop_by_stop_code(stop_code)

# @bus_route.route('/bus_trip', methods=['GET'])
# def all_bus_trips():
#     return get_all_bus_trip()

@bus_route.route('/bus_trip/<int:bus_trip_id>', methods=['GET'])
def bus_trip_by_id(bus_trip_id):
    """
    Get bus trip by trip ID
    ---
    tags:
      - Bus
    parameters:
      - name: bus_trip_id
        in: path
        type: string
        required: true
        description: Bus trip ID
    responses:
      200:
        description: Bus trip details
        schema:
          type: object
          example:
            application/json:
            12kmh_total_bus_duration: 240
            12kmh_total_duration: 2185
            30kmh_total_bus_duration: 212
            30kmh_total_duration: 2157
            48kmh_total_bus_duration: 205
            48kmh_total_duration: 2150
            5kmh_total_bus_duration: 303
            5kmh_total_duration: 2248
            bus_trip_id: 13
            end_area_code: "PG"
            end_geom: null
            end_lat: 1.40544909693222
            end_lon: 103.908503032429
            end_node_id: 2274884501
            end_region_code: "NER"
            filepath: "01012to2274884501.json"
            non_bus_duration: 1945
            non_flooded_total_bus_duration: 203
            non_flooded_total_duration: 2148
            number_of_busroutes: 1
            routeNodeIDs:
                - 4738400701
                - 233432515
                - 233432542
                - 595267994
                - 595268007
                - 233432563
                - 233432607
                - 233432633
                - 365302308
                - 233432671
                - 5982556742
                - 4602210048
                - 233432705
                - 233432799
                - 7043294787
                - 233432823
                - 5166520742
                - 249392291
                - 240646599
                - 249392296
                - 240646581
                - 378619193
                - 378618810
                - 240646389
                - 240646408
                - 236310575
                - 236320394
                - 2948839129
                - 229576235
                - 245396647
                - 5243487086
                - 229576256
                - 377553457
            start_area_code: "RC"
            start_geom: null
            start_lat: 1.29684825487647
            start_lon: 103.85253591654
            start_node_id: 4748705954
            start_region_code: "CR"
            total_bus_distance: 3388
            transfers: 2
            transit_time: 1860
            waiting_time: 366

      404:
        description: Bus trip not found
    """
    return get_bus_trip_by_id(bus_trip_id)

# @bus_route.route('/bus_trip_segment', methods=['GET'])
# def all_bus_trip_segments():
#     return get_all_bus_trip_segment()

@bus_route.route('/bus_trip_segment/<int:bus_trip_id>', methods=['GET'])
def bus_trip_segment_by_id(bus_trip_id):
    """
    Get bus trip segment by bus trip ID
    ---
    tags:
      - Bus
    parameters:
      - name: bus_trip_id
        in: path
        type: string
        required: true
        description: Bus trip ID
    responses:
      200:
        description: Bus trip segment details
        schema:
          type: object
          example:
                12kmh_flooded_bus_duration: 240
                30kmh_flooded_bus_duration: 212
                48kmh_flooded_bus_duration: 205
                5kmh_flooded_bus_duration: 303
                bus_trip_id: 13
                destination_stop_id: "60121"
                filepath: "01012to2274884501.json"
                non_flooded_bus_duration: 203
                origin_stop_id: "01013"
                route_id: "133"
                segment: 1
      404:
        description: Bus trip segment not found
    """
    return get_bus_trip_segment_by_id(bus_trip_id)

@bus_route.route('/bus_trips/delay', methods=['GET'])
def bus_trips_with_delay():

    """
    Get all bus trips currently delayed
    ---
    tags:
      - Bus
    parameters:
      - name: stop_id
        in: query
        type: string
        required: true
        description: Starting bus stop ID
      - name: trip_end_area_code
        in: query
        type: string
        required: true
        description: End area code for trip destination
    responses:
      200:
        description: List of delayed bus trips with nested segment delay info
        schema:
          type: object
          properties:
            trips:
              type: array
              items:
                type: object
                properties:
                  bus_trip_id:
                    type: integer
                    example: 214275
                  start_lat:
                    type: number
                    example: 1.30939538245506
                  start_lon:
                    type: number
                    example: 103.91428724576
                  end_lat:
                    type: number
                    example: 1.43211542666418
                  end_lon:
                    type: number
                    example: 103.720448212322
                  flooded_total_bus_durations:
                    type: object
                    properties:
                      "12kmh":
                        type: integer
                        example: 1205
                      "30kmh":
                        type: integer
                        example: 1205
                      "48kmh":
                        type: integer
                        example: 1205
                      "5kmh":
                        type: integer
                        example: 1205
                  flooded_total_durations:
                    type: object
                    properties:
                      "12kmh":
                        type: integer
                        example: 6284
                      "30kmh":
                        type: integer
                        example: 6284
                      "48kmh":
                        type: integer
                        example: 6284
                      "5kmh":
                        type: integer
                        example: 6284
                  non_flooded_total_bus_duration:
                    type: integer
                    example: 1205
                  non_flooded_total_duration:
                    type: integer
                    example: 6284
                  overall_total_delay:
                    type: object
                    properties:
                      "12kmh":
                        type: integer
                        example: 0
                      "30kmh":
                        type: integer
                        example: 0
                      "48kmh":
                        type: integer
                        example: 0
                      "5kmh":
                        type: integer
                        example: 0
                  overall_bus_delay:
                    type: object
                    properties:
                      "12kmh":
                        type: integer
                        example: 0
                      "30kmh":
                        type: integer
                        example: 0
                      "48kmh":
                        type: integer
                        example: 0
                      "5kmh":
                        type: integer
                        example: 0
                  segments:
                    type: array
                    items:
                      type: object
                      properties:
                        segment_id:
                          type: integer
                          example: 1
                        origin_stop_id:
                          type: string
                          example: "92149"
                        destination_stop_id:
                          type: string
                          example: "08121"
                        non_flooded_bus_duration:
                          type: integer
                          example: 785
                        flooded_durations:
                          type: object
                          properties:
                            "12kmh":
                              type: integer
                              example: 785
                            "30kmh":
                              type: integer
                              example: 785
                            "48kmh":
                              type: integer
                              example: 785
                            "5kmh":
                              type: integer
                              example: 785
                        delays:
                          type: object
                          properties:
                            "12kmh":
                              type: integer
                              example: 0
                            "30kmh":
                              type: integer
                              example: 0
                            "48kmh":
                              type: integer
                              example: 0
                            "5kmh":
                              type: integer
                              example: 0
      400:
        description: Missing required query parameters
        schema:
          type: object
          properties:
            error:
              type: string
              example: stop_id and trip_end_area_code are required
      404:
        description: No bus trips found for given criteria
        schema:
          type: object
          properties:
            error:
              type: string
              example: No bus trips found for given criteria
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Server error occurred
    """
    # Your existing endpoint code here

    return get_bus_trip_delay()
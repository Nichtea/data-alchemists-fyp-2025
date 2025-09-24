from flask import Blueprint
from src.controllers.traffic_controller import (
    get_all_road_max_traffic_flow,get_road_max_traffic_flow_by_id)


traffic_route = Blueprint('traffic_route', __name__)

@traffic_route.route('/road_max_traffic_flow', methods=['GET'])
def all_road_max_traffic_flow():
    """
    Get all road max traffic flow records
    ---
    tags:
      - Roads
    responses:
      200:
        description: List of road max traffic flow records
        schema:
          type: array
          items:
            type: object
            properties:
              RoadCat:
                type: string
                example: "CAT2"
              end_geom:
                type: object
                properties:
                  coordinates:
                    type: array
                    items:
                      type: number
                    example: [103.8127463, 1.321445336]
                  crs:
                    type: object
                    properties:
                      properties:
                        type: object
                        properties:
                          name:
                            type: string
                            example: "EPSG:4326"
                      type:
                        type: string
                        example: "name"
                  type:
                    type: string
                    example: "Point"
              end_lat:
                type: number
                example: 1.321445336
              end_lon:
                type: number
                example: 103.8127463
              road_id:
                type: integer
                example: 1
              road_name:
                type: string
                example: "ADAM ROAD"
              start_geom:
                type: object
                properties:
                  coordinates:
                    type: array
                    items:
                      type: number
                    example: [103.8115894, 1.320198885]
                  crs:
                    type: object
                    properties:
                      properties:
                        type: object
                        properties:
                          name:
                            type: string
                            example: "EPSG:4326"
                      type:
                        type: string
                        example: "name"
                  type:
                    type: string
                    example: "Point"
              start_lat:
                type: number
                example: 1.320198885
              start_lon:
                type: number
                example: 103.8115894
              volume:
                type: integer
                example: 850
      404:
        description: No records found
        schema:
          type: object
          properties:
            message:
              type: string
              example: No records found
    """
    return get_all_road_max_traffic_flow()

@traffic_route.route('/road_max_traffic_flow/id/', methods=['GET'])
def road_max_traffic_flow_by_id():
    """
    Get road max traffic flow details by road IDs
    ---
    tags:
      - Roads
    parameters:
      - name: road_ids
        in: query
        description: Comma-separated list of road IDs
        required: true
        type: string
    responses:
      200:
        description: List of road max traffic flow records for given road IDs
        schema:
          type: array
          items:
            type: object
            properties:
              RoadCat:
                type: string
                example: "CAT2"
              end_geom:
                type: object
                properties:
                  coordinates:
                    type: array
                    items:
                      type: number
                    example: [103.8127463, 1.321445336]
                  crs:
                    type: object
                    properties:
                      properties:
                        type: object
                        properties:
                          name:
                            type: string
                            example: "EPSG:4326"
                      type:
                        type: string
                        example: "name"
                  type:
                    type: string
                    example: "Point"
              end_lat:
                type: number
                example: 1.321445336
              end_lon:
                type: number
                example: 103.8127463
              road_id:
                type: integer
                example: 1
              road_name:
                type: string
                example: "ADAM ROAD"
              start_geom:
                type: object
                properties:
                  coordinates:
                    type: array
                    items:
                      type: number
                    example: [103.8115894, 1.320198885]
                  crs:
                    type: object
                    properties:
                      properties:
                        type: object
                        properties:
                          name:
                            type: string
                            example: "EPSG:4326"
                      type:
                        type: string
                        example: "name"
                  type:
                    type: string
                    example: "Point"
              start_lat:
                type: number
                example: 1.320198885
              start_lon:
                type: number
                example: 103.8115894
              volume:
                type: integer
                example: 850
      400:
        description: Missing or invalid road_ids parameter
        schema:
          type: object
          properties:
            error:
              type: string
              example: road_ids parameter is required
      404:
        description: No records found for given road IDs
        schema:
          type: object
          properties:
            error:
              type: string
              example: Road(s) not found
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Database error
    """
    return get_road_max_traffic_flow_by_id()
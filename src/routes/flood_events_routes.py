from flask import Blueprint
from src.controllers.flood_events_controller import get_all_flood_events, get_flood_event_by_id

flood_events_route = Blueprint('flood_events_route', __name__)

@flood_events_route.route('/flood_events', methods=['GET'])
def all_flood_events():
    """
    Get all flood events
    ---
    tags:
      - Flood Events
    responses:
      200:
        description: List of flood event records
        schema:
          type: array
          items:
            type: object
            properties:
              flood_id:
                type: integer
              event_description:
                type: string
              geom:
                type: object
                description: GeoJSON geometry of the flood event
              event_date:
                type: string
                format: date-time
        examples:
            application/json:
              - daily rainfall total (mm): 45
                date: "2014-03-20"
                flood_id: 1
                flooded_location: "Yishun MRT"
                geom:
                coordinates:
                    - 103.8349951
                    - 1.429525229
                crs:
                    properties:
                    name: "EPSG:4326"
                    type: "name"
                type: "Point"
                highest 120 min rainfall (mm): 44.2
                highest 30 min rainfall (mm): 40.8
                highest 60 min rainfall (mm): 44
                latitude: 1.429525229
                longitude: 103.8349951
                mean_pr: 17.3950819672131
              - daily rainfall total (mm): 25
                date: "2014-04-04"
                flood_id: 2
                flooded_location: "2 KAKI BUKIT ROAD 3"
                geom:
                coordinates:
                    - 103.9019432
                    - 1.337333619
                crs:
                    properties:
                    name: "EPSG:4326"
                    type: "name"
                type: "Point"
                highest 120 min rainfall (mm): 25
                highest 30 min rainfall (mm): 21
                highest 60 min rainfall (mm): 25
                latitude: 1.337333619
                longitude: 103.9019432
                mean_pr: 7.99354838709677
              - daily rainfall total (mm): 89.5
                date: "2014-04-23"
                flood_id: 3
                flooded_location: "PSC Building"
                geom:
                coordinates:
                    - 103.7061887
                    - 1.328862581
                crs:
                    properties:
                    name: "EPSG:4326"
                    type: "name"
                type: "Point"
                highest 120 min rainfall (mm): 89
                highest 30 min rainfall (mm): 49.5
                highest 60 min rainfall (mm): 83
                latitude: 1.328862581
                longitude: 103.7061887
                mean_pr: 14.5746031746032

      404:
        description: No flood events found
        schema:
          type: object
          properties:
            message:
              type: string
              example: No records found
    """
    return get_all_flood_events()

@flood_events_route.route('/flood_events/id/', methods=['GET'])
def flood_event_by_id():
    """
    Get flood event info by flood_event_id(s), including nearest road data
    ---
    tags:
      - Flood Events
    parameters:
      - name: flood_event_ids
        in: query
        required: true
        description: Comma-separated list of flood event IDs
        type: string
    responses:
      200:
        description: Flood event road info for each flood_event_id
        schema:
          type: array
          items:
            type: object
        examples:
          application/json:
            - flood_id: 1
              road_name: "Yishun Avenue 2"
              road_type: "primary"
              length_m: 616.4873388504224
              geometry: "LINESTRING (103.8350704 1.4248212, 103.8350717 1.4248739, 103.8351006 1.4260113, ...)"
            - flood_id: 12
              road_name: "MacKenzie Road"
              road_type: "residential"
              length_m: 257.5635671396551
              geometry: "LINESTRING (103.8484492 1.3055518, 103.8483005 1.3056599, 103.8481111 1.3057976, ...)"
      400:
        description: Missing or invalid flood_event_ids query parameter
        schema:
          type: object
          properties:
            error:
              type: string
              example: flood_event_ids parameter is required
      404:
        description: No flood events found for given IDs
        schema:
          type: object
          properties:
            error:
              type: string
              example: Flood event(s) not found
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: Server error occurred
    """
    return get_flood_event_by_id()
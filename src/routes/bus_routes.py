from flask import Blueprint
from src.controllers.bus_controller import (get_all_bus_stops, get_bus_stop_by_stop_code, get_all_bus_trip, get_bus_trip_by_id,get_all_bus_trip_segment, get_bus_trip_segment_by_id, get_bus_trip_delay, get_unique_end_area_codes, get_bus_trip_segement_delay)
from flasgger import swag_from
from ..examples_for_doc.bus_api_examples import *
from ..examples_for_doc.bus_related_schemas import *
bus_route = Blueprint('bus_route', __name__)



@bus_route.route('/bus_stops', methods=['GET'])
@swag_from({
    "tags": ["Bus"],
    "responses": {
        200: {
            "description": "Bus stop details",
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "stop_id": {"type": "string", "description": "Unique identifier of the bus stop"},
                        "stop_code": {"type": "string", "description": "Official bus stop code"},
                        "stop_name": {"type": "string", "description": "Name of the bus stop"},
                        "stop_lat": {"type": "number", "format": "float", "description": "Latitude"},
                        "stop_lon": {"type": "number", "format": "float", "description": "Longitude"},
                        "wheelchair_boarding": {"type": "string", "description": "1 if wheelchair accessible, 0 if not"},
                        "geom": {"type": "string", "nullable": True, "description": "Geometry data for mapping"},
                        "stop_desc": {"type": "string", "nullable": True, "description": "Optional description"},
                        "stop_url": {"type": "string", "nullable": True, "description": "Optional URL for more info"}
                    }
                }
            },
            "examples": {"application/json": bus_stops_example}
        },
        404: {"description": "Bus stop not found"}
    }
})
def all_bus_stops():
 
    return get_all_bus_stops()

@bus_route.route('/bus_stops/<string:stop_code>', methods=['GET'])
@swag_from({
    "tags": ["Bus"],
    "parameters": [
        {
            "name": "stop_code",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "Bus stop code"
        }
    ],
    "responses": {
        200: {
            "description": "Bus stop details",
            "schema":  bus_stops_schema,
            "examples": {"application/json": bus_stops_example}
        },
        404: {"description": "Bus stop not found"}
    }
})
def bus_stop_by_stop_code(stop_code):
  
    return get_bus_stop_by_stop_code(stop_code)

# @bus_route.route('/bus_trip', methods=['GET'])
# def all_bus_trips():
#     return get_all_bus_trip()

@bus_route.route('/bus_trip/<int:bus_trip_id>', methods=['GET'])
@swag_from({
    "tags": ["Bus"],
    "parameters": [
        {
            "name": "bus_trip_id",
            "in": "path",
            "type": "integer",
            "required": True,
            "description": "Bus trip ID"
        }
    ],
    "responses": {
        200: {
            "description": "Bus trip details",
            "schema": bus_trip_schema,
            "examples": {"application/json": bus_trips_get_example}
        },
        404: {"description": "Bus trip not found"}
    }
})
def bus_trip_by_id(bus_trip_id):
    return get_bus_trip_by_id(bus_trip_id)

# @bus_route.route('/bus_trip_segment', methods=['GET'])
# def all_bus_trip_segments():
#     return get_all_bus_trip_segment()

@bus_route.route('/bus_trip_segment/<int:bus_trip_id>', methods=['GET'])
@swag_from({
    "tags": ["Bus"],
    "parameters": [
        {
            "name": "bus_trip_id",
            "in": "path",
            "type": "integer",
            "required": True,
            "description": "Bus trip ID"
        }
    ],
    "responses": {
        200: {
            "description": "Bus trip segment details",
            "schema": bus_trip_segment_schema,
            "examples": {"application/json": bus_trip_segment_example}
        },
        404: {"description": "Bus trip segment not found"}
    }
})
def bus_trip_segment_by_id(bus_trip_id):

    return get_bus_trip_segment_by_id(bus_trip_id)

@bus_route.route('/bus_trips/delay', methods=['GET'])
@swag_from({
    "tags": ["Bus"],
    "parameters": [
        {"name": "stop_id", "in": "query", "type": "string", "required": True, "description": "Starting bus stop ID"},
        {"name": "trip_end_area_code", "in": "query", "type": "string", "required": True, "description": "End area code for trip destination"}
    ],
    "responses": {
        200: {
            "description": "List of delayed bus trips with nested segment delay info",
            "schema": bus_delayed_schema,
            "examples": {"application/json": bus_trips_delayed_example}
        },
        400: {
            "description": "Missing required query parameters",
            "schema": {"type": "object", "properties": {"error": {"type": "string", "example": "stop_id and trip_end_area_code are required"}}}
        },
        404: {
            "description": "No bus trips found for given criteria",
            "schema": {"type": "object", "properties": {"error": {"type": "string", "example": "No bus trips found for given criteria"}}}
        },
        500: {
            "description": "Internal server error",
            "schema": {"type": "object", "properties": {"error": {"type": "string", "example": "Server error occurred"}}}
        }
    }
})
def bus_trips_with_delay():

    return get_bus_trip_delay()

@bus_route.route('/bus_trips/end_area_codes', methods=['GET'])
def bus_trips_end_area_codes():
    return get_unique_end_area_codes()

@bus_route.route('/bus_trip_segments/delay', methods=['GET'])
def bus_trip_segments_with_delay():
    return get_bus_trip_segement_delay()
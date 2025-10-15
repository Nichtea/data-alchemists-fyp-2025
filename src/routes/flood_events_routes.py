from flask import Blueprint
from src.controllers.flood_events_controller import get_all_flood_events, get_flood_event_by_id, get_flood_events_by_location, get_buses_affected_by_floods
from flasgger import swag_from
from ..examples_for_doc.flooded_events_api import *
from ..examples_for_doc.flooded_events_schemas import *
flood_events_route = Blueprint('flood_events_route', __name__)

@flood_events_route.route('/flood_events', methods=['GET'])

@swag_from({
    "tags": ["Flood Events"],
    "responses": {
        200: {
            "description": "List of flood event records",
            "schema": flood_events_schema,
            "examples": {"application/json": get_all_flood_events_example}
        },
        404: {
            "description": "No flood events found",
            "schema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "example": "No records found"
                    }
                }
            }
        }
    }
})
def all_flood_events():
   
    return get_all_flood_events()

@flood_events_route.route('/flood_events/id/', methods=['GET'])
@swag_from({
    "tags": ["Flood Events"],
    "parameters": [
        {
            "name": "flood_event_ids",
            "in": "query",
            "required": True,
            "type": "string",
            "description": "Comma-separated list of flood event IDs"
        }
    ],
    "responses": {
        200: {
            "description": "Flood event road info for each flood_event_id",
            "schema": flood_event_by_id_schema,
            "examples": {"application/json": flood_event_by_id_example}
        },
        400: {
            "description": "Missing or invalid flood_event_ids query parameter",
            "schema": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "flood_event_ids parameter is required"}
                }
            }
        },
        404: {
            "description": "No flood events found for given IDs",
            "schema": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "Flood event(s) not found"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "schema": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "Server error occurred"}
                }
            }
        }
    }
})

def flood_event_by_id():

    return get_flood_event_by_id()

@flood_events_route.route('/flood_events/location', methods=['GET'])
def flood_event_by_location():
    return get_flood_events_by_location()

@flood_events_route.route('/get_buses_affected_by_floods', methods=['GET'])
def get_buses_affected_by_floods_route():
    return get_buses_affected_by_floods()

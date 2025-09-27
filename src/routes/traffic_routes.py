from flask import Blueprint
from flasgger import swag_from
from ..examples_for_doc.traffic_route_examples import *
from ..examples_for_doc.traffic_route_schemas import *
from src.controllers.traffic_controller import (
    get_all_road_max_traffic_flow,get_road_max_traffic_flow_by_id)


traffic_route = Blueprint('traffic_route', __name__)

@traffic_route.route('/road_max_traffic_flow', methods=['GET'])
@swag_from({
    "tags": ["Roads"],
    "responses": {
        200: {
            "description": "List of road max traffic flow records",
            "schema": road_max_traffic_flow_schema,
            "examples": {"application/json": road_max_traffic_flow_example}
        },
        404: {
            "description": "No records found",
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

def all_road_max_traffic_flow():
   
    return get_all_road_max_traffic_flow()

@traffic_route.route('/road_max_traffic_flow/id/', methods=['GET'])

@swag_from({
    "tags": ["Roads"],
    "responses": {
        200: {
            "description": "List of road max traffic flow records for given road IDs",
            "schema": road_max_traffic_flow_by_id_schema,
            "examples": {"application/json": road_max_traffic_flow_by_id_example}
        }
    }
})

def road_max_traffic_flow_by_id():
 
    return get_road_max_traffic_flow_by_id()
from flask import Blueprint
from src.controllers.traffic_controller import (
    get_all_road_max_traffic_flow,get_road_max_traffic_flow_by_id)


traffic_route = Blueprint('traffic_route', __name__)

@traffic_route.route('/road_max_traffic_flow', methods=['GET'])
def all_road_max_traffic_flow():
    return get_all_road_max_traffic_flow()

@traffic_route.route('/road_max_traffic_flow/<int:road_id>', methods=['GET'])
def road_max_traffic_flow_by_id(road_id):
    return get_road_max_traffic_flow_by_id(road_id)
from flask import Blueprint
from src.controllers.bus_controller import (get_all_bus_stops, get_bus_stop_by_stop_code, get_all_bus_trip, get_bus_trip_by_id,get_all_bus_trip_segment, get_bus_trip_segment_by_id)

bus_route = Blueprint('bus_route', __name__)

@bus_route.route('/bus_stops', methods=['GET'])
def all_bus_stops():
    return get_all_bus_stops()

@bus_route.route('/bus_stops/<string:stop_code>', methods=['GET'])
def bus_stop_by_stop_code(stop_code):
    return get_bus_stop_by_stop_code(stop_code)

@bus_route.route('/bus_trip', methods=['GET'])
def all_bus_trips():
    return get_all_bus_trip()

@bus_route.route('/bus_trip/<int:bus_trip_id>', methods=['GET'])
def bus_trip_by_id(bus_trip_id):
    return get_bus_trip_by_id(bus_trip_id)

@bus_route.route('/bus_trip_segment', methods=['GET'])
def all_bus_trip_segments():
    return get_all_bus_trip_segment()

@bus_route.route('/bus_trip_segment/<int:segment_id>', methods=['GET'])
def bus_trip_segment_by_id(segment_id):
    return get_bus_trip_segment_by_id(segment_id)
from flask import Blueprint
from src.controllers.car_trips_controller import (
    get_all_car_trips_flooded,
    get_car_trip_flooded_by_id,
    get_all_car_trips_dry,
    get_all_car_trips_dry_by_id
)

car_trips_route = Blueprint('car_trips_route', __name__)

@car_trips_route.route('/car_trips_flooded', methods=['GET'])
def all_flooded_trips():
    return get_all_car_trips_flooded()

@car_trips_route.route('/car_trips_flooded/<int:car_trip_id>', methods=['GET'])
def flooded_trip_by_id(car_trip_id):
    return get_car_trip_flooded_by_id(car_trip_id)

@car_trips_route.route('/car_trips_dry', methods=['GET'])
def all_dry_trips():
    return get_all_car_trips_dry()

@car_trips_route.route('/car_trips_dry/<int:car_trip_id>', methods=['GET'])
def dry_trip_by_id(car_trip_id):
    return get_all_car_trips_dry_by_id(car_trip_id)

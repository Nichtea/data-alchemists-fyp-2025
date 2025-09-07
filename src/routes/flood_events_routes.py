from flask import Blueprint
from src.controllers.flood_events_controller import get_all_flood_events, get_flood_event_by_id

flood_events_route = Blueprint('flood_events_route', __name__)

@flood_events_route.route('/flood_events', methods=['GET'])
def all_flood_events():
    return get_all_flood_events()

@flood_events_route.route('/flood_events/<int:flood_event_id>', methods=['GET'])
def flood_event_by_id(flood_event_id):
    return get_flood_event_by_id(flood_event_id)
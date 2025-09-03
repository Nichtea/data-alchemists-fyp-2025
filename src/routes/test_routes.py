from flask import Blueprint
from src.controllers.test_controller import TestController


test_route = Blueprint('test_route', __name__, template_folder='src/templates')

@test_route.route('/')
def home():
    return TestController.home()


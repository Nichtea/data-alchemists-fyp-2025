from flask import Blueprint, render_template

test_controller = Blueprint('test_controller', __name__, template_folder='src/templates')

@test_controller.route('/')
def home():
    return render_template('index.html')


from flask import Flask
from dotenv import load_dotenv
from flasgger import Swagger
import os


from src.routes.car_trips_routes import car_trips_route
from src.routes.bus_routes import bus_route
from src.routes.flood_events_routes import flood_events_route
from src.routes.traffic_routes import traffic_route

def create_app():
    app = Flask(__name__,template_folder="src/templates")
    load_dotenv()
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    swagger = Swagger(app)
    app.register_blueprint(car_trips_route)
    app.register_blueprint(bus_route)
    app.register_blueprint(flood_events_route)
    app.register_blueprint(traffic_route)
    return app

if __name__ == '__main__':
    app=create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
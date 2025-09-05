from flask import Flask
from dotenv import load_dotenv
import os

from src.routes.test_routes import test_route

def create_app():
    app = Flask(__name__,template_folder="src/templates")
    load_dotenv()
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.register_blueprint(test_route)
    return app

if __name__ == '__main__':
    app=create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
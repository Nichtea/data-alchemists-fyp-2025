from flask import Flask
from dotenv import load_dotenv
import os

from src.routes.test_routes import test_route

app = Flask(__name__,template_folder="src/templates")
load_dotenv()
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.register_blueprint(test_route)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
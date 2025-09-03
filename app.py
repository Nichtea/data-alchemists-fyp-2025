from flask import Flask
from src.routes.test_routes import test_route

app = Flask(__name__,template_folder="src/templates")

app.register_blueprint(test_route)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
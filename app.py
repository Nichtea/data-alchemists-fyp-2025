from flask import Flask
from src.controllers.test_controller import test_controller

app = Flask(__name__,template_folder="src/templates")

app.register_blueprint(test_controller)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
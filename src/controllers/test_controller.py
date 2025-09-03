from flask import render_template

class TestController:

    @staticmethod
    def home():
        
        return render_template('index.html')

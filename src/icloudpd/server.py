from typing import Union
from flask import Flask, Response
import waitress

def serve_app() -> None:
    app = Flask(__name__)

    @app.route("/")
    def hello_world() -> Union[Response, str]:
        return "<p>Hello, World!</p>"

    return waitress.serve(app)
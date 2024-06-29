from logging import Logger
from typing import Union

import waitress
from flask import Flask, Response, abort, make_response, render_template

from icloudpd.status import Status, StatusExchange


def serve_app(logger: Logger, _status_exchange: StatusExchange) -> None:
    app = Flask(__name__)
    app.logger = logger

    @app.route("/")
    def index() -> Union[Response, str]:
        return render_template("index.html")

    @app.route("/status", methods=["GET"])
    def get_status() -> Union[Response, str]:
        _status = _status_exchange.get_status()
        if _status == Status.WAITING_FOR_2FA:
            return render_template("code.html")
        return render_template("status.html", status=_status)

    @app.route("/code", methods=["POST"])
    def set_code(_code: str) -> Union[Response, str]:
        if _status_exchange.set_code(_code):
            return make_response("", 201)
        return abort(400)  # incorrect status

    logger.debug("Starting web server...")
    return waitress.serve(app)

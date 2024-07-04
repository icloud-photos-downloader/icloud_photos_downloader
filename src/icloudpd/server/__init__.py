from logging import Logger
from typing import Union

import waitress
from flask import Flask, Response, abort, make_response, render_template, request

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
        if _status == Status.NOT_NEED_MFA:
            return render_template("no_input.html")
        if _status == Status.NEED_MFA:
            return render_template("code.html")
        return render_template("status.html", status=_status)

    @app.route("/code", methods=["POST"])
    def set_code() -> Union[Response, str]:
        code = request.form.get("code")
        if code is not None:
            if _status_exchange.set_code(code):
                return render_template("submitted.html")
        else:
            logger.error(f"cannot find code in request {request.form}")
        return make_response(render_template("error.html"), 400)  # incorrect code

    logger.debug("Starting web server...")
    return waitress.serve(app)

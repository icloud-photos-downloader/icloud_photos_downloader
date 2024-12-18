import os
import sys
from logging import Logger
from typing import Union

import waitress
from flask import Flask, Response, make_response, render_template, request

from icloudpd.status import Status, StatusExchange


def serve_app(logger: Logger, _status_exchange: StatusExchange) -> None:
    app = Flask(__name__)
    app.logger = logger
    # for running in pyinstaller
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir is not None:
        app.template_folder = os.path.join(bundle_dir, "templates")
        app.static_folder = os.path.join(bundle_dir, "static")

    @app.route("/")
    def index() -> Union[Response, str]:
        return render_template("index.html")

    @app.route("/status", methods=["GET"])
    def get_status() -> Union[Response, str]:
        _status = _status_exchange.get_status()
        _config = _status_exchange.get_config()
        _progress = _status_exchange.get_progress()
        if _status == Status.NO_INPUT_NEEDED:
            return render_template(
                "no_input.html", status=_status, progress=_progress, config=vars(_config)
            )
        if _status == Status.NEED_MFA:
            return render_template("code.html")
        if _status == Status.NEED_PASSWORD:
            return render_template("password.html", config=_config)
        return render_template("status.html", status=_status)

    @app.route("/code", methods=["POST"])
    def set_code() -> Union[Response, str]:
        _config = _status_exchange.get_config()
        code = request.form.get("code")
        if code is not None:
            if _status_exchange.set_payload(code):
                return render_template("code_submitted.html")
        else:
            logger.error(f"cannot find code in request {request.form}")
        return make_response(
            render_template("auth_error.html", config=_config, type="Two-Factor Code"), 400
        )  # incorrect code

    @app.route("/password", methods=["POST"])
    def set_password() -> Union[Response, str]:
        _config = _status_exchange.get_config()
        password = request.form.get("password")
        if password is not None:
            if _status_exchange.set_payload(password):
                return render_template("password_submitted.html")
        else:
            logger.error(f"cannot find password in request {request.form}")
        return make_response(
            render_template("auth_error.html", config=_config, type="password"), 400
        )  # incorrect code

    @app.route("/resume", methods=["POST"])
    def resume() -> Union[Response, str]:
        _status_exchange.get_progress().resume = True
        return make_response("Ok", 200)

    @app.route("/cancel", methods=["POST"])
    def cancel() -> Union[Response, str]:
        _status_exchange.get_progress().cancel = True
        return make_response("Ok", 200)

    logger.debug("Starting web server...")
    return waitress.serve(app)

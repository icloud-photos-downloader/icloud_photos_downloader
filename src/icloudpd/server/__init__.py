import os
import sys
from logging import Logger

import waitress
from flask import Flask, Response, make_response, render_template, request

from icloudpd.status import Status, StatusExchange


def serve_app(logger: Logger, _status_exchange: StatusExchange, telegram_bot=None, port: int = 8080) -> None:
    app = Flask(__name__)
    app.logger = logger
    # for running in pyinstaller
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir is not None:
        app.template_folder = os.path.join(bundle_dir, "templates")
        app.static_folder = os.path.join(bundle_dir, "static")

    @app.route("/")
    def index() -> Response | str:
        return render_template("index.html")

    @app.route("/status", methods=["GET"])
    def get_status() -> Response | str:
        _status = _status_exchange.get_status()
        _global_config = _status_exchange.get_global_config()
        _user_configs = _status_exchange.get_user_configs()
        _current_user = _status_exchange.get_current_user()
        _progress = _status_exchange.get_progress()
        _error = _status_exchange.get_error()

        if _status == Status.NO_INPUT_NEEDED:
            return render_template(
                "no_input.html",
                status=_status,
                error=_error,
                progress=_progress,
                global_config=vars(_global_config) if _global_config else None,
                user_configs=[vars(uc) for uc in _user_configs] if _user_configs else [],
                current_user=_current_user,
            )
        if _status == Status.NEED_MFA:
            return render_template("code.html", error=_error, current_user=_current_user)
        if _status == Status.NEED_PASSWORD:
            return render_template("password.html", error=_error, current_user=_current_user)
        return render_template("status.html", status=_status)

    @app.route("/code", methods=["POST"])
    def set_code() -> Response | str:
        _current_user = _status_exchange.get_current_user()
        code = request.form.get("code")
        if code is not None:
            if _status_exchange.set_payload(code):
                return render_template("code_submitted.html", current_user=_current_user)
        else:
            logger.error(f"cannot find code in request {request.form}")
        return make_response(
            render_template(
                "auth_error.html",
                type="Two-Factor Code",
                current_user=_current_user,
            ),
            400,
        )  # incorrect code

    @app.route("/password", methods=["POST"])
    def set_password() -> Response | str:
        _current_user = _status_exchange.get_current_user()
        password = request.form.get("password")
        if password is not None:
            if _status_exchange.set_payload(password):
                return render_template("password_submitted.html", current_user=_current_user)
        else:
            logger.error(f"cannot find password in request {request.form}")
        return make_response(
            render_template("auth_error.html", type="password", current_user=_current_user),
            400,
        )  # incorrect code

    @app.route("/resume", methods=["POST"])
    def resume() -> Response | str:
        _status_exchange.get_progress().resume = True
        return make_response("Ok", 200)

    @app.route("/cancel", methods=["POST"])
    def cancel() -> Response | str:
        _status_exchange.get_progress().cancel = True
        return make_response("Ok", 200)

    # Telegram webhook endpoint (for push notifications)
    @app.route("/telegram/webhook", methods=["POST"])
    def telegram_webhook() -> Response:
        if telegram_bot:
            try:
                update = request.get_json()
                if update:
                    telegram_bot.process_update(update)
                return make_response("Ok", 200)
            except Exception as e:
                logger.error(f"Error processing Telegram webhook: {e}")
                return make_response("Error", 500)
        return make_response("Telegram bot not configured", 404)

    logger.debug(f"Starting web server on port {port}...")
    return waitress.serve(app, host="0.0.0.0", port=port)

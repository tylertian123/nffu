import quart.flask_patch

from flask_static_digest import FlaskStaticDigest
from quart import Quart, render_template

import os

# blueprints

# plugins
static_digest = FlaskStaticDigest()
from .static import setup_digest

def create_app():
    app = Quart(__name__)
    app.secret_key = os.urandom(32)

    app.static_folder = "../static"
    app.template_folder = "../templates"

    static_digest.init_app(app)

    # static page routes (frontend)
    @app.route("/app", defaults={"path": ""})
    @app.route("/app/<path:path>")
    async def main(path):
        return await render_template("app.html")

    # setup static digest commands
    setup_digest(app)

    return app

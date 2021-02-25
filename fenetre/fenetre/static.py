from quart import url_for as quart_url_for, current_app
import os
import json

def static_url_for(endpoint, **values):
    if current_app.cache_manifest and "filename" in values:
        values["filename"] = current_app.cache_manifest.get(values["filename"], values["filename"])

    return quart_url_for(endpoint, **values)

def init_app(app):
    try:
        with open(os.path.join(app.static_folder, "manifest.json")) as f:
            app.cache_manifest = json.load(f)
    except FileNotFoundError:
        app.cache_manifest = None

    app.add_template_global(static_url_for)

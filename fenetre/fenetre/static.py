import click

from flask_static_digest.digester import compile as _compile
from flask_static_digest.digester import clean as _clean

def setup_digest(app):
    @app.cli.command()
    def digest_compile():
        """Generate optimized static files and a cache manifest."""
        _compile(str(app.static_folder),
                 str(app.static_folder),
                 app.config.get("FLASK_STATIC_DIGEST_BLACKLIST_FILTER"),
                 app.config.get("FLASK_STATIC_DIGEST_GZIP_FILES"))


    @app.cli.command()
    def digest_clean():
        """Remove generated static files and cache manifest."""
        _clean(str(app.static_folder),
               app.config.get("FLASK_STATIC_DIGEST_BLACKLIST_FILTER"),
               app.config.get("FLASK_STATIC_DIGEST_GZIP_FILES"))

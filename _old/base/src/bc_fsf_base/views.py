"""Views for core plugins"""

from flask import Blueprint, current_app, jsonify, request


bp_captcha = Blueprint('captcha', __name__)


@bp_captcha.get('/challenge')
def challenge():
    """Get a challenge for the current captcha driver"""

    plugin = current_app.plugins.get('captcha')
    if plugin:
        driver = plugin.driver
        if driver:
            return jsonify(driver.challenge(**dict(request.args.items())))
    return jsonify({'error': "No captcha plugin or driver"}, status=404)

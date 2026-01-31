from flask import Blueprint, jsonify
from services.repricer import _execute_repricer

bp = Blueprint('repricer', __name__, url_prefix='/api/repricer')


@bp.route('/run', methods=['POST'])
def run():
    try:
        _execute_repricer()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

import os
from flask import Blueprint, request, session, jsonify

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '')
    password = data.get('password', '')

    expected_user = os.environ.get('APP_USERNAME', 'admin')
    expected_pass = os.environ.get('APP_PASSWORD')

    if not expected_pass:
        return jsonify({'error': 'APP_PASSWORD no configurada en el servidor'}), 500

    if username == expected_user and password == expected_pass:
        session['user'] = username
        return jsonify({'user': username})

    return jsonify({'error': 'Credenciales incorrectas'}), 401


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@bp.route('/me')
def me():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'No autenticado'}), 401
    return jsonify({'user': user})

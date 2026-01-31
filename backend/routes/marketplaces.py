from flask import Blueprint, request, jsonify
from extensions import db, encrypt_value
from models import Marketplace
from clients.mirakl import MiraklClient
from services.repricer import get_client

bp = Blueprint('marketplaces', __name__, url_prefix='/api/marketplaces')


@bp.route('', methods=['GET'])
def listar():
    items = Marketplace.query.order_by(Marketplace.nombre).all()
    return jsonify([m.to_dict() for m in items])


@bp.route('', methods=['POST'])
def crear():
    data = request.json
    mp = Marketplace(
        nombre=data['nombre'],
        tipo=data.get('tipo', 'mirakl'),
        url_api=data['url_api'],
        shop_id=data.get('shop_id'),
        activo=data.get('activo', True),
    )
    if data.get('api_key'):
        mp.api_key_encrypted = encrypt_value(data['api_key'])
    db.session.add(mp)
    db.session.commit()
    return jsonify(mp.to_dict()), 201


@bp.route('/<int:id>', methods=['PUT'])
def actualizar(id):
    mp = Marketplace.query.get_or_404(id)
    data = request.json
    for field in ('nombre', 'tipo', 'url_api', 'shop_id', 'activo'):
        if field in data:
            setattr(mp, field, data[field])
    if data.get('api_key'):
        mp.api_key_encrypted = encrypt_value(data['api_key'])
    db.session.commit()
    return jsonify(mp.to_dict())


@bp.route('/<int:id>', methods=['DELETE'])
def eliminar(id):
    mp = Marketplace.query.get_or_404(id)
    db.session.delete(mp)
    db.session.commit()
    return '', 204


@bp.route('/<int:id>/test', methods=['POST'])
def test_conexion(id):
    mp = Marketplace.query.get_or_404(id)
    client = get_client(mp)
    ok = client.test_connection()
    return jsonify({'ok': ok, 'mock_mode': client.mock_mode})

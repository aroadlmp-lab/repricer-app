from flask import Blueprint, request, jsonify
from extensions import db
from models import Producto

bp = Blueprint('productos', __name__, url_prefix='/api/productos')


@bp.route('', methods=['GET'])
def listar():
    items = Producto.query.order_by(Producto.nombre).all()
    return jsonify([p.to_dict() for p in items])


@bp.route('', methods=['POST'])
def crear():
    data = request.json
    p = Producto(sku=data['sku'], ean=data.get('ean'), nombre=data['nombre'], marca=data.get('marca'))
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@bp.route('/<int:id>', methods=['PUT'])
def actualizar(id):
    p = Producto.query.get_or_404(id)
    data = request.json
    for field in ('sku', 'ean', 'nombre', 'marca'):
        if field in data:
            setattr(p, field, data[field])
    db.session.commit()
    return jsonify(p.to_dict())


@bp.route('/<int:id>', methods=['DELETE'])
def eliminar(id):
    p = Producto.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return '', 204

from flask import Blueprint, request, jsonify
from extensions import db
from models import Oferta

bp = Blueprint('ofertas', __name__, url_prefix='/api/ofertas')


@bp.route('', methods=['GET'])
def listar():
    q = Oferta.query
    mp_id = request.args.get('marketplace_id')
    if mp_id:
        q = q.filter_by(marketplace_id=int(mp_id))
    items = q.order_by(Oferta.id).all()
    return jsonify([o.to_dict() for o in items])


@bp.route('', methods=['POST'])
def crear():
    data = request.json
    o = Oferta(
        marketplace_id=data['marketplace_id'],
        producto_id=data['producto_id'],
        offer_id_externo=data.get('offer_id_externo'),
        precio_actual=data['precio_actual'],
        precio_min=data.get('precio_min'),
        precio_max=data.get('precio_max'),
        stock=data.get('stock', 0),
        activo=data.get('activo', True),
    )
    db.session.add(o)
    db.session.commit()
    return jsonify(o.to_dict()), 201


@bp.route('/<int:id>', methods=['PUT'])
def actualizar(id):
    o = Oferta.query.get_or_404(id)
    data = request.json
    for field in ('precio_actual', 'precio_min', 'precio_max', 'stock', 'activo', 'offer_id_externo'):
        if field in data:
            setattr(o, field, data[field])
    db.session.commit()
    return jsonify(o.to_dict())


@bp.route('/bulk', methods=['PUT'])
def bulk_update():
    items = request.json
    updated = []
    for item in items:
        o = Oferta.query.get(item['id'])
        if o:
            if 'precio_min' in item:
                o.precio_min = item['precio_min']
            if 'precio_max' in item:
                o.precio_max = item['precio_max']
            if 'activo' in item:
                o.activo = item['activo']
            updated.append(o.to_dict())
    db.session.commit()
    return jsonify(updated)


@bp.route('/mock', methods=['DELETE'])
def eliminar_mock():
    mock_ofertas = Oferta.query.filter(
        (Oferta.product_sku == None) | (Oferta.product_sku == '')
    ).all()
    count = len(mock_ofertas)
    for o in mock_ofertas:
        db.session.delete(o)
    db.session.commit()
    return jsonify({'deleted': count})


@bp.route('/<int:id>', methods=['DELETE'])
def eliminar(id):
    o = Oferta.query.get_or_404(id)
    db.session.delete(o)
    db.session.commit()
    return '', 204

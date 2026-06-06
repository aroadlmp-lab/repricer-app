from flask import Blueprint, request, jsonify
from extensions import db
from models import Oferta, Producto

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
    if o.precio_min is not None and o.precio_max is not None and o.precio_min > o.precio_max:
        return jsonify({'error': 'precio_min no puede ser mayor que precio_max'}), 400
    if o.precio_max is not None and o.precio_actual > o.precio_max:
        o.precio_actual = o.precio_max
    if o.precio_min is not None and o.precio_actual < o.precio_min:
        o.precio_actual = o.precio_min
    db.session.commit()
    return jsonify(o.to_dict())


@bp.route('/bulk', methods=['PUT'])
def bulk_update():
    items = request.json
    if not items or not isinstance(items, list):
        return jsonify({'error': 'Se esperaba un array JSON'}), 400
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
    MOCK_SKUS = [
        'IP15-128-BLK', 'IP15-256-BLK', 'IP15P-128-NAT', 'IP15P-256-NAT',
        'IP15PM-256-BLU', 'IP14-128-WHT', 'IP14P-128-PRP', 'IP13-128-GRN',
        'IPSE3-64-RED', 'IPSE3-128-BLK',
    ]
    mock_producto_ids = [p.id for p in Producto.query.filter(Producto.sku.in_(MOCK_SKUS)).all()]
    mock_ofertas = Oferta.query.filter(
        (Oferta.product_sku == None) | (Oferta.product_sku == '') |
        Oferta.producto_id.in_(mock_producto_ids)
    ).all()
    count = len(mock_ofertas)
    for o in mock_ofertas:
        db.session.delete(o)
    # También eliminar los productos mock
    Producto.query.filter(Producto.sku.in_(MOCK_SKUS)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'deleted': count})


@bp.route('/<int:id>/caza', methods=['POST'])
def iniciar_caza(id):
    o = Oferta.query.get_or_404(id)
    data = request.json or {}
    paso = data.get('paso_caza')
    if not paso or float(paso) <= 0:
        return jsonify({'error': 'paso_caza debe ser mayor que 0'}), 400
    if not o.activo:
        return jsonify({'error': 'La oferta debe estar activa para iniciar la caza'}), 400
    o.cazando_minimo = True
    o.paso_caza = float(paso)
    o.estado_caza = 'cazando'
    o.precio_minimo_detectado = None
    db.session.commit()
    return jsonify(o.to_dict())


@bp.route('/<int:id>/caza', methods=['DELETE'])
def cancelar_caza(id):
    o = Oferta.query.get_or_404(id)
    o.cazando_minimo = False
    o.estado_caza = 'inactivo'
    db.session.commit()
    return jsonify(o.to_dict())


@bp.route('/<int:id>', methods=['DELETE'])
def eliminar(id):
    o = Oferta.query.get_or_404(id)
    db.session.delete(o)
    db.session.commit()
    return '', 204

from flask import Blueprint, request, jsonify
from extensions import db, encrypt_value
from models import Marketplace, Producto, Oferta
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


@bp.route('/<int:id>/raw', methods=['GET'])
def raw_offers(id):
    """Debug: ver datos raw de la API."""
    import requests as req
    mp = Marketplace.query.get_or_404(id)
    client = get_client(mp)
    if client.mock_mode:
        return jsonify({'error': 'mock mode'})

    endpoint = request.args.get('endpoint', 'offers')
    try:
        if endpoint == 'p11':
            product_id = request.args.get('product_id', '')
            r = req.get(f'{client.url_api}/api/products/offers', headers=client._headers(),
                        params={'product_ids': product_id}, timeout=15)
        else:
            r = req.get(f'{client.url_api}/api/offers', headers=client._headers(),
                        params={'max': 2}, timeout=15)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:id>/sync', methods=['POST'])
def sincronizar(id):
    mp = Marketplace.query.get_or_404(id)
    client = get_client(mp)
    ofertas_api = client.get_offers()

    if not ofertas_api:
        return jsonify({'status': 'error', 'message': 'No se pudieron obtener ofertas de la API'}), 400

    nuevas = 0
    actualizadas = 0

    for o in ofertas_api:
        # Buscar o crear producto por SKU
        producto = Producto.query.filter_by(sku=o['sku']).first()
        if not producto:
            producto = Producto(
                sku=o['sku'],
                ean=o.get('ean', ''),
                nombre=o.get('product_title', o['sku']),
                marca='',
            )
            db.session.add(producto)
            db.session.flush()

        # Buscar oferta existente por marketplace + offer_id_externo
        oferta = Oferta.query.filter_by(
            marketplace_id=mp.id,
            offer_id_externo=o['offer_id']
        ).first()

        # Guardar product_id si existe, sino product_sku
        p_sku = o.get('product_id', '') or o.get('product_sku', '')

        if oferta:
            oferta.precio_actual = o['price']
            oferta.stock = o['stock']
            oferta.product_sku = p_sku
            actualizadas += 1
        else:
            oferta = Oferta(
                marketplace_id=mp.id,
                producto_id=producto.id,
                offer_id_externo=o['offer_id'],
                product_sku=p_sku,
                precio_actual=o['price'],
                precio_min=round(o['price'] * 0.90, 2),
                precio_max=round(o['price'] * 1.10, 2),
                stock=o['stock'],
                tiene_buybox=False,
                activo=False,
            )
            db.session.add(oferta)
            nuevas += 1

    db.session.commit()
    return jsonify({
        'status': 'ok',
        'ofertas_api': len(ofertas_api),
        'nuevas': nuevas,
        'actualizadas': actualizadas,
    })

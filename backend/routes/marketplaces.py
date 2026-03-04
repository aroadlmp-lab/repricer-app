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
        channel_code=data.get('channel_code'),
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
    for field in ('nombre', 'tipo', 'url_api', 'shop_id', 'shop_name', 'channel_code', 'ignorar_state_code', 'margen_competencia', 'activo'):
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
    mp = Marketplace.query.get_or_404(id)
    client = get_client(mp)
    if client.mock_mode:
        return jsonify({'error': 'mock mode'})
    try:
        r = client._session.get(f'{client.url_api}/api/offers',
                                params={'max': 2}, timeout=15)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:id>/rawp11/<string:product_id>', methods=['GET'])
def raw_p11(id, product_id):
    mp = Marketplace.query.get_or_404(id)
    client = get_client(mp)
    if client.mock_mode:
        return jsonify({'error': 'mock mode'})
    try:
        r = client._session.get(f'{client.url_api}/api/products/offers',
                                params={'product_ids': product_id}, timeout=15)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e), 'status_code': getattr(e, 'response', None) and getattr(e.response, 'status_code', None)}), 500


@bp.route('/<int:id>/sync', methods=['POST'])
def sincronizar(id):
    mp = Marketplace.query.get_or_404(id)
    from services.sync import sync_marketplace
    result = sync_marketplace(mp)
    if result is None:
        return jsonify({'status': 'error', 'message': 'No se pudieron obtener ofertas de la API'}), 400
    return jsonify({'status': 'ok', **result})


@bp.route('/<int:id>/import-status/<int:import_id>', methods=['GET'])
def import_status(id, import_id):
    """Check status of an offer import in Mirakl."""
    mp = Marketplace.query.get_or_404(id)
    client = get_client(mp)
    if client.mock_mode:
        return jsonify({'error': 'mock mode'})
    result = client.get_import_status(import_id)
    return jsonify(result)


@bp.route('/<int:id>/find-sku/<string:sku>', methods=['GET'])
def find_sku(id, sku):
    """Debug: busca un SKU específico en todas las ofertas de Mirakl."""
    mp = Marketplace.query.get_or_404(id)
    client = get_client(mp)
    if client.mock_mode:
        return jsonify({'error': 'mock mode'})

    # Fetch all offers (same as sync/repricer)
    all_offers = client.get_offers()

    # Build dict and find the SKU
    sku_to_offer = {o['sku']: o for o in all_offers}
    found = sku_to_offer.get(sku)

    # Also search partial matches
    partial_matches = [o for o in all_offers if sku.lower() in o['sku'].lower()]

    return jsonify({
        'search_sku': sku,
        'total_offers_from_mirakl': len(all_offers),
        'exact_match': found,
        'partial_matches': partial_matches[:10],  # Limit to 10
    })

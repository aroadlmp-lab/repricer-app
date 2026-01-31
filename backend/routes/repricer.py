from flask import Blueprint, jsonify
from services.repricer import _execute_repricer, get_client
from models import Marketplace, Oferta

bp = Blueprint('repricer', __name__, url_prefix='/api/repricer')


@bp.route('/run', methods=['POST'])
def run():
    try:
        _execute_repricer()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/debug/<int:marketplace_id>', methods=['GET'])
def debug(marketplace_id):
    """Muestra lo que ve el repricer sin hacer cambios."""
    mp = Marketplace.query.get_or_404(marketplace_id)
    client = get_client(mp)
    results = []

    ofertas = Oferta.query.filter_by(marketplace_id=mp.id, activo=True).all()

    for oferta in ofertas:
        offer_id = oferta.offer_id_externo or str(oferta.id)
        bb_error = None
        bb_info = None
        try:
            bb_info = client.get_buybox_info(offer_id)
        except Exception as e:
            bb_error = str(e)

        results.append({
            'oferta_id': oferta.id,
            'offer_id_externo': offer_id,
            'producto': oferta.producto.nombre if oferta.producto else '',
            'precio_db': oferta.precio_actual,
            'precio_min': oferta.precio_min,
            'precio_max': oferta.precio_max,
            'stock': oferta.stock,
            'buybox_info': bb_info,
            'buybox_error': bb_error,
            'mock_mode': client.mock_mode,
        })

    return jsonify({
        'marketplace': mp.nombre,
        'mock_mode': client.mock_mode,
        'ofertas_activas': len(ofertas),
        'detalle': results,
    })

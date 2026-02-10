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
        product_sku = oferta.product_sku or ''
        bb_error = None
        bb_info = None
        try:
            bb_info = client.get_buybox_info(offer_id, product_sku)
        except Exception as e:
            bb_error = str(e)

        results.append({
            'oferta_id': oferta.id,
            'offer_id_externo': offer_id,
            'product_sku': product_sku,
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
        'shop_name': mp.shop_name,
        'ofertas_activas': len(ofertas),
        'detalle': results,
    })


@bp.route('/test-update/<int:oferta_id>', methods=['GET'])
def test_update(oferta_id):
    """Prueba el update_price SIN cambiar el precio (envia el precio actual)."""
    oferta = Oferta.query.get_or_404(oferta_id)
    mp = Marketplace.query.get_or_404(oferta.marketplace_id)
    client = get_client(mp)
    shop_sku = oferta.producto.sku if oferta.producto else ''
    offer_id = oferta.offer_id_externo or str(oferta.id)

    # Fetch all offers from Mirakl to get current quantity (like sync does)
    mirakl_offers = client.get_offers()
    sku_to_quantity = {o['sku']: o['stock'] for o in mirakl_offers}
    mirakl_quantity = sku_to_quantity.get(shop_sku, 0)

    result = client.update_price(offer_id, oferta.precio_actual, shop_sku, quantity=mirakl_quantity)
    return jsonify({
        'offer_id': offer_id,
        'shop_sku': shop_sku,
        'precio': oferta.precio_actual,
        'stock_db': oferta.stock,
        'stock_mirakl': mirakl_quantity,
        'result': result,
    })


@bp.route('/test-update-debug/<int:oferta_id>', methods=['GET'])
def test_update_debug(oferta_id):
    """Prueba update_price y consulta OF73 para ver el estado de la importación."""
    import time
    oferta = Oferta.query.get_or_404(oferta_id)
    mp = Marketplace.query.get_or_404(oferta.marketplace_id)
    client = get_client(mp)
    shop_sku = oferta.producto.sku if oferta.producto else ''
    offer_id = oferta.offer_id_externo or str(oferta.id)

    # 0. Fetch all offers from Mirakl to get current quantity (like sync does)
    mirakl_offers = client.get_offers()
    sku_to_quantity = {o['sku']: o['stock'] for o in mirakl_offers}
    mirakl_quantity = sku_to_quantity.get(shop_sku, 0)

    # 1. Hacer el update con quantity de Mirakl
    update_result = client.update_price(offer_id, oferta.precio_actual, shop_sku, quantity=mirakl_quantity)

    # 2. Extraer import_id del result
    import_id = update_result.get('import_id')
    import_status = None

    # 3. Si tenemos import_id, esperar un momento y consultar OF73
    if import_id:
        time.sleep(2)  # Dar tiempo a Mirakl para procesar
        import_status = client.get_import_status(import_id)

    return jsonify({
        'oferta_id': oferta_id,
        'offer_id_externo': offer_id,
        'shop_sku': shop_sku,
        'precio_enviado': oferta.precio_actual,
        'stock_db': oferta.stock,
        'stock_mirakl': mirakl_quantity,
        'marketplace': mp.nombre,
        'channel_code': mp.channel_code,
        'update_result': update_result,
        'import_id': import_id,
        'import_status': import_status,
    })

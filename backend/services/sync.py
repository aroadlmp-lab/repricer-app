import logging
from extensions import db
from models import Marketplace, Producto, Oferta
from services.repricer import get_client

logger = logging.getLogger(__name__)


def sync_marketplace(mp):
    client = get_client(mp)
    ofertas_api = client.get_offers()

    if not ofertas_api:
        return None

    nuevas = 0
    actualizadas = 0
    ignoradas = 0

    for o in ofertas_api:
        stock = int(o.get('stock', 0))
        p_sku = o.get('product_id', '') or o.get('product_sku', '')

        oferta = Oferta.query.filter_by(
            marketplace_id=mp.id,
            offer_id_externo=o['offer_id']
        ).first()

        # Si stock es 0: actualizar stock si ya existe, pero no crear nueva
        if stock <= 0:
            if oferta:
                oferta.stock = 0
                oferta.product_sku = p_sku
                actualizadas += 1
            else:
                ignoradas += 1
            continue

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

        if oferta:
            oferta.precio_actual = o['price']
            oferta.stock = stock
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
                stock=stock,
                tiene_buybox=False,
                activo=False,
            )
            db.session.add(oferta)
            nuevas += 1

    db.session.commit()
    return {
        'ofertas_api': len(ofertas_api),
        'nuevas': nuevas,
        'actualizadas': actualizadas,
        'ignoradas_sin_stock': ignoradas,
    }


def sync_all(app=None):
    if app:
        ctx = app.app_context()
        ctx.push()
    try:
        marketplaces = Marketplace.query.filter_by(activo=True).all()
        for mp in marketplaces:
            try:
                result = sync_marketplace(mp)
                logger.info(f'Sync {mp.nombre}: {result}')
            except Exception as e:
                logger.error(f'Sync {mp.nombre} failed: {e}')
    finally:
        if app:
            ctx.pop()

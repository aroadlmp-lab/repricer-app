from typing import Optional
from datetime import datetime, timezone
from extensions import db, decrypt_value
from models import Marketplace, Oferta, HistoricoPrecios, Ejecucion
from clients.mirakl import MiraklClient


def get_client(marketplace: Marketplace) -> MiraklClient:
    api_key = None
    if marketplace.api_key_encrypted:
        try:
            api_key = decrypt_value(marketplace.api_key_encrypted)
        except Exception:
            pass
    return MiraklClient(marketplace.url_api, api_key, marketplace.shop_id, marketplace.shop_name,
                        channel_code=marketplace.channel_code)


def run_repricer(app=None):
    if app:
        ctx = app.app_context()
        ctx.push()
    try:
        _execute_repricer()
    finally:
        if app:
            ctx.pop()


def _execute_repricer():
    import logging
    logger = logging.getLogger(__name__)

    marketplaces = Marketplace.query.filter_by(activo=True).all()

    for mp in marketplaces:
        cambios = 0
        procesadas = 0
        errores_list = []

        try:
            client = get_client(mp)

            # Fetch all offers from Mirakl to get current quantities (same as sync)
            mirakl_offers = client.get_offers()
            sku_to_quantity = {o['sku']: o['stock'] for o in mirakl_offers}
            logger.info(f'REPRICER {mp.nombre}: fetched {len(mirakl_offers)} offers from Mirakl, channel_code={mp.channel_code}')

            ofertas = Oferta.query.filter_by(marketplace_id=mp.id, activo=True).filter(Oferta.stock > 0).all()

            for oferta in ofertas:
                procesadas += 1
                try:
                    offer_id = oferta.offer_id_externo or str(oferta.id)
                    product_sku = oferta.product_sku or ''
                    bb_info = client.get_buybox_info(offer_id, product_sku)

                    if bb_info.get('error'):
                        errores_list.append(f'Oferta {oferta.id}: buybox error: {bb_info["error"]}')
                        continue

                    if bb_info.get('competitors', 0) == 0:
                        # No hay competidores o no se pudo obtener info
                        continue

                    all_offers = bb_info.get('all_offers', [])
                    # Filter competitors by same state_code if the offer has one
                    if oferta.state_code:
                        all_offers = [o for o in all_offers if o.get('state_code') == oferta.state_code]
                    nuevo_precio = _calcular_precio(oferta, bb_info, all_offers)

                    # Siempre actualizar estado buybox
                    oferta.tiene_buybox = bb_info['has_buybox']

                    if nuevo_precio and nuevo_precio != oferta.precio_actual:
                        shop_sku = ''
                        if oferta.producto:
                            shop_sku = oferta.producto.sku
                        # Use quantity from Mirakl (fetched at start), not from DB
                        mirakl_quantity = sku_to_quantity.get(shop_sku, 0)
                        result = client.update_price(
                            offer_id, nuevo_precio, shop_sku, quantity=mirakl_quantity,
                        )
                        if result.get('success') and not result.get('skipped'):
                            motivo = _generar_motivo(oferta, bb_info, nuevo_precio)
                            hist = HistoricoPrecios(
                                oferta_id=oferta.id,
                                precio_anterior=oferta.precio_actual,
                                precio_nuevo=nuevo_precio,
                                motivo=motivo,
                                tenia_buybox=bb_info['has_buybox'],
                            )
                            db.session.add(hist)
                            oferta.precio_actual = nuevo_precio
                            cambios += 1
                        elif result.get('skipped'):
                            logger.warning(f'Oferta {oferta.id} ({shop_sku}): skipped - {result.get("reason")}')
                        else:
                            errores_list.append(f'Oferta {oferta.id}: update failed: {result}')
                except Exception as e:
                    errores_list.append(f'Oferta {oferta.id}: {str(e)}')

            db.session.add(Ejecucion(
                marketplace_id=mp.id,
                estado='error' if errores_list else 'ok',
                ofertas_procesadas=procesadas,
                cambios_realizados=cambios,
                errores='; '.join(errores_list) if errores_list else None,
            ))
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            db.session.add(Ejecucion(
                marketplace_id=mp.id,
                estado='error',
                ofertas_procesadas=procesadas,
                cambios_realizados=cambios,
                errores=str(e),
            ))
            db.session.commit()


def _generar_motivo(oferta, bb_info, nuevo_precio):
    best = bb_info.get('best_price', 0)
    if nuevo_precio < oferta.precio_actual:
        return f'Bajar para ganar posicion (mejor precio competidor: {best})'
    else:
        return f'Subir manteniendo mejor posicion (mejor precio competidor: {best})'


def _calcular_precio(oferta: Oferta, bb_info: dict, all_offers: list = None) -> Optional[float]:
    precio = oferta.precio_actual
    precio_min = oferta.precio_min or 0
    precio_max = oferta.precio_max or float('inf')
    best_price = bb_info.get('best_price', 0)

    if not bb_info['has_buybox']:
        # No tenemos la mejor posicion: bajar 0.01 por debajo del mejor competidor (excluyendo nuestras ofertas)
        competitor_best = _find_best_competitor_price(all_offers or [])
        target = competitor_best if competitor_best else best_price
        if target > 0:
            nuevo = round(target - 0.01, 2)
        else:
            nuevo = round(precio - 0.01, 2)
        if nuevo >= precio_min:
            return nuevo
        return None
    else:
        # Tenemos la mejor posicion: subir hasta el siguiente competidor - 0.01
        next_competitor = _find_next_competitor_price(precio, all_offers or [])
        if next_competitor:
            nuevo = round(min(next_competitor - 0.01, precio_max), 2)
        else:
            nuevo = round(precio + 0.01, 2)
        if nuevo <= precio_max and nuevo > precio:
            return nuevo
        return None


def _find_next_competitor_price(my_price: float, all_offers: list) -> Optional[float]:
    """Find the next competitor price above ours (excluding our own offers)."""
    higher_prices = [
        o['price'] for o in all_offers
        if o.get('price', 0) > my_price and not o.get('is_mine', False)
    ]
    return min(higher_prices) if higher_prices else None


def _find_best_competitor_price(all_offers: list) -> Optional[float]:
    """Find the lowest competitor price (excluding our own offers)."""
    competitor_prices = [
        o['price'] for o in all_offers
        if o.get('price', 0) > 0 and not o.get('is_mine', False)
    ]
    return min(competitor_prices) if competitor_prices else None

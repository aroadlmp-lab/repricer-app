import time
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


def _execute_repricer(progress_callback=None):
    import logging
    logger = logging.getLogger(__name__)

    marketplaces = Marketplace.query.filter_by(activo=True).all()

    for mp in marketplaces:
        cambios = 0
        procesadas = 0
        errores_list = []

        try:
            client = get_client(mp)

            if progress_callback:
                progress_callback({'type': 'start', 'marketplace': mp.nombre})

            # Fetch all offers from Mirakl to get current quantities (same as sync)
            mirakl_offers = client.get_offers()
            sku_to_quantity = {o['sku']: o['stock'] for o in mirakl_offers}
            logger.info(f'REPRICER {mp.nombre}: fetched {len(mirakl_offers)} offers from Mirakl, channel_code={mp.channel_code}')

            ofertas = Oferta.query.filter_by(marketplace_id=mp.id, activo=True).filter(Oferta.stock > 0).all()
            total = len(ofertas)

            if progress_callback:
                progress_callback({'type': 'total', 'marketplace': mp.nombre, 'total': total})

            for oferta in ofertas:
                procesadas += 1
                try:
                    offer_id = oferta.offer_id_externo or str(oferta.id)
                    product_sku = oferta.product_sku or ''
                    time.sleep(0.3)  # Pausa entre llamadas P11 para no superar el rate limit
                    bb_info = client.get_buybox_info(offer_id, product_sku)

                    if bb_info.get('error'):
                        errores_list.append(f'Oferta {oferta.id}: buybox error: {bb_info["error"]}')
                        continue

                    if bb_info.get('competitors', 0) == 0:
                        # No hay competidores o no se pudo obtener info
                        continue

                    all_offers = bb_info.get('all_offers', [])
                    # Filter competitors by state_code
                    if mp.ignorar_state_code:
                        # Phonehouse-style: compete against all refurbished, exclude Nuevo (state_code 11)
                        all_offers = [o for o in all_offers if o.get('state_code') != '11']
                    elif oferta.state_code:
                        # Default: only compare against same state
                        all_offers = [o for o in all_offers if o.get('state_code') == oferta.state_code]

                    # Recompute has_buybox based on the filtered offers to avoid mismatch:
                    # bb_info['has_buybox'] was computed before state filtering, so a cheaper
                    # excluded competitor (e.g. NUEVO in Phonehouse) could wrongly set has_buybox=False
                    # while the filtered set only has more expensive competitors above us.
                    # Use total_price (price + shipping) for accurate market comparison.
                    bb_info_calc = dict(bb_info)
                    competitor_totals_filtered = [
                        o.get('total_price', o['price']) for o in all_offers
                        if not o.get('is_mine', False) and o.get('price', 0) > 0
                    ]
                    competitor_prices_filtered = [
                        o['price'] for o in all_offers
                        if not o.get('is_mine', False) and o.get('price', 0) > 0
                    ]
                    my_offers_filtered = [o for o in all_offers if o.get('is_mine', False)]
                    my_total_filtered = my_offers_filtered[0].get('total_price', my_offers_filtered[0]['price']) if my_offers_filtered else bb_info.get('my_price', 0)
                    if competitor_totals_filtered:
                        best_total = min(competitor_totals_filtered)
                        best_price_display = min(competitor_prices_filtered)
                        bb_info_calc['has_buybox'] = my_total_filtered > 0 and my_total_filtered <= best_total
                        bb_info_calc['best_price'] = round(best_price_display, 2)  # price sin shipping para display
                    elif all_offers:
                        # Only our own offers remain after filtering → we have the buybox
                        bb_info_calc['has_buybox'] = my_total_filtered > 0

                    margen = getattr(mp, 'margen_competencia', 0.0) or 0.0
                    nuevo_precio = _calcular_precio(oferta, bb_info_calc, all_offers, margen=margen)

                    # Siempre actualizar estado buybox y precio buybox usando datos
                    # filtrados (bb_info_calc) para que el display sea consistente
                    # con la lógica de cálculo (excluye NUEVO en ignorar_state_code)
                    oferta.tiene_buybox = bb_info_calc['has_buybox']
                    if competitor_prices_filtered:
                        # Solo guardar el mejor precio del segmento filtrado (REAC, no NUEVO)
                        oferta.precio_buybox = bb_info_calc['best_price']

                    if nuevo_precio and nuevo_precio != oferta.precio_actual:
                        shop_sku = ''
                        if oferta.producto:
                            shop_sku = oferta.producto.sku
                        # Use quantity from Mirakl (fetched at start), not from DB.
                        # Diferenciar "no encontrado" (posible filtro por channel_code)
                        # de "encontrado con stock 0" (realmente sin stock).
                        if shop_sku in sku_to_quantity:
                            mirakl_quantity = sku_to_quantity[shop_sku]
                        else:
                            mirakl_quantity = oferta.stock
                            logger.warning(f'SKU {shop_sku!r} not in sku_to_quantity (channel filter?), using DB stock={oferta.stock}')
                        result = client.update_price(
                            offer_id, nuevo_precio, shop_sku, quantity=mirakl_quantity,
                            description=oferta.descripcion,
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

                if progress_callback:
                    progress_callback({
                        'type': 'progress',
                        'marketplace': mp.nombre,
                        'procesadas': procesadas,
                        'total': total,
                        'cambios': cambios,
                    })

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


def _calcular_precio(oferta: Oferta, bb_info: dict, all_offers: list = None, margen: float = 0.0) -> Optional[float]:
    """Calcula el nuevo precio óptimo.

    margen (%) — margen adicional por debajo del competidor para compensar
    desventaja de seller score (ej: 5 → apuntar a competidor × 0.95 - 0.01).
    Con margen=0 el comportamiento es idéntico al original (-0.01 del competidor).
    """
    precio = oferta.precio_actual
    precio_min = oferta.precio_min or 0
    precio_max = oferta.precio_max or float('inf')
    best_price = bb_info.get('best_price', 0)
    factor = 1.0 - (margen / 100.0)

    if not bb_info['has_buybox']:
        # No tenemos la mejor posicion: bajar por debajo del mejor competidor aplicando margen
        competitor_best = _find_best_competitor_price(all_offers or [])
        target = competitor_best if competitor_best else best_price
        if target > 0:
            nuevo = round(min(target * factor - 0.01, precio_max), 2)
        else:
            nuevo = round(precio - 0.01, 2)
        if nuevo >= precio_min:
            return nuevo
        return None
    else:
        # Tenemos la mejor posicion: subir hasta el siguiente competidor respetando el margen
        next_competitor = _find_next_competitor_price(precio, all_offers or [])
        if next_competitor:
            nuevo = round(min(next_competitor * factor - 0.01, precio_max), 2)
            if margen > 0:
                # Con margen activo: puede necesitar bajar para mantener la distancia con el competidor
                if nuevo >= precio_min and nuevo != precio:
                    return nuevo
                return None
            else:
                # Sin margen: solo subir (comportamiento original)
                if nuevo <= precio_max and nuevo > precio:
                    return nuevo
                return None
        else:
            # Sin competidores por encima
            if margen > 0:
                return None  # No hay referencia para calcular el target
            nuevo = round(precio + 0.01, 2)
            if nuevo <= precio_max:
                return nuevo
            return None


def _find_next_competitor_price(my_price: float, all_offers: list) -> Optional[float]:
    """Find the next competitor total_price above ours (excluding our own offers)."""
    higher_prices = [
        o.get('total_price', o['price']) for o in all_offers
        if o.get('total_price', o.get('price', 0)) > my_price and not o.get('is_mine', False)
    ]
    return min(higher_prices) if higher_prices else None


def _find_best_competitor_price(all_offers: list) -> Optional[float]:
    """Find the lowest competitor total_price (excluding our own offers)."""
    competitor_prices = [
        o.get('total_price', o['price']) for o in all_offers
        if o.get('price', 0) > 0 and not o.get('is_mine', False)
    ]
    return min(competitor_prices) if competitor_prices else None

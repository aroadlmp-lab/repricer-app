import time
import logging
from typing import Optional
from extensions import db, decrypt_value
from models import Marketplace, Oferta, HistoricoPrecios, Ejecucion
from clients.mirakl import MiraklClient
from services.locks import get_marketplace_lock

logger = logging.getLogger(__name__)


def get_client(marketplace: Marketplace):
    api_key = None
    if marketplace.api_key_encrypted:
        try:
            api_key = decrypt_value(marketplace.api_key_encrypted)
        except Exception as e:
            logger.error(f'[{marketplace.nombre}] Error desencriptando API key: {e}. El marketplace operará en mock mode (sin llamadas reales a Mirakl).')
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

    marketplaces = Marketplace.query.filter_by(activo=True).all()

    for mp in marketplaces:
        cambios = 0
        procesadas = 0
        errores_list = []

        lock = get_marketplace_lock(mp.id)
        if not lock.acquire(blocking=False):
            logger.warning(f'REPRICER {mp.nombre}: saltado este ciclo, ya hay un sync/repricer en curso')
            if progress_callback:
                progress_callback({'type': 'skipped', 'marketplace': mp.nombre, 'reason': 'ya en curso'})
            continue

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

            # Para ignorar_state_code: pre-construir mapa base_sku -> set(product_skus)
            # para poder consultar P11 de todos los estados del mismo producto físico y
            # compararlos entre sí (funcional vs muy bueno vs como nuevo).
            # Phonehouse usa product_ids distintos para cada condición del mismo modelo,
            # así que enlazamos por EAN (mismo EAN = mismo modelo físico, distinta condición).
            producto_variants = {}  # ean -> set(product_skus) para fusión cross-estado
            if mp.ignorar_state_code:
                all_mp_offers = Oferta.query.filter(
                    Oferta.marketplace_id == mp.id,
                    Oferta.product_sku.isnot(None),
                ).all()
                for o in all_mp_offers:
                    if o.product_sku and o.producto and o.producto.ean:
                        ean = o.producto.ean
                        producto_variants.setdefault(ean, set()).add(o.product_sku)
                multi = {e: s for e, s in producto_variants.items() if len(s) > 1}
                logger.info(f'REPRICER {mp.nombre}: ignorar_state_code=True, '
                            f'{len(producto_variants)} EANs, {len(multi)} con multiples product_skus: {multi}')

            # Cache de P11 por product_sku para no repetir la misma llamada
            p11_cache = {}

            for oferta in ofertas:
                procesadas += 1
                try:
                    offer_id = oferta.offer_id_externo or str(oferta.id)
                    product_sku = oferta.product_sku or ''

                    # P11 call con cache para evitar duplicados
                    if product_sku not in p11_cache:
                        time.sleep(0.3)  # Rate limiting
                        p11_cache[product_sku] = client.get_buybox_info(offer_id, product_sku)
                    bb_info = p11_cache[product_sku]

                    if bb_info.get('error'):
                        errores_list.append(f'Oferta {oferta.id}: buybox error: {bb_info["error"]}')
                        continue

                    if bb_info.get('competitors', 0) == 0:
                        # No hay competidores o no se pudo obtener info
                        continue

                    # Comenzar con las ofertas del estado propio (de P11 original)
                    all_offers = list(bb_info.get('all_offers', []))

                    # Extraer nuestro precio ANTES de fusionar otros estados.
                    # Cuando hay múltiples ofertas propias (ej: muy bueno + funcional del mismo
                    # vendedor en el mismo P11), buscar la que coincide con oferta.precio_actual
                    # para no confundir estados y calcular has_buybox incorrectamente.
                    original_my_offers = [o for o in all_offers if o.get('is_mine', False)]
                    # Buscar nuestra oferta específica por 'price' (precio unitario sin envío),
                    # que coincide con oferta.precio_actual. Usar total_price para el matching
                    # era menos fiable porque puede incluir gastos de envío variables.
                    matching_mine = [
                        o for o in original_my_offers
                        if abs(o.get('price', 0) - oferta.precio_actual) < 0.02
                    ]
                    my_offer = matching_mine[0] if matching_mine else (original_my_offers[0] if original_my_offers else None)
                    my_total_price = (
                        my_offer.get('total_price', my_offer['price'])
                        if my_offer
                        else oferta.precio_actual  # fallback directo si no encontramos la oferta en P11
                    )
                    logger.info(f'REPRICER {mp.nombre}: oferta {oferta.id} '
                                f'my_offers_count={len(original_my_offers)} '
                                f'matching={len(matching_mine)} '
                                f'my_total={my_total_price} precio_actual={oferta.precio_actual}')

                    # Para ignorar_state_code: fusionar P11 de los otros estados del mismo producto.
                    # Esto permite ver si un competidor de distinto estado (ej: muy bueno) está
                    # más barato y gana la buybox, algo invisible si solo consultamos nuestro estado.
                    if mp.ignorar_state_code and product_sku:
                        ean = oferta.producto.ean if oferta.producto else ''
                        related_skus = (producto_variants.get(ean, set()) - {product_sku}) if ean else set()
                        logger.info(f'REPRICER {mp.nombre}: oferta {oferta.id} psku={product_sku!r} '
                                    f'ean={ean!r} related={related_skus} '
                                    f'has_buybox_raw={bb_info.get("has_buybox")} my_total={my_total_price}')
                        for rel_sku in sorted(related_skus):
                            if rel_sku not in p11_cache:
                                time.sleep(0.3)
                                p11_cache[rel_sku] = client.get_buybox_info('', rel_sku)
                            rel_bb = p11_cache[rel_sku]
                            if not rel_bb.get('error'):
                                all_offers.extend(rel_bb.get('all_offers', []))

                    # Filter competitors by state_code
                    if mp.ignorar_state_code:
                        # Phonehouse-style: compete against all refurbished, exclude Nuevo (state_code 11)
                        all_offers = [o for o in all_offers if o.get('state_code') != '11']
                    elif oferta.state_code:
                        # Default: only compare against same state
                        all_offers = [o for o in all_offers if o.get('state_code') == oferta.state_code]

                    # Recompute has_buybox con el conjunto fusionado y filtrado.
                    # En ignorar_state_code usamos my_total_price del estado propio (extraído antes
                    # del merge) para comparar contra el mejor precio del mercado unificado.
                    bb_info_calc = dict(bb_info)
                    competitor_totals_filtered = [
                        o.get('total_price', o['price']) for o in all_offers
                        if not o.get('is_mine', False) and o.get('price', 0) > 0
                    ]
                    competitor_prices_filtered = [
                        o['price'] for o in all_offers
                        if not o.get('is_mine', False) and o.get('price', 0) > 0
                    ]
                    if competitor_totals_filtered:
                        best_total = min(competitor_totals_filtered)
                        best_price_display = min(competitor_prices_filtered)
                        bb_info_calc['has_buybox'] = my_total_price > 0 and my_total_price <= best_total
                        bb_info_calc['best_price'] = round(best_price_display, 2)
                    elif all_offers:
                        # Solo quedan nuestras propias ofertas → tenemos la buybox
                        bb_info_calc['has_buybox'] = my_total_price > 0

                    es_caza = getattr(oferta, 'cazando_minimo', False) and getattr(oferta, 'estado_caza', 'inactivo') == 'cazando'
                    if es_caza:
                        nuevo_precio = _calcular_precio_caza(oferta, bb_info_calc, competitor_prices_filtered)
                    else:
                        margen = getattr(mp, 'margen_competencia', 0.0) or 0.0
                        nuevo_precio = _calcular_precio(oferta, bb_info_calc, all_offers, margen=margen, my_total_price=my_total_price)
                    logger.info(f'REPRICER {mp.nombre}: oferta {oferta.id} '
                                f'has_buybox={bb_info_calc["has_buybox"]} '
                                f'best={bb_info_calc.get("best_price")} '
                                f'actual={oferta.precio_actual} min={oferta.precio_min} max={oferta.precio_max} '
                                f'nuevo={nuevo_precio}'
                                + (f' [CAZA estado={oferta.estado_caza}]' if es_caza else ''))

                    # Actualizar estado buybox y precio buybox con datos del mercado unificado
                    oferta.tiene_buybox = bb_info_calc['has_buybox']
                    if competitor_prices_filtered:
                        oferta.precio_buybox = bb_info_calc['best_price']

                    if nuevo_precio and nuevo_precio != oferta.precio_actual:
                        shop_sku = ''
                        if oferta.producto:
                            shop_sku = oferta.producto.sku
                        # Use quantity from Mirakl (fetched at start), not from DB.
                        if shop_sku in sku_to_quantity:
                            mirakl_quantity = sku_to_quantity[shop_sku]
                        else:
                            mirakl_quantity = oferta.stock
                            logger.warning(f'[{mp.nombre}] Oferta {oferta.id} SKU {shop_sku!r} no encontrado en sku_to_quantity '
                                           f'(posible filtro channel_code={mp.channel_code!r}), usando DB stock={oferta.stock}')
                        result = client.update_price(
                            offer_id, nuevo_precio, shop_sku, quantity=mirakl_quantity,
                            description=oferta.descripcion,
                        )
                        if result.get('success') and not result.get('skipped'):
                            if es_caza:
                                if oferta.estado_caza == 'completado' and oferta.precio_minimo_detectado:
                                    motivo = f'Caza completada: mínimo competidor={oferta.precio_minimo_detectado}€, subiendo a {nuevo_precio}€'
                                else:
                                    motivo = f'Caza: bajando {oferta.paso_caza}€/ciclo (mín. propio: {oferta.precio_min}€)'
                            else:
                                motivo = _generar_motivo(oferta, bb_info_calc, nuevo_precio)
                            hist = HistoricoPrecios(
                                oferta_id=oferta.id,
                                precio_anterior=oferta.precio_actual,
                                precio_nuevo=nuevo_precio,
                                motivo=motivo,
                                tenia_buybox=bb_info_calc['has_buybox'],
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

            if not errores_list:
                estado = 'ok'
            elif procesadas > len(errores_list):
                estado = 'parcial'
            else:
                estado = 'error'
            db.session.add(Ejecucion(
                marketplace_id=mp.id,
                estado=estado,
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
        finally:
            lock.release()


def _generar_motivo(oferta, bb_info, nuevo_precio):
    best = bb_info.get('best_price', 0)
    if nuevo_precio < oferta.precio_actual:
        return f'Bajar para ganar posicion (mejor precio competidor: {best})'
    else:
        return f'Subir manteniendo mejor posicion (mejor precio competidor: {best})'


def _calcular_precio(oferta: Oferta, bb_info: dict, all_offers: list = None, margen: float = 0.0, my_total_price: float = None) -> Optional[float]:
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
        next_competitor = _find_next_competitor_price(my_total_price if my_total_price else precio, all_offers or [])
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


def _calcular_precio_caza(oferta: Oferta, bb_info: dict, competitor_prices_filtered: list) -> Optional[float]:
    """Lógica de caza de mínimo: baja agresivamente hasta ganar buybox, luego sube al piso del competidor."""
    has_buybox = bb_info['has_buybox']
    precio_min = oferta.precio_min or 0
    precio_max = oferta.precio_max or float('inf')

    if has_buybox and competitor_prices_filtered:
        # El competidor llegó a su mínimo y nosotros ganamos: su precio actual ES su mínimo
        comp_min = round(min(competitor_prices_filtered), 2)
        oferta.precio_minimo_detectado = comp_min
        oferta.estado_caza = 'completado'
        oferta.cazando_minimo = False
        logger.info(f'CAZA COMPLETADA: oferta {oferta.id} precio_min_competidor={comp_min}')
        # Subir al máximo posible justo por debajo del mínimo del competidor
        target = round(min(comp_min - 0.01, precio_max), 2)
        if target > oferta.precio_actual and target >= precio_min:
            return target
        return None
    elif has_buybox:
        # Sin competidores en segmento: completar sin mínimo detectado
        oferta.estado_caza = 'completado'
        oferta.cazando_minimo = False
        logger.info(f'CAZA COMPLETADA: oferta {oferta.id} sin competidores en segmento filtrado')
        return None
    else:
        # Seguimos sin buybox: bajar otro paso
        nuevo = round(oferta.precio_actual - oferta.paso_caza, 2)
        if nuevo < precio_min:
            oferta.estado_caza = 'abortado'
            oferta.cazando_minimo = False
            logger.warning(f'CAZA ABORTADA: oferta {oferta.id} siguiente paso={nuevo} < precio_min={precio_min}')
            return None
        return nuevo

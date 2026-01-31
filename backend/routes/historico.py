from flask import Blueprint, request, jsonify
from models import HistoricoPrecios, Ejecucion, Oferta

bp = Blueprint('historico', __name__, url_prefix='/api/historico')


@bp.route('', methods=['GET'])
def listar():
    q = HistoricoPrecios.query
    mp_id = request.args.get('marketplace_id')
    if mp_id:
        oferta_ids = [o.id for o in Oferta.query.filter_by(marketplace_id=int(mp_id)).all()]
        q = q.filter(HistoricoPrecios.oferta_id.in_(oferta_ids))
    limit = request.args.get('limit', 50, type=int)
    items = q.order_by(HistoricoPrecios.created_at.desc()).limit(limit).all()
    return jsonify([h.to_dict() for h in items])


@bp.route('/ejecuciones', methods=['GET'])
def ejecuciones():
    mp_id = request.args.get('marketplace_id')
    q = Ejecucion.query
    if mp_id:
        q = q.filter_by(marketplace_id=int(mp_id))
    limit = request.args.get('limit', 20, type=int)
    items = q.order_by(Ejecucion.created_at.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in items])


@bp.route('/stats', methods=['GET'])
def stats():
    from sqlalchemy import func
    from models import Oferta, Marketplace

    total_ofertas = Oferta.query.filter_by(activo=True).count()
    con_buybox = Oferta.query.filter_by(activo=True, tiene_buybox=True).count()
    total_marketplaces = Marketplace.query.filter_by(activo=True).count()

    from datetime import datetime, timezone, timedelta
    hoy = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cambios_hoy = HistoricoPrecios.query.filter(HistoricoPrecios.created_at >= hoy).count()

    alertas = Oferta.query.filter(
        Oferta.activo == True,
        Oferta.precio_min != None,
        Oferta.precio_actual <= Oferta.precio_min
    ).count()

    return jsonify({
        'total_ofertas': total_ofertas,
        'con_buybox': con_buybox,
        'pct_buybox': round(con_buybox / total_ofertas * 100, 1) if total_ofertas else 0,
        'total_marketplaces': total_marketplaces,
        'cambios_hoy': cambios_hoy,
        'alertas': alertas,
    })

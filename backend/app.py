import os
import logging
import sys
from flask import Flask, send_from_directory, session, jsonify, request
from flask_cors import CORS
from extensions import db, migrate

# Configure logging to stdout for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path='')

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///repricer.db'
    ).replace('postgres://', 'postgresql://')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('RAILWAY_ENVIRONMENT') is not None

    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)

    from routes import marketplaces, productos, ofertas, historico, repricer, auth
    app.register_blueprint(auth.bp)
    app.register_blueprint(marketplaces.bp)
    app.register_blueprint(productos.bp)
    app.register_blueprint(ofertas.bp)
    app.register_blueprint(historico.bp)
    app.register_blueprint(repricer.bp)

    @app.before_request
    def require_auth():
        if request.path.startswith('/api/') and not request.path.startswith('/api/auth/'):
            if 'user' not in session:
                return jsonify({'error': 'No autenticado'}), 401

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if path and os.path.exists(os.path.join(FRONTEND_DIST, path)):
            return send_from_directory(FRONTEND_DIST, path)
        index = os.path.join(FRONTEND_DIST, 'index.html')
        if os.path.exists(index):
            return send_from_directory(FRONTEND_DIST, 'index.html')
        return '<!doctype html><html><body><h1>Repricer API</h1><p>Frontend not built. Run: cd frontend && npm run build</p></body></html>'

    with app.app_context():
        db.create_all()
        _add_missing_columns()

    if os.environ.get('ENABLE_SCHEDULER', '').lower() in ('true', '1', 'yes'):
        _start_scheduler(app)

    return app


def _start_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
    from services.repricer import run_repricer
    from services.sync import sync_all

    scheduler = BackgroundScheduler()

    def job_error_listener(event):
        logger.error(f'Scheduler job error: job={event.job_id}, exception={event.exception}')

    def job_missed_listener(event):
        logger.warning(f'Scheduler job missed: job={event.job_id}')

    scheduler.add_listener(job_error_listener, EVENT_JOB_ERROR)
    scheduler.add_listener(job_missed_listener, EVENT_JOB_MISSED)

    scheduler.add_job(
        func=run_repricer, trigger='interval', minutes=15,
        args=[app], id='repricer_job',
        max_instances=1, coalesce=True, misfire_grace_time=300,
    )
    scheduler.add_job(
        func=sync_all, trigger='cron', hour=6, minute=0,
        args=[app], id='sync_job',
        max_instances=1, coalesce=True, misfire_grace_time=600,
    )
    scheduler.start()
    logger.info('Scheduler started: repricer (15min) + sync (daily 06:00 UTC)')


def _add_missing_columns():
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('ofertas')]
    if 'product_sku' not in columns:
        db.session.execute(text('ALTER TABLE ofertas ADD COLUMN product_sku VARCHAR(100)'))
    if 'state_code' not in columns:
        db.session.execute(text('ALTER TABLE ofertas ADD COLUMN state_code VARCHAR(20)'))
    mp_columns = [c['name'] for c in inspector.get_columns('marketplaces')]
    if 'shop_name' not in mp_columns:
        db.session.execute(text('ALTER TABLE marketplaces ADD COLUMN shop_name VARCHAR(100)'))
    if 'channel_code' not in mp_columns:
        db.session.execute(text('ALTER TABLE marketplaces ADD COLUMN channel_code VARCHAR(20)'))
    if 'ignorar_state_code' not in mp_columns:
        db.session.execute(text('ALTER TABLE marketplaces ADD COLUMN ignorar_state_code BOOLEAN DEFAULT FALSE'))
    if 'margen_competencia' not in mp_columns:
        db.session.execute(text('ALTER TABLE marketplaces ADD COLUMN margen_competencia FLOAT DEFAULT 0'))
    oferta_columns = [c['name'] for c in inspector.get_columns('ofertas')]
    if 'descripcion' not in oferta_columns:
        db.session.execute(text('ALTER TABLE ofertas ADD COLUMN descripcion TEXT'))
    if 'precio_buybox' not in oferta_columns:
        db.session.execute(text('ALTER TABLE ofertas ADD COLUMN precio_buybox FLOAT'))
    if 'cazando_minimo' not in oferta_columns:
        db.session.execute(text('ALTER TABLE ofertas ADD COLUMN cazando_minimo BOOLEAN DEFAULT FALSE'))
    if 'paso_caza' not in oferta_columns:
        db.session.execute(text('ALTER TABLE ofertas ADD COLUMN paso_caza FLOAT'))
    if 'precio_minimo_detectado' not in oferta_columns:
        db.session.execute(text('ALTER TABLE ofertas ADD COLUMN precio_minimo_detectado FLOAT'))
    if 'estado_caza' not in oferta_columns:
        db.session.execute(text("ALTER TABLE ofertas ADD COLUMN estado_caza VARCHAR(20) DEFAULT 'inactivo'"))
    # Clean orphan historico_precios records (oferta was deleted)
    db.session.execute(text('''
        DELETE FROM historico_precios
        WHERE oferta_id NOT IN (SELECT id FROM ofertas)
    '''))
    db.session.commit()



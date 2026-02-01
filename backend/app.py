import os
import logging
from flask import Flask, send_from_directory
from flask_cors import CORS
from extensions import db, migrate

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path='')

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///repricer.db'
    ).replace('postgres://', 'postgresql://')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)

    from routes import marketplaces, productos, ofertas, historico, repricer
    app.register_blueprint(marketplaces.bp)
    app.register_blueprint(productos.bp)
    app.register_blueprint(ofertas.bp)
    app.register_blueprint(historico.bp)
    app.register_blueprint(repricer.bp)

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
        _seed_if_empty()

    if os.environ.get('ENABLE_SCHEDULER', '').lower() in ('true', '1', 'yes'):
        _start_scheduler(app)

    return app


def _start_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler
    from services.repricer import run_repricer
    from services.sync import sync_all

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=run_repricer, trigger='interval', minutes=15,
        args=[app], id='repricer_job',
    )
    scheduler.add_job(
        func=sync_all, trigger='cron', hour=6, minute=0,
        args=[app], id='sync_job',
    )
    scheduler.start()
    logger.info('Scheduler started: repricer (15min) + sync (daily 06:00 UTC)')


def _add_missing_columns():
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('ofertas')]
    if 'product_sku' not in columns:
        db.session.execute(text('ALTER TABLE ofertas ADD COLUMN product_sku VARCHAR(100)'))
    mp_columns = [c['name'] for c in inspector.get_columns('marketplaces')]
    if 'shop_name' not in mp_columns:
        db.session.execute(text('ALTER TABLE marketplaces ADD COLUMN shop_name VARCHAR(100)'))
    db.session.commit()


def _seed_if_empty():
    from models import Marketplace, Producto, Oferta

    if Marketplace.query.count() > 0:
        return

    mp1 = Marketplace(nombre='Carrefour', tipo='mirakl', url_api='https://carrefour-mirakl.example.com')
    mp2 = Marketplace(nombre='Phonehouse', tipo='mirakl', url_api='https://phonehouse-mirakl.example.com')
    db.session.add_all([mp1, mp2])
    db.session.flush()

    productos_data = [
        ('IP15-128-BLK', '1234567890001', 'iPhone 15 128GB Negro', 'Apple'),
        ('IP15-256-BLK', '1234567890002', 'iPhone 15 256GB Negro', 'Apple'),
        ('IP15P-128-NAT', '1234567890003', 'iPhone 15 Pro 128GB Natural', 'Apple'),
        ('IP15P-256-NAT', '1234567890004', 'iPhone 15 Pro 256GB Natural', 'Apple'),
        ('IP15PM-256-BLU', '1234567890005', 'iPhone 15 Pro Max 256GB Azul', 'Apple'),
        ('IP14-128-WHT', '1234567890006', 'iPhone 14 128GB Blanco', 'Apple'),
        ('IP14P-128-PRP', '1234567890007', 'iPhone 14 Pro 128GB Morado', 'Apple'),
        ('IP13-128-GRN', '1234567890008', 'iPhone 13 128GB Verde', 'Apple'),
        ('IPSE3-64-RED', '1234567890009', 'iPhone SE 3 64GB Rojo', 'Apple'),
        ('IPSE3-128-BLK', '1234567890010', 'iPhone SE 3 128GB Negro', 'Apple'),
    ]

    productos = []
    for sku, ean, nombre, marca in productos_data:
        p = Producto(sku=sku, ean=ean, nombre=nombre, marca=marca)
        productos.append(p)
    db.session.add_all(productos)
    db.session.flush()

    import random
    precios_base = [899.99, 999.99, 1099.99, 1199.99, 1299.99, 699.99, 899.99, 599.99, 429.99, 479.99]

    for mp in [mp1, mp2]:
        for i, prod in enumerate(productos):
            precio = precios_base[i] + random.uniform(-20, 20)
            precio = round(precio, 2)
            oferta = Oferta(
                marketplace_id=mp.id,
                producto_id=prod.id,
                offer_id_externo=str(1000 + i + (10 if mp == mp2 else 0)),
                precio_actual=precio,
                precio_min=round(precio * 0.85, 2),
                precio_max=round(precio * 1.10, 2),
                stock=random.randint(0, 15),
                tiene_buybox=random.random() > 0.4,
                activo=True,
            )
            db.session.add(oferta)

    db.session.commit()

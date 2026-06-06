from datetime import datetime, timezone
from extensions import db


class Marketplace(db.Model):
    __tablename__ = 'marketplaces'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), nullable=False, default='mirakl')
    url_api = db.Column(db.String(255), nullable=False)
    api_key_encrypted = db.Column(db.Text, nullable=True)
    shop_id = db.Column(db.String(50), nullable=True)
    shop_name = db.Column(db.String(100), nullable=True)
    channel_code = db.Column(db.String(20), nullable=True)
    ignorar_state_code = db.Column(db.Boolean, default=False)
    margen_competencia = db.Column(db.Float, default=0.0)
    activo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    ofertas = db.relationship('Oferta', backref='marketplace', lazy='dynamic')
    ejecuciones = db.relationship('Ejecucion', backref='marketplace', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'tipo': self.tipo,
            'url_api': self.url_api,
            'shop_id': self.shop_id,
            'shop_name': self.shop_name,
            'channel_code': self.channel_code,
            'ignorar_state_code': self.ignorar_state_code,
            'margen_competencia': self.margen_competencia or 0.0,
            'activo': self.activo,
            'tiene_api_key': self.api_key_encrypted is not None,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
        }


class Producto(db.Model):
    __tablename__ = 'productos'

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    ean = db.Column(db.String(13), nullable=True)
    nombre = db.Column(db.String(255), nullable=False)
    marca = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    ofertas = db.relationship('Oferta', backref='producto', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.sku,
            'ean': self.ean,
            'nombre': self.nombre,
            'marca': self.marca,
        }


class Oferta(db.Model):
    __tablename__ = 'ofertas'

    id = db.Column(db.Integer, primary_key=True)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplaces.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    offer_id_externo = db.Column(db.String(100), nullable=True)
    product_sku = db.Column(db.String(100), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    precio_actual = db.Column(db.Float, nullable=False)
    precio_min = db.Column(db.Float, nullable=True)
    precio_max = db.Column(db.Float, nullable=True)
    precio_buybox = db.Column(db.Float, nullable=True)
    stock = db.Column(db.Integer, default=0)
    state_code = db.Column(db.String(20), nullable=True)
    tiene_buybox = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)
    cazando_minimo = db.Column(db.Boolean, default=False)
    paso_caza = db.Column(db.Float, nullable=True)
    precio_minimo_detectado = db.Column(db.Float, nullable=True)
    estado_caza = db.Column(db.String(20), default='inactivo')  # inactivo, cazando, completado, abortado
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    historico = db.relationship('HistoricoPrecios', backref='oferta', lazy='dynamic',
                                order_by='HistoricoPrecios.created_at.desc()',
                                cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('ix_ofertas_marketplace_activo', 'marketplace_id', 'activo'),
        db.Index('ix_ofertas_marketplace_id', 'marketplace_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'marketplace_id': self.marketplace_id,
            'producto_id': self.producto_id,
            'offer_id_externo': self.offer_id_externo,
            'product_sku': self.product_sku,
            'descripcion': self.descripcion,
            'precio_actual': self.precio_actual,
            'precio_min': self.precio_min,
            'precio_max': self.precio_max,
            'precio_buybox': self.precio_buybox,
            'stock': self.stock,
            'state_code': self.state_code,
            'tiene_buybox': self.tiene_buybox,
            'activo': self.activo,
            'cazando_minimo': self.cazando_minimo or False,
            'paso_caza': self.paso_caza,
            'precio_minimo_detectado': self.precio_minimo_detectado,
            'estado_caza': self.estado_caza or 'inactivo',
            'updated_at': (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
            'producto': self.producto.to_dict() if self.producto else None,
            'marketplace_nombre': self.marketplace.nombre if self.marketplace else None,
        }


class HistoricoPrecios(db.Model):
    __tablename__ = 'historico_precios'

    id = db.Column(db.Integer, primary_key=True)
    oferta_id = db.Column(db.Integer, db.ForeignKey('ofertas.id'), nullable=False)
    precio_anterior = db.Column(db.Float, nullable=False)
    precio_nuevo = db.Column(db.Float, nullable=False)
    motivo = db.Column(db.String(255), nullable=True)
    tenia_buybox = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.Index('ix_historico_oferta_id', 'oferta_id'),
        db.Index('ix_historico_created_at', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'oferta_id': self.oferta_id,
            'precio_anterior': self.precio_anterior,
            'precio_nuevo': self.precio_nuevo,
            'motivo': self.motivo,
            'tenia_buybox': self.tenia_buybox,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'oferta': {
                'producto': self.oferta.producto.to_dict() if self.oferta and self.oferta.producto else None,
                'marketplace_nombre': self.oferta.marketplace.nombre if self.oferta and self.oferta.marketplace else None,
            } if self.oferta else None,
        }


class Ejecucion(db.Model):
    __tablename__ = 'ejecuciones'

    id = db.Column(db.Integer, primary_key=True)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplaces.id'), nullable=True)
    estado = db.Column(db.String(20), default='ok')  # ok, error, parcial
    __table_args__ = (
        db.Index('ix_ejecuciones_created_at', 'created_at'),
    )
    ofertas_procesadas = db.Column(db.Integer, default=0)
    cambios_realizados = db.Column(db.Integer, default=0)
    errores = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'marketplace_id': self.marketplace_id,
            'marketplace_nombre': self.marketplace.nombre if self.marketplace else 'Global',
            'estado': self.estado,
            'ofertas_procesadas': self.ofertas_procesadas,
            'cambios_realizados': self.cambios_realizados,
            'errores': self.errores,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
        }

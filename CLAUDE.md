# Repricer App

Herramienta de repricing automático para marketplaces Mirakl. Monitoriza precios de competidores y ajusta automáticamente los nuestros para ganar/mantener la buybox respetando márgenes.

## Stack

- **Backend:** Flask 3.0, SQLAlchemy, APScheduler, Gunicorn
- **Frontend:** React 18, Vite 5, Tailwind CSS 3, React Router 6, Axios
- **BD:** PostgreSQL (producción) / SQLite (desarrollo)
- **Deploy:** Railway (GitHub auto-deploy), también soporta Render y Docker

## Estructura de archivos

```
backend/
├── app.py                  # Factory create_app(), scheduler, migraciones manuales
├── run.py                  # Entry point dev (ENABLE_SCHEDULER=true)
├── extensions.py           # db, migrate, encrypt/decrypt (Fernet)
├── models.py               # Marketplace, Producto, Oferta, HistoricoPrecios, Ejecucion
├── requirements.txt
├── clients/
│   ├── base.py             # ABC MarketplaceClient
│   └── mirakl.py           # Cliente Mirakl (get_offers, get_buybox_info, update_price, mock)
├── services/
│   ├── repricer.py         # Lógica de repricing (_calcular_precio, _find_next_competitor_price)
│   └── sync.py             # Sincronización de ofertas (sync_marketplace, sync_all)
└── routes/
    ├── auth.py             # Login, logout, sesión (/api/auth/*)
    ├── marketplaces.py     # CRUD + test + sync + raw debug
    ├── productos.py        # CRUD productos
    ├── ofertas.py          # CRUD + bulk + DELETE mock
    ├── historico.py        # Historial de precios, ejecuciones, stats
    └── repricer.py         # Ejecución manual + debug buybox

frontend/src/
├── App.jsx                 # Router + auth gate (muestra Login o Layout)
├── api.js                  # Axios con baseURL /api
├── components/
│   ├── Layout.jsx          # Nav + selector de marketplace + botón logout
│   ├── StatsCards.jsx      # Tarjetas dashboard
│   ├── LogsPanel.jsx       # Panel de cambios de precio
│   └── OfertasTable.jsx    # Tabla ofertas con edición inline, toggle activo, buybox
└── pages/
    ├── Login.jsx           # Formulario de login
    ├── Dashboard.jsx       # Stats + últimos cambios + botón ejecutar repricer
    ├── Ofertas.jsx         # Listado con filtros pill, buscador, ordenación
    ├── Historico.jsx       # Ejecuciones + historial de precios
    └── Marketplaces.jsx    # Config marketplaces (API key, shop_id, shop_name, sync, test)
```

## Modelos de datos

- **Marketplace** — nombre, tipo, url_api, api_key_encrypted, shop_id, shop_name, activo
- **Producto** — sku (unique), ean, nombre, marca
- **Oferta** — marketplace_id, producto_id, offer_id_externo, product_sku, precio_actual, precio_min, precio_max, stock, tiene_buybox, activo
- **HistoricoPrecios** — oferta_id, precio_anterior, precio_nuevo, motivo, tenia_buybox
- **Ejecucion** — marketplace_id, estado (ok/error), ofertas_procesadas, cambios_realizados, errores

Relaciones: Marketplace → [Oferta, Ejecucion], Producto → [Oferta], Oferta → [HistoricoPrecios]

## Lógica de repricing

Ejecuta cada 15 minutos para cada marketplace activo:

1. Obtiene ofertas activas con stock > 0
2. Para cada oferta, llama a P11 (`GET /api/products/offers`) con `product_sku`
3. Identifica ofertas propias por `shop_name` (campo `is_mine` en all_offers)
4. Calcula nuevo precio:
   - **Sin buybox:** bajar a `mejor_precio_competidor - 0.01` (excluyendo ofertas propias), respetando `precio_min`
   - **Con buybox:** subir hasta `siguiente_competidor - 0.01`, respetando `precio_max`. Si no hay competidor por encima, sube 0.01
5. Actualiza precio vía OF24 (`POST /api/offers`) enviando `shop_sku`, `price`, `quantity`
6. Actualiza `tiene_buybox` en cada ejecución (no solo al cambiar precio)
7. Registra cambio en HistoricoPrecios y crea Ejecucion

## Sincronización

- **Manual:** `POST /api/marketplaces/:id/sync`
- **Automática:** Diaria a las 06:00 UTC (scheduler)
- Ofertas con stock 0 se eliminan de la BD al sincronizar; no se crean nuevas sin stock
- Ofertas nuevas (con stock > 0) se crean con `activo=False`, precio_min=90%, precio_max=110%

## Variables de entorno

| Variable | Uso | Default |
|---|---|---|
| `DATABASE_URL` | Conexión PostgreSQL | `sqlite:///repricer.db` |
| `SECRET_KEY` | Flask session | `dev-secret-key` |
| `FERNET_KEY` | Cifrado API keys | Auto-generado |
| `ENABLE_SCHEDULER` | Activa scheduler (true/1/yes) | No activo |
| `APP_USERNAME` | Usuario para login | `admin` |
| `APP_PASSWORD` | Contraseña para login (**requerida**) | — |

En Railway: `ENABLE_SCHEDULER=true` es necesario para que el repricer y sync automático funcionen. `APP_PASSWORD` es obligatoria para que el login funcione.

## Autenticación

Login con formulario, sesión Flask con cookie. Credenciales configuradas via `APP_USERNAME` y `APP_PASSWORD`.

- `before_request` en app.py protege todas las rutas `/api/*` excepto `/api/auth/*`
- Frontend: App.jsx comprueba `/api/auth/me` al montar; si 401, muestra página de Login
- Layout incluye botón "Salir" que llama a `/api/auth/logout`

## API endpoints

### Auth `/api/auth`
- `POST /login` — Login (body: `username`, `password`), crea sesión
- `POST /logout` — Cierra sesión
- `GET /me` — Devuelve usuario actual o 401

### Marketplaces `/api/marketplaces`
- `GET /` — Listar
- `POST /` — Crear (cifra api_key)
- `PUT /:id` — Actualizar
- `DELETE /:id` — Eliminar
- `POST /:id/test` — Test conexión
- `POST /:id/sync` — Sincronizar ofertas
- `GET /:id/raw` — Debug: ofertas crudas de la API
- `GET /:id/rawp11/:product_id` — Debug: respuesta P11

### Ofertas `/api/ofertas`
- `GET /` — Listar (filtro: `marketplace_id`)
- `POST /` — Crear
- `PUT /:id` — Actualizar (auto-ajusta precio si supera min/max)
- `PUT /bulk` — Actualización masiva
- `DELETE /mock` — Borrar ofertas mock (SKUs de prueba)
- `DELETE /:id` — Eliminar

### Historial `/api/historico`
- `GET /` — Cambios de precio (filtro: `marketplace_id`, `limit`)
- `GET /ejecuciones` — Logs de ejecuciones
- `GET /stats` — Estadísticas dashboard

### Repricer `/api/repricer`
- `POST /run` — Ejecutar manualmente
- `GET /debug/:marketplace_id` — Debug buybox sin hacer cambios
- `GET /test-update/:oferta_id` — Test update (envía precio actual)

## Cliente Mirakl

`clients/mirakl.py` — Si `api_key` es None, entra en **mock mode** (datos ficticios, sin llamadas reales).

Endpoints Mirakl usados:
- `GET /api/offers` (paginado, max=100) — Listado de ofertas propias
- `GET /api/products/offers` (P11) — Ofertas de todos los vendedores por producto
- `POST /api/offers` (OF24) — Actualización de precio

## Frontend

- Selector de marketplace global en Layout (filtra todas las vistas)
- Ofertas: ordenadas activas primero, filtros pill (Todas/Activas/Sin buybox), buscador por nombre/SKU/EAN/offer ID/marketplace
- Al guardar precio_min/max, el backend ajusta automáticamente precio_actual si queda fuera de rango
- Buybox se muestra como punto verde/rojo
- Timestamps se almacenan en UTC y se envían con sufijo `Z` para que el navegador los convierta a hora local

## Deploy

Railway despliega automáticamente al hacer `git push origin main`. El build ejecuta `build.sh` (pip install + npm build). Gunicorn llama a `app:create_app()`.

## Notas importantes

- `shop_name` en Marketplace debe coincidir exactamente con el nombre de tu tienda en Mirakl para que la identificación de ofertas propias funcione
- El repricer excluye ofertas propias al calcular precios (evita autocompetencia cuando hay varias unidades)
- `product_sku` en Oferta es el ID de producto en Mirakl (necesario para P11), distinto del SKU del producto
- Las migraciones manuales en `_add_missing_columns()` añaden columnas si no existen (product_sku, shop_name)

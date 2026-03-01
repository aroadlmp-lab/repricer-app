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
│   └── OfertasTable.jsx    # Tabla ofertas con edición inline, toggle activo, buybox, precio buybox
└── pages/
    ├── Login.jsx           # Formulario de login
    ├── Dashboard.jsx       # Stats + últimos cambios + botón ejecutar repricer
    ├── Ofertas.jsx         # Listado con filtros pill, buscador, ordenación
    ├── Historico.jsx       # Ejecuciones (con errores expandibles) + historial de precios
    └── Marketplaces.jsx    # Config marketplaces (API key, shop_id, shop_name, channel_code, ignorar_state_code, sync, test)
```

## Modelos de datos

- **Marketplace** — nombre, tipo, url_api, api_key_encrypted, shop_id, shop_name, channel_code, ignorar_state_code, activo
- **Producto** — sku (unique), ean, nombre, marca
- **Oferta** — marketplace_id, producto_id, offer_id_externo, product_sku, descripcion, precio_actual, precio_min, precio_max, precio_buybox, stock, state_code, tiene_buybox, activo
- **HistoricoPrecios** — oferta_id, precio_anterior, precio_nuevo, motivo, tenia_buybox
- **Ejecucion** — marketplace_id, estado (ok/parcial/error), ofertas_procesadas, cambios_realizados, errores

Relaciones: Marketplace → [Oferta, Ejecucion], Producto → [Oferta], Oferta → [HistoricoPrecios (cascade delete)]

## Lógica de repricing

Ejecuta cada 15 minutos para cada marketplace activo:

1. **Obtiene TODAS las ofertas de Mirakl** al inicio usando `get_offers()` (igual que el sync)
2. Crea diccionario `{sku: quantity}` con los stocks reales de Mirakl
3. Para cada oferta activa con stock > 0 en la BD:
   - Espera 0.3s antes de llamar a P11 (rate limiting preventivo)
   - Llama a P11 (`GET /api/products/offers`) con `product_sku` para obtener competidores. Reintenta hasta 3 veces si recibe 429 (respetando `Retry-After`)
   - Identifica ofertas propias por `shop_name` (campo `is_mine` en all_offers)
   - Filtra competidores por `state_code`:
     - Si `marketplace.ignorar_state_code=True`: excluye solo `state_code=11` (Nuevo), compite contra todos los reacondicionados
     - Si no: filtra por mismo `state_code` exacto (comportamiento por defecto)
   - **Recalcula `has_buybox`** sobre el conjunto filtrado (no el global de P11) para evitar que un NUEVO excluido fuerce `has_buybox=False` cuando en realidad somos el REAC más barato
4. Calcula nuevo precio:
   - **Sin buybox:** bajar a `min(mejor_precio_competidor - 0.01, precio_max)` (excluyendo ofertas propias), respetando `precio_min`. Si el competidor está por encima de `precio_max`, baja hasta `precio_max` en lugar de quedarse paralizado
   - **Con buybox:** subir hasta `min(siguiente_competidor - 0.01, precio_max)`. Si no hay competidor por encima, sube 0.01
5. Si hay cambio de precio:
   - Busca el `quantity` real en el diccionario (obtenido en paso 1):
     - SKU **encontrado con quantity=0** → salta el update (sin stock real)
     - SKU **no encontrado** en el dict (posible filtro por `channel_code` en `get_offers()`) → usa `oferta.stock` como fallback y loguea warning en Railway
   - Actualiza vía OF24 (`POST /api/offers`): envía `price` + `quantity` + `description` + `all_prices` si hay `channel_code`
6. Actualiza `tiene_buybox` y `precio_buybox` usando el **segmento filtrado** (no el mercado global). En marketplaces con `ignorar_state_code`, refleja la posición en el segmento REAC, no frente a NUEVO. `precio_buybox` solo se actualiza cuando hay competidores en el segmento filtrado
7. Registra cambio en HistoricoPrecios y crea Ejecucion

## Sincronización

- **Manual:** `POST /api/marketplaces/:id/sync`
- **Automática:** Diaria a las 06:00 UTC (scheduler)
- Ofertas con stock 0 se eliminan de la BD al sincronizar (junto con su histórico de precios); no se crean nuevas sin stock
- Ofertas nuevas (con stock > 0) se crean con `activo=False`, precio_min=90%, precio_max=110%
- Al sincronizar se guarda el `state_code` y la `descripcion` de cada oferta

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
- `GET /:id/raw` — Debug: ofertas crudas de la API (primeras 2)
- `GET /:id/rawp11/:product_id` — Debug: respuesta P11
- `GET /:id/import-status/:import_id` — Debug: estado de importación OF73 (ver si Mirakl procesó el update)
- `GET /:id/find-sku/:sku` — Debug: busca un SKU en todas las ofertas de Mirakl (muestra stock real)

### Ofertas `/api/ofertas`
- `GET /` — Listar (filtro: `marketplace_id`)
- `POST /` — Crear
- `PUT /:id` — Actualizar (auto-ajusta precio si supera min/max)
- `PUT /bulk` — Actualización masiva
- `DELETE /mock` — Borrar ofertas mock (SKUs de prueba)
- `DELETE /:id` — Eliminar

### Historial `/api/historico`
- `GET /` — Cambios de precio (filtro: `marketplace_id`, `limit`)
- `GET /ejecuciones` — Logs de ejecuciones (incluye campo `errores` con texto del fallo)
- `GET /stats` — Estadísticas dashboard

### Repricer `/api/repricer`
- `POST /run` — Ejecutar manualmente (streaming NDJSON: emite eventos `start/total/progress` con marketplace, procesadas, total, cambios)
- `GET /debug/:marketplace_id` — Debug buybox sin hacer cambios
- `GET /test-update/:oferta_id` — Test update (envía precio actual, obtiene quantity de Mirakl)
- `GET /test-update-debug/:oferta_id` — Test update completo con diagnóstico: muestra stock_db, stock_mirakl, import_id e import_status de Mirakl

## Cliente Mirakl

`clients/mirakl.py` — Si `api_key` es None, entra en **mock mode** (datos ficticios, sin llamadas reales). Acepta `channel_code` opcional para soporte multi-canal. Incluye logging de cada update para debug.

Endpoints Mirakl usados:
- `GET /api/offers` (paginado, max=100) — Listado de ofertas propias. El repricer usa esto al inicio para obtener TODAS las ofertas con sus quantities reales. Si `channel_code` está configurado, filtra ofertas por canal (campo `channels[]` es array de strings) y extrae precio del canal desde `all_prices`
- `GET /api/products/offers` (P11) — Ofertas de todos los vendedores por producto. Extrae precio del canal si `channel_code` está configurado. Incluye retry automático con backoff en caso de 429 (hasta 3 intentos, respeta `Retry-After`)
- `POST /api/offers` (OF24) — Actualización de precio. Envía `price` + `quantity` + `description` (para no borrarla) + `all_prices` si `channel_code` está configurado
- `GET /api/offers/imports/:id` (OF73) — Estado de importación. Útil para debug cuando OF24 retorna 201 pero el precio no cambia

## Frontend

- Selector de marketplace global en Layout (filtra todas las vistas)
- Ofertas: ordenadas activas primero, filtros pill (Todas/Activas/Sin buybox), buscador por nombre/SKU/EAN/offer ID/marketplace
- Tabla de ofertas incluye columna **Mejor precio** (precio buybox del mercado): azul si no tenemos buybox, verde si sí la tenemos. Se actualiza en cada ejecución del repricer
- Al guardar precio_min/max, el backend ajusta automáticamente precio_actual si queda fuera de rango
- Buybox se muestra como punto verde/rojo
- Histórico: ejecuciones con error muestran botón "Ver error" que expande el texto exacto del fallo. Badge naranja para estado `parcial`
- Timestamps se almacenan en UTC y se envían con sufijo `Z` para que el navegador los convierta a hora local
- El botón "Ejecutar repricer" del Dashboard muestra una **barra de progreso en tiempo real**: spinner, nombre del marketplace activo, contador `N / M ofertas`, cambios realizados en vivo y tiempo transcurrido. El backend hace streaming NDJSON (`application/x-ndjson`) desde un thread secundario con Queue; el frontend lo consume con `fetch` + `ReadableStream` (Axios no soporta streaming)

## Deploy

Railway despliega automáticamente al hacer `git push origin main`. El build ejecuta `build.sh` (pip install + npm build). Gunicorn llama a `app:create_app()`.

## Notas importantes

- `shop_name` en Marketplace debe coincidir exactamente con el nombre de tu tienda en Mirakl para que la identificación de ofertas propias funcione
- El repricer excluye ofertas propias al calcular precios (evita autocompetencia cuando hay varias unidades)
- `product_sku` en Oferta es el ID de producto en Mirakl (necesario para P11), distinto del SKU del producto
- Las migraciones manuales en `_add_missing_columns()` añaden columnas si no existen (product_sku, shop_name, channel_code, state_code, ignorar_state_code, descripcion, precio_buybox) y limpian registros huérfanos de historico_precios
- `channel_code` en Marketplace permite que dos marketplaces compartan la misma API pero gestionen precios por canal (ej: Pixmania ES con `ES_B2C`, Pixmania FR con `B2C`)
- `state_code` en Oferta indica el estado de reacondicionado del producto
- `ignorar_state_code` en Marketplace: cuando es `True`, el repricer no filtra por estado exacto sino que compite contra todos los reacondicionados excluyendo Nuevo (`state_code=11`). Útil para Phonehouse, donde los estados son NUEVO / REACONDICIONADO-FUNCIONAL / REACONDICIONADO-MUY BUENO / REACONDICIONADO-COMO NUEVO
- `descripcion` en Oferta: se guarda desde el campo `description` de la API de Mirakl y se incluye siempre en el payload OF24 para evitar que Mirakl la borre al actualizar el precio
- `precio_buybox` en Oferta: precio más bajo del **segmento filtrado** (ganador de buybox dentro del estado de reacondicionado relevante), actualizado en cada ejecución del repricer. En marketplaces con `ignorar_state_code`, refleja el mínimo REAC, no el global (que podría ser un NUEVO más barato). Si no hay competidores en el segmento filtrado, el campo no se actualiza (conserva el valor de la última ejecución con competidores). Se muestra en la tabla de ofertas
- **Rate limiting P11:** el repricer espera 0.3s entre llamadas P11 y reintenta automáticamente hasta 3 veces si recibe 429. Carrefour tiene límite de peticiones por minuto en la API
- **Scheduler:** configurado con `max_instances=1` y `coalesce=True` para evitar solapamiento de ejecuciones si una tarda más de 15 min. Incluye listener de errores para logging explícito en Railway
- **IMPORTANTE:** El repricer obtiene TODAS las ofertas de Mirakl al inicio (usando `get_offers()`, igual que el sync) y crea un diccionario `{sku: quantity}`. Para cada update distingue dos casos: (1) SKU **encontrado con quantity=0** → salta el update (sin stock real, evita re-listar productos vendidos); (2) SKU **no encontrado** en el dict (puede ocurrir cuando `channel_code` filtra `get_offers()` y la oferta pertenece a otro canal) → usa `oferta.stock` de la BD como fallback y loguea un warning en Railway para facilitar el diagnóstico
- **IMPORTANTE (has_buybox filtrado):** El campo `has_buybox` que devuelve P11 se calcula sobre el mercado global (incluye NUEVO y REAC). Tras filtrar `all_offers` por `state_code`, el repricer **recalcula `has_buybox`** sobre el conjunto filtrado. Esto evita que un competidor NUEVO más barato (excluido en marketplaces con `ignorar_state_code`) fuerce `has_buybox=False` e impida subir precio cuando en realidad somos el REAC más barato del segmento. El mismo `has_buybox` recalculado se usa tanto para la lógica de precio como para actualizar `tiene_buybox` en la BD
- Algunos marketplaces (Carrefour, Phonehouse) resetean `quantity` a 0 si no se incluye en el update, por eso siempre se envía
- Los logs de Railway muestran `REPRICER {marketplace}: fetched X offers from Mirakl` al inicio y `UPDATE_PRICE:` con el payload exacto enviado
- Gunicorn tiene timeout de 300s para permitir que el repricer procese muchas ofertas sin ser matado
- Los SKUs pueden contener comas (ej: `#RN0007,`, `#RN0007,,`) — esto es intencional para diferenciar estados de reacondicionado
- El logging está configurado en `app.py` para enviar a stdout y ser visible en Railway Deploy Logs

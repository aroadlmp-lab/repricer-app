import random
from typing import Optional, List
import requests
from .base import MarketplaceClient


class MiraklClient(MarketplaceClient):
    def __init__(self, url_api: str, api_key: Optional[str] = None,
                 shop_id: Optional[str] = None, shop_name: Optional[str] = None,
                 channel_code: Optional[str] = None):
        self.url_api = url_api.rstrip('/')
        self.api_key = api_key
        self.shop_id = shop_id
        self.shop_name = shop_name
        self.channel_code = channel_code
        self.mock_mode = api_key is None

    def _headers(self):
        return {'Authorization': self.api_key, 'Accept': 'application/json'}

    def test_connection(self) -> bool:
        if self.mock_mode:
            return True
        try:
            r = requests.get(f'{self.url_api}/api/offers', headers=self._headers(),
                             params={'max': 1}, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def get_offers(self):
        if self.mock_mode:
            return self._mock_offers()
        all_offers = []
        offset = 0
        while True:
            try:
                r = requests.get(f'{self.url_api}/api/offers', headers=self._headers(),
                                 params={'max': 100, 'offset': offset}, timeout=30)
                r.raise_for_status()
                data = r.json()
                offers = data.get('offers', [])
                if not offers:
                    break
                for o in offers:
                    # Filter by channel if configured
                    if self.channel_code:
                        channels = o.get('channels', [])
                        if self.channel_code not in channels:
                            continue

                    # Extract price: prefer channel-specific price from all_prices
                    price = float(o.get('price', 0))
                    if self.channel_code and o.get('all_prices'):
                        for ap in o['all_prices']:
                            if ap.get('channel_code') == self.channel_code:
                                price = float(ap.get('price', price))
                                break
                        else:
                            for ap in o['all_prices']:
                                if ap.get('channel_code') is None:
                                    price = float(ap.get('price', price))
                                    break

                    all_offers.append({
                        'offer_id': str(o.get('offer_id', o.get('id', ''))),
                        'sku': o.get('shop_sku', ''),
                        'product_sku': o.get('product_sku', ''),
                        'product_title': o.get('product_title', o.get('description', '')),
                        'price': price,
                        'stock': int(o.get('quantity', 0)),
                        'state_code': o.get('state_code', o.get('offer_state_code', '')),
                        'ean': o.get('product_references', [{}])[0].get('reference', '') if o.get('product_references') else '',
                    })
                if len(offers) < 100:
                    break
                offset += 100
            except Exception:
                break
        return all_offers

    def get_buybox_info(self, offer_id: str, product_sku: str = '') -> dict:
        """Usa P11 (GET /api/products/offers) para obtener ofertas competidoras."""
        if self.mock_mode:
            return self._mock_buybox(offer_id)
        if not product_sku:
            return {'has_buybox': False, 'best_price': 0, 'my_price': 0, 'competitors': 0, 'all_offers': []}
        try:
            r = requests.get(f'{self.url_api}/api/products/offers', headers=self._headers(),
                             params={'product_ids': product_sku}, timeout=15)
            r.raise_for_status()
            data = r.json()

            all_product_offers = []
            my_price = 0
            best_price = float('inf')

            for product in data.get('products', []):
                for offer in product.get('offers', []):
                    # Extract price: prefer channel-specific from all_prices
                    price = float(offer.get('price', 0))
                    if self.channel_code and offer.get('all_prices'):
                        for ap in offer['all_prices']:
                            if ap.get('channel_code') == self.channel_code:
                                price = float(ap.get('price', price))
                                break
                        else:
                            for ap in offer['all_prices']:
                                if ap.get('channel_code') is None:
                                    price = float(ap.get('price', price))
                                    break

                    s_name = offer.get('shop_name', '')
                    state = offer.get('state_code', '')
                    is_mine = bool(self.shop_name and s_name == self.shop_name)
                    all_product_offers.append({
                        'shop_name': s_name,
                        'price': price,
                        'state_code': state,
                        'is_mine': is_mine,
                    })
                    if price > 0 and price < best_price:
                        best_price = price
                    # Match by shop_name
                    if self.shop_name and s_name == self.shop_name:
                        my_price = price

            if best_price == float('inf'):
                best_price = 0

            has_buybox = my_price > 0 and my_price <= best_price

            return {
                'has_buybox': has_buybox,
                'best_price': round(best_price, 2),
                'my_price': round(my_price, 2),
                'competitors': len(all_product_offers),
                'all_offers': all_product_offers,
            }
        except Exception as e:
            return {'has_buybox': False, 'best_price': 0, 'my_price': 0, 'competitors': 0,
                    'all_offers': [], 'error': str(e)}

    def update_price(self, offer_id: str, price: float, shop_sku: str = '',
                     quantity: int = None) -> dict:
        """Actualiza precio via OF24 (POST /api/offers). Solo envía price + campos obligatorios."""
        if self.mock_mode:
            return {'success': True}
        try:
            offer_data = {
                'shop_sku': shop_sku,
                'price': price,  # Always required by Mirakl
            }
            # Add channel-specific price if configured
            if self.channel_code:
                offer_data['all_prices'] = [{'channel_code': self.channel_code, 'unit_origin_price': price}]
            # Solo incluir quantity si lo tenemos
            if quantity is not None:
                offer_data['quantity'] = quantity

            payload = {'offers': [offer_data]}
            r = requests.post(f'{self.url_api}/api/offers', headers=self._headers(),
                              json=payload, timeout=10)

            if r.status_code in (200, 201, 204):
                return {'success': True, 'status_code': r.status_code, 'sent': offer_data}

            return {
                'success': False,
                'status_code': r.status_code,
                'body': r.text[:500],
                'sent': offer_data,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _mock_offers(self):
        skus = [
            ('IP15-128-BLK', 899.99), ('IP15-256-BLK', 999.99), ('IP15P-128-NAT', 1099.99),
            ('IP15P-256-NAT', 1199.99), ('IP15PM-256-BLU', 1299.99),
            ('IP14-128-WHT', 699.99), ('IP14P-128-PRP', 899.99),
            ('IP13-128-GRN', 599.99), ('IPSE3-64-RED', 429.99), ('IPSE3-128-BLK', 479.99),
        ]
        return [
            {'offer_id': str(1000 + i), 'sku': sku, 'product_sku': f'PROD-{i}',
             'price': price, 'stock': random.randint(0, 20)}
            for i, (sku, price) in enumerate(skus)
        ]

    def _mock_buybox(self, offer_id: str) -> dict:
        has_bb = random.random() > 0.4
        base_price = 500 + random.random() * 800
        return {
            'has_buybox': has_bb,
            'best_price': round(base_price, 2),
            'my_price': round(base_price + random.uniform(-10, 10), 2),
            'competitors': random.randint(1, 8),
            'all_offers': [],
        }

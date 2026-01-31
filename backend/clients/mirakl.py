import random
from typing import Optional, List
import requests
from .base import MarketplaceClient


class MiraklClient(MarketplaceClient):
    def __init__(self, url_api: str, api_key: Optional[str] = None, shop_id: Optional[str] = None):
        self.url_api = url_api.rstrip('/')
        self.api_key = api_key
        self.shop_id = shop_id
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
                    all_offers.append({
                        'offer_id': str(o.get('offer_id', o.get('id', ''))),
                        'sku': o.get('shop_sku', ''),
                        'product_sku': o.get('product_sku', ''),
                        'product_title': o.get('product_title', o.get('description', '')),
                        'price': float(o.get('price', 0)),
                        'stock': int(o.get('quantity', 0)),
                        'state_code': o.get('offer_state_code', ''),
                        'ean': o.get('product_references', [{}])[0].get('reference', '') if o.get('product_references') else '',
                    })
                if len(offers) < 100:
                    break
                offset += 100
            except Exception:
                break
        return all_offers

    def get_buybox_info(self, offer_id: str, product_sku: str = '') -> dict:
        """Usa P11 (GET /api/products/offers) para obtener ofertas competidoras del mismo producto."""
        if self.mock_mode:
            return self._mock_buybox(offer_id)
        if not product_sku:
            return {'has_buybox': False, 'best_price': 0, 'my_price': 0, 'competitors': 0, 'all_offers': []}
        try:
            r = requests.get(f'{self.url_api}/api/products/offers', headers=self._headers(),
                             params={'product_sku': product_sku, 'max': 50}, timeout=15)
            r.raise_for_status()
            data = r.json()

            all_product_offers = []
            my_price = 0
            best_price = float('inf')

            for product in data.get('products', []):
                for offer in product.get('offers', []):
                    price = float(offer.get('price', 0))
                    oid = str(offer.get('id', ''))
                    shop = str(offer.get('shop_id', ''))
                    all_product_offers.append({
                        'offer_id': oid,
                        'shop_id': shop,
                        'price': price,
                        'state_code': offer.get('state_code', ''),
                    })
                    if price > 0 and price < best_price:
                        best_price = price
                    if self.shop_id and shop == self.shop_id:
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

    def update_price(self, offer_id: str, price: float) -> bool:
        if self.mock_mode:
            return True
        try:
            payload = {'offers': [{'offer_id': int(offer_id), 'price': price}]}
            r = requests.put(f'{self.url_api}/api/offers', headers=self._headers(),
                             json=payload, timeout=10)
            return r.status_code in (200, 201, 204)
        except Exception:
            return False

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

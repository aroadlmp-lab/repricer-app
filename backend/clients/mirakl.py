import random
from typing import Optional
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

    def get_offers(self) -> list[dict]:
        if self.mock_mode:
            return self._mock_offers()
        try:
            r = requests.get(f'{self.url_api}/api/offers', headers=self._headers(),
                             params={'max': 100}, timeout=30)
            r.raise_for_status()
            data = r.json()
            return [
                {
                    'offer_id': str(o.get('offer_id', o.get('id', ''))),
                    'sku': o.get('shop_sku', ''),
                    'price': float(o.get('price', 0)),
                    'stock': int(o.get('quantity', 0)),
                }
                for o in data.get('offers', [])
            ]
        except Exception:
            return []

    def get_buybox_info(self, offer_id: str) -> dict:
        if self.mock_mode:
            return self._mock_buybox(offer_id)
        try:
            r = requests.get(f'{self.url_api}/api/offers/{offer_id}/pricing',
                             headers=self._headers(), timeout=10)
            r.raise_for_status()
            data = r.json()
            return {
                'has_buybox': data.get('winner', False),
                'buybox_price': float(data.get('best_price', 0)),
                'competitors': data.get('total_offers', 0),
            }
        except Exception:
            return {'has_buybox': False, 'buybox_price': 0, 'competitors': 0}

    def update_price(self, offer_id: str, price: float) -> bool:
        if self.mock_mode:
            return True
        try:
            payload = {'offers': [{'offer_id': int(offer_id), 'price': price}]}
            r = requests.put(f'{self.url_api}/api/offers', headers=self._headers(),
                             json=payload, timeout=10)
            return r.status_code in (200, 204)
        except Exception:
            return False

    def _mock_offers(self) -> list[dict]:
        skus = [
            ('IP15-128-BLK', 899.99), ('IP15-256-BLK', 999.99), ('IP15P-128-NAT', 1099.99),
            ('IP15P-256-NAT', 1199.99), ('IP15PM-256-BLU', 1299.99),
            ('IP14-128-WHT', 699.99), ('IP14P-128-PRP', 899.99),
            ('IP13-128-GRN', 599.99), ('IPSE3-64-RED', 429.99), ('IPSE3-128-BLK', 479.99),
        ]
        return [
            {'offer_id': str(1000 + i), 'sku': sku, 'price': price, 'stock': random.randint(0, 20)}
            for i, (sku, price) in enumerate(skus)
        ]

    def _mock_buybox(self, offer_id: str) -> dict:
        has_bb = random.random() > 0.4
        base_price = 500 + random.random() * 800
        return {
            'has_buybox': has_bb,
            'buybox_price': round(base_price, 2),
            'competitors': random.randint(1, 8),
        }

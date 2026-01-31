from abc import ABC, abstractmethod
from typing import List


class MarketplaceClient(ABC):
    @abstractmethod
    def test_connection(self) -> bool:
        pass

    @abstractmethod
    def get_offers(self) -> List[dict]:
        """Return list of offers with keys: offer_id, sku, price, stock."""
        pass

    @abstractmethod
    def get_buybox_info(self, offer_id: str) -> dict:
        """Return dict with keys: has_buybox, buybox_price, competitors."""
        pass

    @abstractmethod
    def update_price(self, offer_id: str, price: float) -> bool:
        pass

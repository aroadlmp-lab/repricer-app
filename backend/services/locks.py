import threading

_locks = {}
_locks_guard = threading.Lock()


class MarketplaceBusyError(Exception):
    """Se lanza cuando ya hay un sync/repricer en curso para el mismo marketplace."""
    pass


def get_marketplace_lock(marketplace_id):
    """Lock no-reentrante por marketplace, compartido entre sync y repricer.

    Evita que dos llamadas a get_offers()/P11 para el mismo marketplace se
    ejecuten en paralelo (ej: un sync manual solapado con el repricer
    programado), lo que multiplica las peticiones a Mirakl y dispara 429s
    en marketplaces con rate limit ajustado (Carrefour).
    """
    with _locks_guard:
        lock = _locks.get(marketplace_id)
        if lock is None:
            lock = threading.Lock()
            _locks[marketplace_id] = lock
        return lock

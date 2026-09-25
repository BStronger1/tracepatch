"""Conservative reservations survive crashes and never silently refund unknown calls."""
import json
import os
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path


class BudgetLedger:
    def __init__(self, path: Path, limit: str = '10', historical_reserve: str = '1.2'):
        self.path = path
        self.limit = Decimal(limit)
        self.history = Decimal(historical_reserve)
        if not self.limit.is_finite() or not self.history.is_finite() or not 0 <= self.history <= self.limit:
            raise ValueError('Invalid budget')
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.locked():
            if not path.exists():
                self.write({'currency': 'CNY', 'limit': str(self.limit),
                            'historical_reserve': str(self.history), 'requests': []})
            elif Decimal(self.read()['limit']) != self.limit:
                raise ValueError('Existing ledger limit differs; explicit review required')

    @contextmanager
    def locked(self):
        lock = self.path.with_suffix('.lock')
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise RuntimeError('Ledger busy or stale lock; inspect before retrying') from None
        try:
            os.close(fd)
            yield
        finally:
            lock.unlink()

    def read(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def write(self, data):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        temporary.replace(self.path)

    def reserve(self, request_id: str, amount: str = '0.1'):
        amount = Decimal(amount)
        if not amount.is_finite() or amount <= 0:
            raise ValueError('Reservation must be positive and finite')
        with self.locked():
            data = self.read()
            if any(r['id'] == request_id for r in data['requests']):
                raise ValueError('Duplicate request ID; never retry an ambiguous request implicitly')
            used = Decimal(data['historical_reserve']) + sum(Decimal(r['reserved_cny']) for r in data['requests'])
            if used + amount > Decimal(data['limit']):
                raise RuntimeError('Budget reservation limit reached; no API call allowed')
            data['requests'].append({'id': request_id, 'reserved_cny': str(amount), 'status': 'started'})
            self.write(data)

    def record(self, request_id: str, record: dict):
        with self.locked():
            data = self.read()
            target = next(r for r in data['requests'] if r['id'] == request_id)
            for field in ('status', 'prompt_tokens', 'completion_tokens', 'estimated_no_cache_cny', 'error_type'):
                if field in record:
                    target[field] = record[field]
            self.write(data)

    def summary(self):
        with self.locked():
            data = self.read()
        reserved = Decimal(data['historical_reserve']) + sum(Decimal(r['reserved_cny']) for r in data['requests'])
        return {'limit_cny': str(self.limit), 'reserved_cny': str(reserved),
                'remaining_reservation_cny': str(self.limit - reserved),
                'note': 'Conservative planning reservations, not actual provider charges'}

    def increase_limit(self, new_limit: str, reason: str):
        """Explicit operator action; preserve every reservation and log the change."""
        value = Decimal(new_limit)
        if not value.is_finite() or not reason.strip():
            raise ValueError('Finite budget and change reason required')
        with self.locked():
            data = self.read()
            previous = Decimal(data['limit'])
            if value <= previous:
                raise ValueError('New limit must exceed existing limit')
            data.setdefault('limit_changes', []).append({'from': str(previous), 'to': str(value), 'reason': reason})
            data['limit'] = str(value)
            self.write(data)
            self.limit = value

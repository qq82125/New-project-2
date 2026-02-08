from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.services import subscriptions


@dataclass
class FakeInsert:
    values_data: dict

    def on_conflict_do_update(self, index_elements, set_):
        self.set_data = set_
        return self


class FakeInsertBuilder:
    def values(self, **kwargs):
        return FakeInsert(values_data=kwargs)


class FakeDB:
    def __init__(self, subs):
        self.subs = subs
        self.existing = {}

    def scalars(self, _stmt):
        return self.subs

    def scalar(self, _stmt):
        key = (self._current_date, self._current_subscriber, self._current_channel)
        return self.existing.get(key)

    def execute(self, stmt):
        key = (stmt.values_data['digest_date'], stmt.values_data['subscriber_key'], stmt.values_data['channel'])
        self.existing[key] = SimpleNamespace(status=stmt.values_data['status'])

    def commit(self):
        return None


def test_match_subscription_company_product_keyword():
    product = SimpleNamespace(
        id=uuid4(),
        name='Alpha Test Kit',
        udi_di='UDI-001',
        reg_no='REG-001',
        company=SimpleNamespace(name='Acme Med'),
    )

    s_company = SimpleNamespace(subscription_type='company', target_value='acme')
    s_product = SimpleNamespace(subscription_type='product', target_value='udi-001')
    s_keyword = SimpleNamespace(subscription_type='keyword', target_value='alpha')

    assert subscriptions._match_subscription(s_company, product)
    assert subscriptions._match_subscription(s_product, product)
    assert subscriptions._match_subscription(s_keyword, product)


def test_daily_digest_one_subscriber_one_day_one_push(monkeypatch):
    subscriber = SimpleNamespace(
        subscriber_key='u1',
        channel='webhook',
        email_to=None,
        subscription_type='keyword',
        target_value='alpha',
        webhook_url='https://example.com/hook',
        is_active=True,
    )
    db = FakeDB([subscriber])

    change = SimpleNamespace(change_type='update', change_date=datetime.now(timezone.utc), changed_fields={'name': {'old': 'A', 'new': 'B'}})
    product = SimpleNamespace(id=uuid4(), name='Alpha', udi_di='U1', reg_no='R1', company=SimpleNamespace(name='Acme'))

    monkeypatch.setattr(subscriptions, '_fetch_changes', lambda *_: [(change, product)])
    monkeypatch.setattr(subscriptions, '_send_webhook', lambda *_: True)
    monkeypatch.setattr(subscriptions, 'insert', lambda _model: FakeInsertBuilder())

    target_date = date(2026, 2, 8)
    db._current_date = target_date
    db._current_subscriber = 'u1'
    db._current_channel = 'webhook'

    r1 = subscriptions.dispatch_daily_subscription_digest(db, target_date)
    r2 = subscriptions.dispatch_daily_subscription_digest(db, target_date)

    assert r1['sent'] == 1
    assert r2['sent'] == 0
    assert r2['skipped'] >= 1


def test_daily_digest_email_channel(monkeypatch):
    subscriber = SimpleNamespace(
        subscriber_key='user@example.com',
        channel='email',
        email_to='user@example.com',
        subscription_type='keyword',
        target_value='alpha',
        webhook_url=None,
        is_active=True,
    )
    db = FakeDB([subscriber])

    change = SimpleNamespace(change_type='update', change_date=datetime.now(timezone.utc), changed_fields={})
    product = SimpleNamespace(id=uuid4(), name='Alpha', udi_di='U1', reg_no='R1', company=SimpleNamespace(name='Acme'))

    monkeypatch.setattr(subscriptions, '_fetch_changes', lambda *_: [(change, product)])
    monkeypatch.setattr(subscriptions, '_send_email', lambda *_: True)
    monkeypatch.setattr(subscriptions, 'insert', lambda _model: FakeInsertBuilder())

    target_date = date(2026, 2, 9)
    db._current_date = target_date
    db._current_subscriber = 'user@example.com'
    db._current_channel = 'email'

    result = subscriptions.dispatch_daily_subscription_digest(db, target_date)
    assert result['sent'] == 1

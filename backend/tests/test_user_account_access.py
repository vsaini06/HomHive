from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.auth.models import HouseholdMembershipRecord, UserRecord, UserSessionRecord
from app.auth.service import AccountService, HouseholdTokens, hash_password, verify_password


def test_user_registration_membership_and_revocation():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    accounts = AccountService(factory)
    session = accounts.register('demo@example.test', 'correct horse password')
    household = session['households'][0]
    assert household.startswith('home_')
    assert accounts.membership(session['access_token'], household)
    assert not accounts.membership(session['access_token'], 'home_' + '0' * 32)
    assert accounts.login('demo@example.test', 'correct horse password')['households'] == [household]
    accounts.logout(session['access_token'])
    assert not accounts.membership(session['access_token'], household)
    engine.dispose()


def test_password_hash_salted_and_not_reversible():
    first = hash_password('very strong password')
    second = hash_password('very strong password')
    assert first != second
    assert verify_password('very strong password', first)
    assert not verify_password('wrong password', first)


def test_household_credential_bridge_refuses_arbitrary_ids():
    tokens = HouseholdTokens({'existing': 'legacy-secret'}, 'a' * 40)
    assert tokens.get('existing') == 'legacy-secret'
    assert tokens.get('home_' + 'a' * 32)
    assert tokens.get('other_household') is None

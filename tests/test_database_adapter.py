import pytest
from database.adapter import DatabaseAdapter

@pytest.fixture
def db_adapter():
    return DatabaseAdapter()

def test_get_user_referral_points(db_adapter):
    # Assuming a test user ID that exists or mock if needed
    points = db_adapter.get_user_referral_points(12345)
    assert isinstance(points, int)
    assert points >= 0

def test_update_user_referral_points(db_adapter):
    success = db_adapter.update_user_referral_points(12345, 100)
    assert success is True
    points = db_adapter.get_user_referral_points(12345)
    assert points == 100

# Add more tests for other methods similarly
from db.database import get_session, PositionSimulated
from datetime import datetime

session = get_session()

# Mock a position: AAPL bought at a lower price
pos = PositionSimulated(
    ticker="AAPL",
    entry_date=datetime.now().strftime("%Y-%m-%d"),
    entry_price=150.0, # Hypothetical entry
    size=100.0 / 150.0,
    status="OPEN"
)

session.add(pos)
session.commit()
session.close()
print("Test position added for AAPL at 150.0")

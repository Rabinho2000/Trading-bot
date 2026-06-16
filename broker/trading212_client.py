import config

class Trading212Client:
    def __init__(self, api_key=None):
        self.api_key = api_key or config.T212_API_KEY
        self.dry_run = config.DRY_RUN
        
    def get_account_summary(self):
        """Placeholder for account summary"""
        return {"balance": 10000.0, "currency": "EUR"}

    def place_order(self, order):
        """
        Placeholder for placing an order.
        Strict safety checks.
        """
        if self.dry_run:
            print(f"[DRY_RUN] Order would be placed: {order}")
            return True, "DRY_RUN_SUCCESS"
            
        if not config.IF_LIVE_TRADING_ENABLED:
            return False, "LIVE_TRADING_DISABLED"
            
        print(f"Executing LIVE order: {order}")
        # Real API call would go here
        return True, "LIVE_ORDER_EXECUTED"

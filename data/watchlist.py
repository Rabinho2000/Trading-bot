import config

def get_watchlist():
    """Return the default watchlist from config"""
    return config.DEFAULT_WATCHLIST

def get_sector_rotation_watchlist():
    """Example of a sector rotation watchlist"""
    return [
        "XLF", "XLK", "XLV", "XLP", "XLY", "XLI", "XLC", "XLU", "XLE", "XLB", "XLRE"
    ]

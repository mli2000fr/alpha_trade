"""Compatibility CLI; canonical ingestion lives in service.market.intraday_backfill."""
from service.market.intraday_backfill import *  # noqa: F403

if __name__=='__main__':
    main()

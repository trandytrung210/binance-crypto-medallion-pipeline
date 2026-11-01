-- Prices and traded quote volume by UTC day.
SELECT symbol,bucket_time,open_price,high_price,low_price,close_price,
       quote_volume,vwap,taker_buy_share,is_complete
FROM gold.mart_daily ORDER BY symbol,bucket_time;

-- Only complete hourly buckets.
SELECT symbol,count(*) AS complete_hours,sum(quote_volume) AS quote_volume
FROM gold.mart_hourly WHERE is_complete GROUP BY symbol;

-- Reconcile trade counts between levels.
SELECT (SELECT sum(trade_count) FROM silver.fact_candles) AS silver_trades,
       (SELECT sum(trade_count) FROM gold.mart_daily) AS gold_trades;

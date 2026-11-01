from datetime import datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
import json,time,logging
import duckdb,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
from .storage import ROOT,Capture,verified_run,load,save,current,uid,stamp
KIND='binance_spot_klines'
NUMBERS=['open_price','high_price','low_price','close_price','base_volume','quote_volume','taker_buy_base','taker_buy_quote']
SCHEMA=pa.schema([('symbol',pa.string()),('open_time',pa.timestamp('ms',tz='UTC')),('close_time',pa.timestamp('ms',tz='UTC'))]+[(n,pa.decimal128(28,10)) for n in NUMBERS]+[('trade_count',pa.int64()),('source_run_id',pa.string()),('source_file',pa.string())])
def window(config):
 start=datetime.fromisoformat(config['start']).replace(tzinfo=timezone.utc)
 end=datetime.fromisoformat(config['end']).replace(tzinfo=timezone.utc)
 if start>=end or end>datetime.now(timezone.utc):raise ValueError('Require a completed historical date window')
 if config['interval']!='1m':raise ValueError('This implementation supports 1m candles only')
 return int(start.timestamp()*1000),int(end.timestamp()*1000)
def download(config,root=ROOT):
 start,end=window(config);capture=Capture(KIND,config,root)
 try:
  base=config['api_base'].rstrip('/')
  capture.fetch(base+'/api/v3/exchangeInfo',{'symbols':json.dumps(config['symbols'],separators=(',',':'))},'exchange_info.json',role='dimension')
  for symbol in config['symbols']:
   cursor=start;page=0
   while cursor<end:
    page+=1
    rows=capture.fetch(base+'/api/v3/klines',{'symbol':symbol,'interval':'1m','startTime':cursor,'endTime':end-1,'limit':1000},f'{symbol}_{page:04}.json',role='candles',symbol=symbol)
    if not isinstance(rows,list) or not rows:raise ValueError('Empty/malformed page for '+symbol)
    next_cursor=int(rows[-1][0])+60000
    if next_cursor<=cursor:raise ValueError('Pagination did not advance')
    logging.info('%s page %s: %s rows',symbol,page,len(rows));cursor=next_cursor
    time.sleep(config['request_pause_seconds'])
  return capture.finish()
 except Exception as e:capture.fail(e);raise

def parse_row(raw,symbol,run_id,source_file,start,end):
 if not isinstance(raw,list) or len(raw)!=12:raise ValueError('expected_12_fields')
 opened=int(raw[0]);closed=int(raw[6])
 if opened<start or opened>=end or opened%60000:raise ValueError('outside_window_or_misaligned')
 if closed!=opened+59999:raise ValueError('invalid_close_time')
 values=[Decimal(str(raw[i])) for i in [1,2,3,4,5,7,9,10]]
 if any(not x.is_finite() for x in values):raise ValueError('non_finite_numeric')
 if any(x<0 for x in values) or any(x<=0 for x in values[:4]):raise ValueError('invalid_price_or_volume')
 o,h,l,c,b,q,tb,tq=values
 if l>min(o,c) or h<max(o,c) or l>h:raise ValueError('invalid_ohlc')
 if tb>b or tq>q:raise ValueError('taker_volume_exceeds_total')
 if int(raw[8])<0 or Decimal(str(raw[8]))!=int(raw[8]):raise ValueError('invalid_trade_count')
 if any(x!=x.quantize(Decimal('0.0000000001')) for x in values):raise ValueError('decimal_scale_exceeds_10')
 return dict(symbol=symbol,open_time=datetime.fromtimestamp(opened/1000,timezone.utc),close_time=datetime.fromtimestamp(closed/1000,timezone.utc),**dict(zip(NUMBERS,values)),trade_count=int(raw[8]),source_run_id=run_id,source_file=source_file)

def build(run_id,root=ROOT,fail_before_publish=False):
 folder,m=verified_run(run_id,KIND,root);config=m['config'];start,end=window(config)
 publication=uid();report=root/'reports'/publication;report.mkdir(parents=True)
 good=[];bad=[];seen={};duplicates=0;input_rows=0
 for entry in m['responses']:
  if entry['role']!='candles':continue
  for number,raw in enumerate(load(folder/entry['file'])):
   input_rows+=1
   try:
    row=parse_row(raw,entry['symbol'],run_id,entry['file'],start,end);key=(row['symbol'],row['open_time'])
    if key in seen:
     if row!=seen[key]:
      # Same logical record may occur on a different source page.
      logical=lambda r:{k:v for k,v in r.items() if k!='source_file'}
      if logical(row)!=logical(seen[key]):raise ValueError('conflicting_duplicate')
     duplicates+=1;continue
    seen[key]=row;good.append(row)
   except (ValueError,InvalidOperation,TypeError,OverflowError) as e:bad.append(dict(file=entry['file'],index=number,reason=str(e),raw=raw))
 save(report/'quarantine.json',bad)
 expected=(end-start)//60000*len(config['symbols'])
 quality=dict(input_rows=input_rows,valid_rows=len(good),quarantined=len(bad),duplicate_rows=duplicates,expected_rows=expected)
 save(report/'quality.json',quality)
 if bad or len(good)!=expected:raise ValueError('Data quality gate failed; inspect '+str(report))
 batch=pa.Table.from_pylist(good,schema=SCHEMA)
 silver=root/'data/silver'/publication;gold=root/'data/gold'/publication
 silver.mkdir(parents=True);gold.mkdir(parents=True)
 db=duckdb.connect(str(gold/'warehouse.duckdb'));db.execute("SET TimeZone='UTC'")
 try:
  db.register('incoming',batch)
  previous=current(root)
  if previous:
   db.register('previous',pq.read_table(root/previous['silver']))
   db.execute('CREATE TABLE merged AS SELECT * EXCLUDE(rank) FROM (SELECT *,row_number() OVER(PARTITION BY symbol,open_time ORDER BY priority DESC) rank FROM (SELECT *,0 priority FROM previous UNION ALL SELECT *,1 priority FROM incoming)) WHERE rank=1')
   # Strip the merge priority helper before publishing.
   db.execute('ALTER TABLE merged DROP priority')
  else:db.execute('CREATE TABLE merged AS SELECT * FROM incoming')
  db.execute('CREATE SCHEMA silver');db.execute('CREATE SCHEMA gold')
  db.execute('CREATE TABLE silver.fact_candles AS SELECT * FROM merged ORDER BY symbol,open_time')
  db.execute('ALTER TABLE silver.fact_candles ADD PRIMARY KEY(symbol,open_time)')
  symbols=load(folder/'exchange_info.json')['symbols']
  dimensions=pa.Table.from_pylist([dict(symbol=s['symbol'],base_asset=s['baseAsset'],quote_asset=s['quoteAsset']) for s in symbols])
  db.register('symbol_source',dimensions);db.execute('CREATE TABLE gold.dim_symbol AS SELECT * FROM symbol_source')
  orphan=db.execute('SELECT count(*) FROM silver.fact_candles f LEFT JOIN gold.dim_symbol d USING(symbol) WHERE d.symbol IS NULL').fetchone()[0]
  if orphan:raise ValueError('Orphan symbols')
  db.execute("CREATE TABLE gold.dim_date AS SELECT DISTINCT cast(open_time AS DATE) date_key,year(open_time) AS calendar_year,month(open_time) AS calendar_month,day(open_time) AS calendar_day FROM silver.fact_candles")
  for name,bucket,expected_minutes in [('hourly','hour',60),('daily','day',1440)]:
   db.execute(f"""CREATE TABLE gold.mart_{name} AS
    SELECT symbol,date_trunc('{bucket}',open_time) bucket_time,
    arg_min(open_price,open_time) open_price,max(high_price) high_price,min(low_price) low_price,arg_max(close_price,open_time) close_price,
    sum(base_volume) base_volume,sum(quote_volume) quote_volume,sum(trade_count) trade_count,
    sum(taker_buy_base) taker_buy_base,sum(taker_buy_quote) taker_buy_quote,
    sum(quote_volume)::DOUBLE/nullif(sum(base_volume)::DOUBLE,0) vwap,
    sum(taker_buy_quote)::DOUBLE/nullif(sum(quote_volume)::DOUBLE,0) taker_buy_share,
    count(*) minute_count,count(*)={expected_minutes} is_complete
    FROM silver.fact_candles GROUP BY 1,2 ORDER BY 1,2""")
  # Exact DECIMAL sums must reconcile after aggregation, including partial buckets.
  totals=db.execute('SELECT sum(base_volume),sum(quote_volume),sum(trade_count) FROM silver.fact_candles').fetchone()
  for name in ['hourly','daily']:
   if db.execute(f'SELECT sum(base_volume),sum(quote_volume),sum(trade_count) FROM gold.mart_{name}').fetchone()!=totals:raise ValueError('Volume/trade reconciliation failed')
  db.sql('SELECT * FROM silver.fact_candles').write_parquet(str(silver/'candles.parquet'),compression='zstd')
  for table in ['dim_symbol','dim_date','mart_hourly','mart_daily']:
   db.sql('SELECT * FROM gold.'+table).write_parquet(str(gold/(table+'.parquet')),compression='zstd')
   db.sql('SELECT * FROM gold.'+table).df().to_csv(gold/(table+'.csv'),index=False)
  rows=db.execute('SELECT count(*) FROM silver.fact_candles').fetchone()[0]
  hourly=db.execute('SELECT count(*) FROM gold.mart_hourly').fetchone()[0]
  daily=db.execute('SELECT count(*) FROM gold.mart_daily').fetchone()[0]
  watermarks={symbol:str(ts) for symbol,ts in db.execute("SELECT symbol,max(open_time)+interval '1 minute' FROM silver.fact_candles GROUP BY symbol").fetchall()}
 finally:db.close()
 result=dict(publication_id=publication,source_run_id=run_id,published_at=stamp(),silver=str((silver/'candles.parquet').relative_to(root)),warehouse=str((gold/'warehouse.duckdb').relative_to(root)),gold=str(gold.relative_to(root)),report=str(report.relative_to(root)),silver_rows=rows,hourly_rows=hourly,daily_rows=daily,watermarks=watermarks,quality=quality)
 save(report/'publication.json',result)
 if fail_before_publish:raise RuntimeError('Injected failure before publication; previous pointer preserved')
 save(root/'data/current.json',result)
 logging.info('Published %s: %s silver, %s hourly, %s daily',publication,rows,hourly,daily)
 return result

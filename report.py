import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.storage import ROOT,current,read_current_sql,save
c=current();df=read_current_sql('SELECT * FROM gold.mart_hourly ORDER BY bucket_time');daily=read_current_sql('SELECT * FROM gold.mart_daily ORDER BY bucket_time')
fig,axes=plt.subplots(2,1,figsize=(12,7),layout='constrained')
for symbol,part in df.groupby('symbol'):
 prices=part.close_price.astype(float);axes[0].plot(part.bucket_time,prices/prices.iloc[0]*100,label=symbol)
for symbol,part in daily.groupby('symbol'):
 axes[1].plot(part.bucket_time,part.quote_volume.astype(float)/1e6,marker='o',label=symbol)
axes[0].set(title='Binance spot prices · first hourly close = 100',ylabel='Indexed close');axes[1].set(title='Daily traded quote volume',ylabel='Million USDT',xlabel='UTC date')
for ax in axes:ax.legend();ax.grid(alpha=.2)
fig.savefig(ROOT/'reports/overview.png',dpi=160);plt.close(fig)
summary=read_current_sql('SELECT symbol,sum(quote_volume)::DOUBLE quote_volume_usdt,sum(trade_count) trade_count,count(*) AS day_count FROM gold.mart_daily GROUP BY symbol').to_dict('records')
save(ROOT/'reports/summary.json',dict(publication_id=c['publication_id'],metrics=summary))
print('Created reports/overview.png and reports/summary.json')

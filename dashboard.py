import streamlit as st
from src.storage import current,read_current_sql
st.set_page_config(page_title='Binance market analytics',layout='wide')
st.title('Binance historical market analytics')
c=current()
if not c:st.info('Run python run.py run first.');st.stop()
st.caption('Validated publication: '+c['publication_id']+' | Historical 1-minute candles; no live stream')
a,b,d=st.columns(3);a.metric('Silver candles',c['silver_rows']);b.metric('Hourly groups',c['hourly_rows']);d.metric('Quarantined',c['quality']['quarantined'])
symbol=st.selectbox('Symbol',read_current_sql('SELECT symbol FROM gold.dim_symbol ORDER BY symbol').symbol.tolist())
df=read_current_sql('SELECT * FROM gold.mart_hourly');df=df[df.symbol==symbol]
st.line_chart(df,x='bucket_time',y=['close_price','vwap'])
st.bar_chart(df,x='bucket_time',y='quote_volume')
st.dataframe(read_current_sql('SELECT * FROM gold.mart_daily'),hide_index=True)
st.download_button('Download daily CSV',read_current_sql('SELECT * FROM gold.mart_daily').to_csv(index=False),'market_daily.csv','text/csv')

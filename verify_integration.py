"""Offline integration checks using an already downloaded real Bronze run."""
import hashlib,json,subprocess,sys
from pathlib import Path
import duckdb
from src.storage import ROOT,load,save,digest

def fingerprint(state):
    tables=[]
    with duckdb.connect(str(ROOT/state['warehouse']),read_only=True) as db:
        names=db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='gold' ORDER BY table_name").fetchall()
        for (name,) in names:
            rows=db.execute('SELECT * FROM gold.'+name+' ORDER BY ALL').fetchall()
            rows=[[round(v,9) if isinstance(v,float) else str(v) for v in row] for row in rows]
            tables.append((name,rows))
    return hashlib.sha256(json.dumps(tables).encode()).hexdigest()

def main():
    state=load(ROOT/'data/current.json');source_id=state['source_run_id']
    bronze=ROOT/'data/bronze'/source_id;manifest=load(bronze/'manifest.json')
    before={x['file']:digest(bronze/x['file']) for x in manifest['responses']}
    pointer_before=(ROOT/'data/current.json').read_bytes();gold_before=fingerprint(state)
    cmd=[sys.executable,'run.py','build','--run-id',source_id]
    failed=subprocess.run(cmd+['--fail-before-publish'],cwd=ROOT,capture_output=True,text=True)
    assert failed.returncode!=0 and 'Injected failure' in failed.stderr,failed.stdout+failed.stderr
    assert (ROOT/'data/current.json').read_bytes()==pointer_before,'Failure advanced publication pointer'
    replay=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    assert replay.returncode==0,replay.stdout+replay.stderr
    after=load(ROOT/'data/current.json')
    assert after['silver_rows']==state['silver_rows'],'Replay added duplicate keys'
    assert fingerprint(after)==gold_before,'Replay changed Gold business values'
    assert {x['file']:digest(bronze/x['file']) for x in manifest['responses']}==before,'Raw bytes changed'
    unit=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True)
    assert unit.returncode==0,unit.stderr
    extra={}
    if 'analysis_start' in state:
        # Independent Python calculation across Jan/Feb local month boundary, on the shipped window.
        import pyarrow.parquet as pq
        from datetime import datetime,timedelta,timezone
        target=datetime(2025,1,31,17,tzinfo=timezone.utc)
        facts=pq.read_table(ROOT/after['silver']).to_pylist()
        with duckdb.connect(str(ROOT/after['warehouse']),read_only=True) as db:
            checks=0
            for city in manifest['config']['cities']:
                values=[r['precipitation_mm'] for r in facts if r['city_id']==city['city_id'] and target-timedelta(hours=24)<r['event_time']<=target]
                if len(values)==24:
                    value=db.execute('SELECT precipitation_24h_mm FROM gold.fact_hourly WHERE city_id=? AND event_time=?',[city['city_id'],target]).fetchone()[0]
                    assert abs(sum(values)-value)<1e-8,'Month-boundary rainfall mismatch'
                    checks+=1
            extra['month_boundary_cities_checked']=checks
            assert checks==3,'This shipped-window verification expects the default three-city dataset'
    result=dict(source_run_id=source_id,publication_id=after['publication_id'],silver_rows=after['silver_rows'],daily_rows=after['daily_rows'],hourly_rows=after.get('hourly_rows'),bronze_files_verified=len(before),checks={'failure_keeps_current_pointer':True,'offline_replay_preserves_row_count':True,'offline_replay_preserves_gold_values_rounded_9dp':True,'bronze_hashes_unchanged':True,'unit_tests_passed':True},extra=extra)
    save(ROOT/'evidence/verification.json',result)
    (ROOT/'evidence/unit_tests.txt').write_text(unit.stderr)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

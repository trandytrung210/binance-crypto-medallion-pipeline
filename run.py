import argparse,json
from src import pipeline
from src.storage import current,lock,ROOT

def main():
 p=argparse.ArgumentParser(description='Download real source data and build a validated medallion publication')
 p.add_argument('command',choices=['run','download','build','status'])
 p.add_argument('--start',help='Inclusive date YYYY-MM-DD')
 p.add_argument('--end',help='Exclusive date YYYY-MM-DD')
 p.add_argument('--run-id',help='Existing Bronze run for an offline build/replay')
 p.add_argument('--fail-before-publish',action='store_true',help='Exercise failure recovery without changing current.json')
 a=p.parse_args()
 if a.command=='status':print(json.dumps(current(),indent=2));return
 with lock():
  if a.command in ('run','download'):
   config=json.loads((ROOT/'config.json').read_text())
   if a.start:config['start']=a.start
   if a.end:config['end']=a.end
   run_id=pipeline.download(config)
   print('BRONZE_RUN_ID='+run_id,flush=True)
  else:
   if not a.run_id:p.error('build requires --run-id')
   run_id=a.run_id
  if a.command!='download':
   result=pipeline.build(run_id,fail_before_publish=a.fail_before_publish)
   print(json.dumps(result,indent=2))
if __name__=='__main__':main()

import contextlib,fcntl,hashlib,json,logging,os,uuid
from pathlib import Path
from datetime import datetime,timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
ROOT=Path(__file__).resolve().parents[1]
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
def uid():return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
def stamp():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 with tmp.open('w',encoding='utf-8') as f:
  json.dump(value,f,ensure_ascii=False,indent=2,default=str,allow_nan=False);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def load(path):return json.loads(Path(path).read_text())
def current(root=ROOT):
 p=root/'data/current.json';return load(p) if p.exists() else None
@contextlib.contextmanager
def lock(root=ROOT):
 root.mkdir(parents=True,exist_ok=True)
 with (root/'.pipeline.lock').open('a') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError('Another writer is running')
  try:yield
  finally:fcntl.flock(f,fcntl.LOCK_UN)
class Capture:
 def __init__(self,kind,config,root=ROOT):
  self.root=root;self.id=uid();self.folder=root/'data/bronze'/self.id
  self.folder.mkdir(parents=True);self.path=self.folder/'manifest.json'
  self.manifest=dict(run_id=self.id,kind=kind,created_at=stamp(),config=config,status='extracting',responses=[])
  save(self.path,self.manifest)
  self.session=requests.Session()
  retry=Retry(total=4,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=['GET'],respect_retry_after_header=True)
  self.session.mount('https://',HTTPAdapter(max_retries=retry))
 def fetch(self,url,params,name,**tags):
  response=self.session.get(url,params=params,timeout=(10,90))
  p=self.folder/name
  with p.open('xb') as f:f.write(response.content)
  record=dict(file=name,url=response.url,status_code=response.status_code,retrieved_at=stamp(),sha256=digest(p),bytes=p.stat().st_size,**tags)
  self.manifest['responses'].append(record);save(self.path,self.manifest)
  response.raise_for_status();return response.json()
 def finish(self):
  self.manifest.update(status='extracted',extract_finished_at=stamp());save(self.path,self.manifest);self.session.close();return self.id
 def fail(self,error):
  self.manifest.update(status='extraction_failed',error=str(error));save(self.path,self.manifest);self.session.close()
def verified_run(run_id,kind,root=ROOT):
 if Path(run_id).name!=run_id:raise ValueError('Invalid run identifier')
 folder=root/'data/bronze'/run_id;m=load(folder/'manifest.json')
 if m['kind']!=kind or m['status']!='extracted':raise ValueError('Run is not an extracted '+kind+' run')
 for entry in m['responses']:
  if digest(folder/entry['file'])!=entry['sha256']:raise ValueError('Bronze checksum mismatch: '+entry['file'])
 return folder,m

def read_current_sql(sql,root=ROOT):
 import duckdb
 c=current(root)
 if not c:raise RuntimeError('No validated publication yet')
 with duckdb.connect(str(root/c['warehouse']),read_only=True) as db:return db.execute(sql).fetch_df()

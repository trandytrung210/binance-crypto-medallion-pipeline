import unittest,tempfile,json,hashlib
from pathlib import Path
from src.pipeline import parse_row
from src.storage import verified_run,save
class QualityRules(unittest.TestCase):
 def setUp(self):self.row=[1735689600000,'100','110','90','105','10',1735689659999,'1010',20,'4','404','0']
 def parse(self,row):return parse_row(row,'BTCUSDT','test_run','page.json',1735689600000,1735689660000)
 def test_valid(self):self.assertEqual(str(self.parse(self.row)['base_volume']),'10')
 def test_invalid_high(self):
  r=self.row.copy();r[2]='80'
  with self.assertRaisesRegex(ValueError,'ohlc'):self.parse(r)
 def test_taker_volume(self):
  r=self.row.copy();r[9]='11'
  with self.assertRaisesRegex(ValueError,'taker'):self.parse(r)
 def test_timestamp_boundary(self):
  r=self.row.copy();r[0]=1735689660000
  with self.assertRaisesRegex(ValueError,'outside'):self.parse(r)
 def test_checksum_tampering(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);folder=root/'data/bronze/run1';folder.mkdir(parents=True)
   p=folder/'raw.json';p.write_text('[]');checksum=hashlib.sha256(p.read_bytes()).hexdigest()
   save(folder/'manifest.json',dict(kind='test',status='extracted',responses=[dict(file='raw.json',sha256=checksum)]))
   p.write_text('[1]')
   with self.assertRaisesRegex(ValueError,'checksum'):verified_run('run1','test',root)
if __name__=='__main__':unittest.main()

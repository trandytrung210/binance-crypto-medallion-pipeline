import unittest
from streamlit.testing.v1 import AppTest
from src.storage import ROOT,current

@unittest.skipUnless(current(), 'Requires a validated local publication')
class DashboardSmoke(unittest.TestCase):
    def test_open_and_change_selection(self):
        app=AppTest.from_file(str(ROOT/'dashboard.py')).run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        options=app.selectbox[0].options
        if len(options)>1:
            app.selectbox[0].set_value(options[1]).run(timeout=30)
            self.assertEqual(len(app.exception),0,str(app.exception))
if __name__=='__main__':unittest.main()

"""v2 state regressions; use only a temporary save file."""
import concurrent.futures
import copy
import json
from pathlib import Path
import tempfile
import unittest
import pokemon_team as app

class FeaturesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path, self.old_state = app.STATE_FILE, app.STATE
        app.STATE_FILE = Path(self.temp.name) / 'team.json'
        app.STATE = app.validate_state({'slots':[None]*6, 'layout':'vertical'})
        self.mon = {'dex':1, 'form':'', 'name':'Bulbasaur', 'shiny':True, 'nickname':'Sprout', 'level':25}

    def tearDown(self):
        app.STATE_FILE, app.STATE = self.old_path, self.old_state
        self.temp.cleanup()

    def test_saved_team_is_independent_and_survives_restart(self):
        app.patch_state({'slot':0, 'value':self.mon})
        app.patch_state({'style':{'size':120, 'hideEmpty':True, 'labels':True}})
        app.patch_state({'saveTeam':'Run A'})
        app.patch_state({'swap':[0,5]})
        self.assertEqual(app.STATE['slots'][5]['nickname'], 'Sprout')
        self.assertIsNotNone(app.STATE['presets']['Run A']['slots'][0])
        app.load_state()
        app.patch_state({'loadTeam':'Run A'})
        self.assertIsNotNone(app.STATE['slots'][0])
        self.assertIsNone(app.STATE['slots'][5])
        self.assertEqual(app.STATE['style']['size'],120)
        app.patch_state({'deleteTeam':'Run A'})
        self.assertFalse(app.STATE['presets'])
        self.assertIsNotNone(app.STATE['slots'][0])

    def test_nuzlocke_history_and_edit(self):
        app.patch_state({'slot':0,'value':self.mon})
        app.patch_state({'challenge':{'enabled':True,'badges':3}})
        app.patch_state({'fainted':{'slot':0,'value':True}})
        app.patch_state({'fainted':{'slot':0,'value':True}})
        self.assertEqual(app.STATE['challenge']['deaths'],1)
        app.patch_state({'slot':0,'value':dict(self.mon, nickname='Leaf')})
        self.assertTrue(app.STATE['slots'][0]['fainted'])
        app.patch_state({'fainted':{'slot':0,'value':False}})
        self.assertEqual(app.STATE['challenge']['deaths'],1)

    def test_hunt_increments_are_atomic(self):
        app.patch_state({'huntTarget':self.mon})
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _:app.patch_state({'huntDelta':1}),range(25)))
        self.assertEqual(app.STATE['hunt']['count'],25)
        app.patch_state({'huntOptions':{'hotkey':'Space'}})
        app.patch_state({'huntReset':True})
        app.patch_state({'huntDelta':-1})
        self.assertEqual(app.STATE['hunt']['count'],0)

    def test_backup_round_trip_and_invalid_import_is_atomic(self):
        app.patch_state({'slot':0,'value':self.mon})
        app.patch_state({'saveTeam':'A'})
        app.patch_state({'huntTarget':self.mon})
        app.patch_state({'huntDelta':1})
        saved=copy.deepcopy(app.STATE)
        app.patch_state({'slot':0,'value':None})
        app.patch_state({'importData':{'format':'pokemon-team-backup','version':2,'state':saved}})
        self.assertEqual(app.STATE,saved)
        before=app.STATE_FILE.read_bytes()
        bad=copy.deepcopy(saved);bad['slots'][0]['dex']=-1
        with self.assertRaises(ValueError):
            app.patch_state({'importData':{'format':'pokemon-team-backup','version':2,'state':bad}})
        self.assertEqual(app.STATE_FILE.read_bytes(),before)
        app.patch_state({'importData':{'format':'pokemon-team','version':2,'team':saved}})
        self.assertIn('A',app.STATE['presets'])

    def test_old_saves_and_rejected_styles(self):
        old={'slots':[dict(dex=1,form='',name='Bulbasaur')]+[None]*5,'layout':'grid'}
        app.STATE_FILE.write_text(json.dumps(old));app.load_state()
        self.assertFalse(app.STATE['slots'][0]['shiny'])
        self.assertEqual(app.STATE['slots'][0]['nickname'],'')
        self.assertEqual(app.STATE['style'],app.DEFAULT_STYLE)
        for bad in [{'frame':'url(evil)'},{'size':1000},{'gap':-2},{'labels':'yes'}]:
            with self.assertRaises(ValueError):app.patch_state({'style':bad})

if __name__ == '__main__':unittest.main()

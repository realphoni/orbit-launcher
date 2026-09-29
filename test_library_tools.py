import unittest
from library_tools import merge_backup, personal_settings

class BackupTests(unittest.TestCase):
    def test_merge_preserves_launch_paths_and_unrelated_settings(self):
        current={'custom':[{'path':'existing.exe'}],'played':{'steam:1':123},'favorites':['steam:1']}
        incoming={'format':'orbit-personal-library','version':1,'settings':{'favorites':['steam:2'],'custom':[{'path':'bad.exe'}],'profiles':{'steam:2':{'rating':4}},'coverSize':'large'}}
        result=merge_backup(current,incoming)
        self.assertEqual(result['custom'],current['custom'])
        self.assertEqual(result['played'],current['played'])
        self.assertEqual(result['favorites'],['steam:1','steam:2'])
        self.assertNotIn('custom',personal_settings(result))
        self.assertEqual(current['favorites'],['steam:1'])
    def test_rejects_invalid_backup_without_modifying_original(self):
        current={'favorites':['steam:1']}
        for bad in [None,{}, {'format':'orbit-personal-library','version':1,'settings':{'hidden':'oops'}}, {'format':'orbit-personal-library','version':1,'settings':{'profiles':{'steam:1':{'rating':99}}}}]:
            with self.assertRaises(ValueError):merge_backup(current,bad)
        self.assertEqual(current,{'favorites':['steam:1']})

if __name__=='__main__':unittest.main()

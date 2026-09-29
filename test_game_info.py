import unittest
from unittest.mock import patch, MagicMock
import json
from game_info import validate_profile, fetch_reviews

class GameInfoTests(unittest.TestCase):
    def test_profile_validation_and_collection_deduplication(self):
        p=validate_profile(dict(rating=5,status='Completed',notes='A good game',collections=[' Co-op ','co-op','Weekend']))
        self.assertEqual(p['collections'], ['Co-op','Weekend'])
        for value in [-1,6,True,'5']:
            with self.assertRaises(ValueError):validate_profile({'rating':value})
        with self.assertRaises(ValueError):validate_profile({'notes':'x'*5001})

    def test_reviews_are_aggregated_without_inventing_scores(self):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps(dict(success=1,query_summary=dict(total_positive=80,total_negative=20,review_score_desc='Positive'))).encode()
        with patch('game_info.urlopen',return_value=response):
            self.assertEqual(fetch_reviews('620')['percent'],80)
        response.__enter__.return_value.read.return_value=json.dumps(dict(success=1,query_summary=dict(total_positive=0,total_negative=0))).encode()
        with patch('game_info.urlopen',return_value=response):self.assertIsNone(fetch_reviews('620')['percent'])
        with self.assertRaises(ValueError):fetch_reviews('../bad')

if __name__=='__main__':unittest.main()

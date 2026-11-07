import unittest
from dl_outcomes.review_leaderboard import leaderboard

class LeaderboardTests(unittest.TestCase):
    def test_published_work_is_credited_to_the_reviewer_including_imported_backups(self):
        schools={'a':{'state_code':'CA'},'b':{'state_code':'TX'}}
        records=[dict(review_id='one',reviewer='Brian',school_id='a',batch_id='batch1',github_actor='bjgaines11',changes={'delivery_structure':{}}),
                 dict(review_id='two',reviewer=' Brian ',school_id='b',batch_id='batch2',github_actor='bklawrence',changes={},notes='Useful source'),
                 dict(review_id='blank',reviewer='Other',school_id='a',batch_id='batch3',changes={})]
        result=leaderboard(records+[records[0]],schools)
        self.assertEqual(len(result),1);self.assertEqual(result[0]['reviewer'],'Brian')
        self.assertEqual(result[0]['reviews'],2);self.assertEqual(result[0]['schools'],2)
        self.assertEqual(result[0]['submissions'],2);self.assertEqual(result[0]['evidence_only'],1)

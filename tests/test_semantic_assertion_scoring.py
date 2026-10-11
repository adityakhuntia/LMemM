import unittest
from semantic_memory.evaluation import score_assertions

class AssertionScoringTests(unittest.TestCase):
    def row(self,assertions):
        return {'gold':[{'kind':'decision','statement':'We chose SQLite.','reason':None}],
                'evidence':{'e1':'We chose SQLite.'},'assertions':assertions}
    def claim(self,**changes):
        value={'kind':'decision','statement':'We chose SQLite.','reason':None,'citations':['e1'],'status':'supported'}
        value.update(changes);return value
    def test_fabricated_proposition_of_correct_type_is_false_positive(self):
        m=score_assertions([self.row([self.claim(statement='We chose Redis.')])])
        self.assertEqual((m['true_positive'],m['false_positive'],m['false_negative']),(0,1,1))
        self.assertEqual(m['unsupported_assertions'],1)
    def test_invented_reason_fails_even_with_correct_statement(self):
        m=score_assertions([self.row([self.claim(reason='because it is faster')])])
        self.assertEqual(m['claim_precision'],0)
        self.assertEqual(m['invalid_grounding'],1)
    def test_wrong_citation_fails_even_with_correct_quote(self):
        m=score_assertions([self.row([self.claim(citations=['missing'])])])
        self.assertEqual(m['invalid_citations'],1)
        self.assertEqual(m['true_positive'],0)
    def test_tentative_claim_is_not_counted_as_supported_assertion(self):
        m=score_assertions([self.row([self.claim(status='inferred')])])
        self.assertEqual((m['true_positive'],m['false_positive'],m['false_negative']),(0,0,1))
        self.assertEqual(m['unsupported_assertions'],0)
    def test_duplicate_claims_do_not_inflate_recall(self):
        m=score_assertions([self.row([self.claim(),self.claim()])])
        self.assertEqual((m['true_positive'],m['false_positive']),(1,1))
    def test_missing_reason_is_a_miss_when_reason_was_recorded(self):
        row=self.row([self.claim()]);row['gold'][0]['reason']='it stays local'
        row['gold'][0]['statement']='We chose SQLite because it stays local.'
        row['evidence']['e1']=row['gold'][0]['statement']
        row['assertions'][0]['statement']=row['gold'][0]['statement']
        m=score_assertions([row]);self.assertEqual(m['false_negative'],1)

    def test_every_claimed_citation_must_ground_the_assertion(self):
        row=self.row([self.claim(citations=['e1','unrelated'])]);row['evidence']['unrelated']='Weather forecast.'
        m=score_assertions([row]);self.assertEqual(m['true_positive'],0)
        self.assertEqual(m['invalid_grounding'],1)

from herd.sec_8k_hard_adverse_event_corpus_v2 import build
def test_v2_merges_only_exact_event_identity_promotions():
 rows,report=build()
 assert len(rows)==947
 assert report['newly_mapped_events']==115
 assert report['mapped_events']==300
 assert report['price_outcomes_opened'] is False
 assert report['operational_action_ratio']==0.0

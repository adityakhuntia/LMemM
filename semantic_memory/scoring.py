"""Exact labelled assertion scoring, independent of model and support promotion."""

def _normalized(value):
    return ' '.join((value or '').split()).casefold()

def _key(claim):
    return (claim['kind'],_normalized(claim['statement']),_normalized(claim.get('reason')),
            claim.get('task_state'))

def score_assertions(rows):
    tp=fp=fn=unsupported=invalid_citations=invalid_grounding=0
    for row in rows:
        unmatched=list(row['gold'])
        for claim in row['assertions']:
            if claim['status'] not in {'supported','user_asserted'}:continue
            refs=claim.get('citations',[])
            valid_refs=bool(refs) and all(ref in row['evidence'] for ref in refs)
            if not valid_refs:invalid_citations+=1
            texts=[_normalized(row['evidence'][ref]) for ref in refs if ref in row['evidence']]
            quote=_normalized(claim['statement']);reason=_normalized(claim.get('reason'))
            grounded=bool(quote) and any(quote in text and (not reason or reason in text) for text in texts)
            if not grounded:invalid_grounding+=1
            match=next((i for i,gold in enumerate(unmatched) if _key(gold)==_key(claim)),None)
            if valid_refs and grounded and match is not None:
                tp+=1;unmatched.pop(match)
            else:
                fp+=1
                if claim['kind']=='decision' or claim.get('task_state')=='completed':unsupported+=1
        fn+=len(unmatched)
    return {'claim_precision':tp/(tp+fp) if tp+fp else 0,
            'claim_recall':tp/(tp+fn) if tp+fn else 0,'true_positive':tp,
            'false_positive':fp,'false_negative':fn,'unsupported_assertions':unsupported,
            'invalid_citations':invalid_citations,'invalid_grounding':invalid_grounding}

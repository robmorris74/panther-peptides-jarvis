from app.policy import storefront_copy_check, RESEARCH_DISCLAIMER

def test_blocks_human_claim():
    r=storefront_copy_check('This product helps with weight loss. '+RESEARCH_DISCLAIMER)
    assert not r['approved']

def test_requires_disclaimer():
    assert not storefront_copy_check('Used as a reference material in receptor-binding research.')['approved']

def test_allows_research_copy():
    assert storefront_copy_check('Reference material for controlled laboratory assay development. '+RESEARCH_DISCLAIMER)['approved']

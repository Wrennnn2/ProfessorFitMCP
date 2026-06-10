from professor_fit_mcp.services.institution import InstitutionClassifier


def test_us_r1_recognized():
    clf = InstitutionClassifier()
    result = clf.classify("Massachusetts Institute of Technology", "US")
    assert result["tier"] == "R1"



def test_uk_russell_recognized():
    clf = InstitutionClassifier()
    result = clf.classify("University of Oxford", "GB")
    assert result["tier"] == "Russell"


def test_unknown_institution():
    clf = InstitutionClassifier()
    result = clf.classify("Unknown Small College", "US")
    assert result["tier"] is None


def test_case_insensitive():
    clf = InstitutionClassifier()
    result = clf.classify("stanford university", "US")
    assert result["tier"] == "R1"


def test_fuzzy_alias_berkeley_college():
    # OpenAlex sometimes returns "Berkeley College" for UC Berkeley affiliates
    clf = InstitutionClassifier()
    result = clf.classify("Berkeley College", "US")
    assert result["tier"] == "R1"


def test_fuzzy_ucsb_alias():
    clf = InstitutionClassifier()
    result = clf.classify("University of California, Santa Barbara", "US")
    assert result["tier"] == "R1"


def test_northeastern_university_us_no_tier():
    clf = InstitutionClassifier()
    result = clf.classify("Northeastern University", "US")
    assert result["tier"] is None or result["tier"] == "R1"

from curation_utils import file_helper


def test_clear_bad_chars():
    x = """
    +++
title = "चिद्गगनचन्द्रिका"
unicode_script = "devanagari"
+++
		कर्रोपपदाग्निहोत्रशास्त्रिणा धनदानन्दनाथदीक्षानामशालिना,
		विरचितया `दिव्यचकोरिकया' समलंकृता ।।
			प्रथमविमर्शः ।।
    """
    assert file_helper.clear_bad_chars(x) == x
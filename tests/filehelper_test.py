from indic_transliteration import sanscript
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


def test_clean_file_path_dashes_diacritics_and_boundaries():
    assert file_helper.clean_file_path("13–14") == "13-14"
    assert file_helper.clean_file_path("Index verborum — Vorwort") == "Index_verborum_-_Vorwort"
    assert file_helper.clean_file_path("Die wichtigste Literatur zum Kāṭhaka") == "Die_wichtigste_Literatur_zum_Kathaka"
    assert file_helper.clean_file_path("§ 1 Die Handschriften") == "1_Die_Handschriften"
    assert file_helper.clean_file_path("dir/ § 2 Foo /_index.md") == "dir/2_Foo/_index.md"
    assert file_helper.clean_file_path("Title?") == "Title"


def test_get_storage_name_mixed_german_and_devanagari():
    assert file_helper.get_storage_name("१३–१४", source_script=sanscript.DEVANAGARI) == "13-14"
    assert file_helper.get_storage_name(
        "VERZEICHNISS DER VERS- UND CAPITELANFÄNGE DES KÂṬHAKAM",
        source_script=sanscript.DEVANAGARI,
        max_length=80,
    ) == "VERZEICHNISS_DER_VERS-_UND_CAPITELANFANGE_DES_KATHAKAM"
    assert file_helper.get_storage_name(
        "Die wichtigste Literatur zum Kāṭhaka",
        source_script=sanscript.DEVANAGARI,
        max_length=80,
    ) == "Die_wichtigste_Literatur_zum_Kathaka"

"""
Hermetic test suite for pure deterministic Skyrim voice asset identity and FUZ packing.
"""

from pathlib import Path
import pytest
from src.models import StringEntry
from src.voice_assets import (
    VoiceAssetMetadataError,
    build_voice_basename,
    build_voice_relative_path,
    validate_voice_asset_entry,
    pack_fuz,
    unpack_fuz,
)


# --- 1. GOLDEN BASENAME TESTS ---

def test_golden_basename_tg00():
    """TG00 + TG00Brynjolf + 0x0136C9 + 1 -> TG00_TG00Brynjolf_000136C9_1"""
    basename = build_voice_basename(
        quest_edid="TG00",
        topic_edid="TG00Brynjolf",
        local_object_id=0x0136C9,
        response_number=1,
    )
    assert basename == "TG00_TG00Brynjolf_000136C9_1"


def test_golden_basename_long_truncation():
    """
    DialogueWhiterun (16) + DialogueWhiterunCarlottaIntro (29) -> total 45 > 25.
    Quest len 16 > 10 -> truncated to 10 (DialogueWh)
    Topic truncated to 15 (DialogueWhiteru)
    Result: DialogueWh_DialogueWhiteru_0006497C_1
    """
    basename = build_voice_basename(
        quest_edid="DialogueWhiterun",
        topic_edid="DialogueWhiterunCarlottaIntro",
        local_object_id=0x06497C,
        response_number=1,
    )
    assert basename == "DialogueWh_DialogueWhiteru_0006497C_1"


def test_golden_basename_empty_topic():
    """
    DialogueWhiterunTemple (22) + "" (0) -> total 22 <= 25.
    Result: DialogueWhiterunTemple__000D88D0_1
    """
    basename = build_voice_basename(
        quest_edid="DialogueWhiterunTemple",
        topic_edid="",
        local_object_id=0x0D88D0,
        response_number=1,
    )
    assert basename == "DialogueWhiterunTemple__000D88D0_1"


def test_golden_basename_quest_under_10_long_topic():
    """
    Quest len <= 10: 'ShortQuest' (10) + 'VeryLongTopicNameHere' (21) -> total 31 > 25.
    Quest preserved (10) -> 'ShortQuest'
    Topic gets remaining budget (25 - 10 = 15) -> 'VeryLongTopicNa'
    """
    basename = build_voice_basename(
        quest_edid="ShortQuest",
        topic_edid="VeryLongTopicNameHere",
        local_object_id=0x123456,
        response_number=1,
    )
    assert basename == "ShortQuest_VeryLongTopicNa_00123456_1"


def test_golden_basename_response_number_variations():
    """Validates raw response numbers: 0, 2, 255."""
    assert build_voice_basename("Q", "T", 0x1, 0) == "Q_T_00000001_0"
    assert build_voice_basename("Q", "T", 0x1, 2) == "Q_T_00000001_2"
    assert build_voice_basename("Q", "T", 0x1, 255) == "Q_T_00000001_255"


def test_golden_basename_formid_boundaries():
    """Validates 24-bit FormID boundary formatting and overflow rejection."""
    assert build_voice_basename("Q", "T", 0x0, 1) == "Q_T_00000000_1"
    assert build_voice_basename("Q", "T", 0xFFFFFF, 1) == "Q_T_00FFFFFF_1"

    with pytest.raises(VoiceAssetMetadataError, match="local_object_id"):
        build_voice_basename("Q", "T", -1, 1)

    with pytest.raises(VoiceAssetMetadataError, match="local_object_id"):
        build_voice_basename("Q", "T", 0x01000000, 1)  # 25-bit


def test_golden_basename_invalid_inputs():
    """Fails fast on None or non-integer response/FormID."""
    with pytest.raises(VoiceAssetMetadataError, match="quest_edid"):
        build_voice_basename(None, "Topic", 0x1, 1)  # type: ignore

    with pytest.raises(VoiceAssetMetadataError, match="topic_edid"):
        build_voice_basename("Quest", None, 0x1, 1)  # type: ignore

    with pytest.raises(VoiceAssetMetadataError, match="response_number"):
        build_voice_basename("Quest", "Topic", 0x1, -1)

    with pytest.raises(VoiceAssetMetadataError, match="response_number"):
        build_voice_basename("Quest", "Topic", 0x1, 256)


# --- 2. RELATIVE PATH & SAFETY TESTS ---

def test_build_voice_relative_path_basic():
    """Validates standard relative path generation."""
    rel = build_voice_relative_path(
        defining_plugin="Skyrim.esm",
        voice_type="MaleNord",
        basename="TG00_TG00Brynjolf_000136C9_1",
        extension=".fuz",
    )
    assert rel == Path("Sound/Voice/Skyrim.esm/MaleNord/TG00_TG00Brynjolf_000136C9_1.fuz")


def test_build_voice_relative_path_custom_plugin_and_wav():
    """Validates custom mod filename and wav staging extension."""
    rel = build_voice_relative_path(
        defining_plugin="My Custom Mod.esp",
        voice_type="FemaleCommander",
        basename="MyQuest_MyTopic_00000800_1",
        extension=".wav",
    )
    assert rel == Path("Sound/Voice/My Custom Mod.esp/FemaleCommander/MyQuest_MyTopic_00000800_1.wav")


@pytest.mark.parametrize("bad_plugin", [
    "../Skyrim.esm",
    "dir/Skyrim.esm",
    "dir\\Skyrim.esm",
    "C:\\Skyrim.esm",
    "Skyrim\x00.esm",
    "",
    "   ",
    "..",
    ".",
    "CON",
    "con",
    "CON.txt",
    "NUL.esp",
    "PRN",
    "COM1",
    "com9",
    "LPT1",
    "LPT9",
    "BadPlugin.esp ",
    "BadPlugin.esp.",
    " BadPlugin.esp",
    "Bad\x01Plugin.esp",
    "Bad\x1FPlugin.esp",
    "Bad<Plugin.esp",
    "Bad>Plugin.esp",
    "Bad:Plugin.esp",
    'Bad"Plugin.esp',
    "Bad|Plugin.esp",
    "Bad?Plugin.esp",
    "Bad*Plugin.esp",
])
def test_path_safety_rejects_malicious_plugin(bad_plugin):
    with pytest.raises(VoiceAssetMetadataError):
        build_voice_relative_path(bad_plugin, "MaleNord", "TG00_TG00Brynjolf_000136C9_1")


@pytest.mark.parametrize("bad_voice_type", [
    "../MaleNord",
    "Male/Nord",
    "Male\\Nord",
    "Male\x00Nord",
    "C:MaleNord",
    "",
    "   ",
    "Male?Nord",
    "Male*Nord",
    'Male"Nord',
    "Male<Nord",
    "Male>Nord",
    "Male|Nord",
    "CON",
    "AUX",
    "MaleNord ",
    "MaleNord.",
    " MaleNord",
    "Male\x05Nord",
])
def test_path_safety_rejects_malicious_voice_type(bad_voice_type):
    with pytest.raises(VoiceAssetMetadataError):
        build_voice_relative_path("Skyrim.esm", bad_voice_type, "TG00_TG00Brynjolf_000136C9_1")


@pytest.mark.parametrize("valid_plugin,valid_voice_type", [
    ("Skyrim.esm", "MaleNord"),
    ("Dawnguard.esm", "FemaleYoungEager"),
    ("Dragonborn.esm", "MaleEvenToned"),
    ("HearthFires.esm", "FemaleChild"),
    ("My Custom Mod.esp", "FemaleCommander"),
    ("Unofficial Skyrim Special Edition Patch.esp", "MaleBrute"),
])
def test_path_safety_preserves_valid_components(valid_plugin, valid_voice_type):
    rel = build_voice_relative_path(valid_plugin, valid_voice_type, "TG00_TG00Brynjolf_000136C9_1")
    assert rel == Path(f"Sound/Voice/{valid_plugin}/{valid_voice_type}/TG00_TG00Brynjolf_000136C9_1.fuz")


@pytest.mark.parametrize("bad_ext", ["fuz", "wav", "/.fuz", "..fuz", ".fuz\x00", "", ".fuz ", ".fuz.", ".f?z", ".f*z"])
def test_path_safety_rejects_malicious_extension(bad_ext):
    with pytest.raises(VoiceAssetMetadataError):
        build_voice_relative_path("Skyrim.esm", "MaleNord", "TG00_TG00Brynjolf_000136C9_1", extension=bad_ext)


# --- 3. MULTI-RESPONSE NON-COLLISION TEST ---

def test_multi_response_non_collision():
    """
    Simulates a multi-response INFO (0x00ABCDEF) with response numbers 1 and 2.
    Asserts distinct basenames and distinct relative paths.
    """
    base1 = build_voice_basename("QuestA", "TopicA", 0xABCDEF, 1)
    base2 = build_voice_basename("QuestA", "TopicA", 0xABCDEF, 2)

    path1 = build_voice_relative_path("Skyrim.esm", "MaleNord", base1)
    path2 = build_voice_relative_path("Skyrim.esm", "MaleNord", base2)

    assert base1 == "QuestA_TopicA_00ABCDEF_1"
    assert base2 == "QuestA_TopicA_00ABCDEF_2"
    assert base1 != base2
    assert path1 != path2
    assert str(path1).endswith("QuestA_TopicA_00ABCDEF_1.fuz")
    assert str(path2).endswith("QuestA_TopicA_00ABCDEF_2.fuz")


# --- 4. STRINGENTRY VALIDATION ---

def test_validate_voice_asset_entry_success():
    entry = StringEntry(
        form_id="000136C9",
        text="Never done an honest day's work, eh?",
        is_dialog=True,
        voice_type="MaleNord",
        defining_plugin="Skyrim.esm",
        local_object_id=0x0136C9,
        string_index=1,
        quest_edid="TG00",
        topic_edid="TG00Brynjolf",
    )
    # Should not raise
    validate_voice_asset_entry(entry)


def test_validate_voice_asset_entry_empty_topic_allowed():
    entry = StringEntry(
        form_id="000D88D0",
        text="Welcome to the temple.",
        is_dialog=True,
        voice_type="FemaleNord",
        defining_plugin="Skyrim.esm",
        local_object_id=0x0D88D0,
        string_index=1,
        quest_edid="DialogueWhiterunTemple",
        topic_edid="",  # Empty string is valid
    )
    # Should not raise
    validate_voice_asset_entry(entry)


@pytest.mark.parametrize("missing_field,value", [
    ("is_dialog", False),
    ("defining_plugin", None),
    ("voice_type", None),
    ("local_object_id", None),
    ("string_index", None),
    ("quest_edid", None),
    ("topic_edid", None),
])
def test_validate_voice_asset_entry_fails_fast_on_missing_metadata(missing_field, value):
    kwargs = {
        "form_id": "000136C9",
        "text": "Hello",
        "is_dialog": True,
        "voice_type": "MaleNord",
        "defining_plugin": "Skyrim.esm",
        "local_object_id": 0x0136C9,
        "string_index": 1,
        "quest_edid": "TG00",
        "topic_edid": "TG00Brynjolf",
    }
    kwargs[missing_field] = value
    entry = StringEntry(**kwargs)

    with pytest.raises(VoiceAssetMetadataError):
        validate_voice_asset_entry(entry)


# --- 5. FUZ BINARY PACKER & UNPACKER TESTS ---

def test_pack_and_unpack_fuz_roundtrip():
    """Verifies complete structural roundtrip of FUZ container."""
    lip_data = b"MOCK_LIP_STREAM_BYTE_PAYLOAD_12345"
    xwm_data = b"RIFF\x24\x00\x00\x00XWMAfmt \x12\x00\x00\x00DATA"

    fuz_bytes = pack_fuz(lip_bytes=lip_data, xwm_bytes=xwm_data)

    # 1. Structural header assertions
    assert len(fuz_bytes) == 12 + len(lip_data) + len(xwm_data)
    assert fuz_bytes[:4] == b"FUZE"
    assert fuz_bytes[4:8] == b"\x01\x00\x00\x00"  # Version 1 LE
    assert fuz_bytes[8:12] == len(lip_data).to_bytes(4, "little")

    # 2. Roundtrip unpack
    unpacked_lip, unpacked_xwm = unpack_fuz(fuz_bytes)
    assert unpacked_lip == lip_data
    assert unpacked_xwm == xwm_data


def test_pack_fuz_rejects_empty_payloads():
    """FUZ packer must reject empty LIP or audio bytes."""
    with pytest.raises(VoiceAssetMetadataError, match="lip_bytes"):
        pack_fuz(b"", b"audio")

    with pytest.raises(VoiceAssetMetadataError, match="xwm_bytes"):
        pack_fuz(b"lip", b"")


@pytest.mark.parametrize("corrupted_bytes", [
    b"",
    b"FUZ",
    b"NOT_FUZE_HEADER_DATA",
    b"FUZE\x02\x00\x00\x00\x04\x00\x00\x001234AUDIO",  # Version 2
    b"FUZE\x01\x00\x00\x00\x64\x00\x00\x00TRUNCATED",  # Declared lip 100 bytes, only 9 provided
    b"FUZE\x01\x00\x00\x00\x04\x00\x00\x001234",  # Zero-length audio
])
def test_unpack_fuz_rejects_malformed_container(corrupted_bytes):
    with pytest.raises(VoiceAssetMetadataError):
        unpack_fuz(corrupted_bytes)

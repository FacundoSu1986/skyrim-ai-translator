import asyncio
import os
from pathlib import Path
from src.parser import parse_strings_file
from src.translator import translate_entries
from src.tts_generator import generate_voice_file
from src.dsd_exporter import export_to_dsd

async def main():
    # Setup test paths
    plugin_name = "Skyrim.esm"
    input_file = Path("test_input.json")
    output_dsd = Path(f"output/dsd/{plugin_name}.json")
    output_voice_dir = Path(f"output/Sound/Voice/{plugin_name}")

    # Mock Input Data
    input_file.write_text("""[
        {"FormID": "00000001", "Text": "Hello there!"},
        {"FormID": "00000002", "Text": "I used to be an adventurer like you...", "is_dialog": true, "actor": "Guard"}
    ]""", encoding="utf-8")

    print("1. Parsing JSON...")
    entries = parse_strings_file(str(input_file))

    print("2. Translating Entries...")
    # Using the default placeholder mock LLM
    translated_entries = await translate_entries(entries, "spanish")

    print("3. Generating Voice Files (Mocked without network)...")
    class MockCommunicate:
        def __init__(self, text, voice):
            self.text = text
        async def save(self, filepath):
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text("dummy mp3 data")
            
    tasks = [
        generate_voice_file(entry, str(output_voice_dir), tts_class=MockCommunicate)
        for entry in translated_entries
        if entry.is_dialog
    ]
    await asyncio.gather(*tasks)

    print("4. Exporting to DSD JSON...")
    export_to_dsd(translated_entries, str(output_dsd))

    print("Pipeline Complete. Check the 'output' directory.")

if __name__ == "__main__":
    asyncio.run(main())

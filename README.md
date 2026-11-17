# ComfyUI-YuE2-HumComposer

A work-in-progress ComfyUI extension for incorporating hummed melodies into YuE2-generated songs. It combines SheetSage2 transcription with ABC-based melody placement, variation, and score editing.

**Experimental and under active development.** The workflow can be run, but features, compatibility, and output quality are still being validated.

## Getting started

1. Place this folder in `ComfyUI/custom_nodes/ComfyUI-YuE2-HumComposer`.
2. Restart ComfyUI and refresh your browser.
3. Load the [integrated example workflow](examples/sheetsage_composition_workflow.json) and select an installed YuE2 checkpoint.
4. Set the style and lyrics, then run the workflow.

To use humming, select a SheetSage2 encoder and audio files, then enable the corresponding **BOOL** controls for the main theme or Intro/Bridge overrides before running. All audio inputs are disabled by default. The example uses ComfyUI's native YuE2 and SheetSage2 nodes; model files are not included.

## Development scope

- Optional main-theme humming and separate Intro/Bridge audio overrides, each controlled independently
- ABC melody analysis with key and chord progression suggestions
- Main-theme placement in compatible score regions, independent of section names, with repeated statements and limited variation
- Section-specific melody controls: use the supplied melody (`LOCK`), apply limited variation (`VARIATION`), or retain the generated material (`AI`)
- Staff notation, ABC, and piano roll editing with on-screen piano and computer keyboard input, multiple voices, and chords

# ComfyUI-YuE2-HumComposer

**English** | [한국어](docs/i18n/ko/README.md)

HumComposer is a ComfyUI custom-node extension for **melody-guided music composition**. Use a microphone recording, an audio file, or an ABC score as input. HumComposer analyzes the melody, applies it to selected sections of a song, and sends the resulting ABC score to **ComfyUI's native YuE2 music generation workflow**.

## Requirements

- An up-to-date **ComfyUI** installation. Native YuE2 requires [ComfyUI v0.36.0 or later](https://docs.comfy.org/tutorials/audio/yue2/yue2).
- **Python 3.10 or later**, as specified in the HumComposer package metadata. Use the Python environment configured for your ComfyUI installation.
- **YuE2 checkpoint**. Place the example's default checkpoint, `yue2_3b_int8_convrot.safetensors`, in ComfyUI's `models/checkpoints/` folder and select it in **Load Checkpoint**.
- **SheetSage2 for audio transcription**. Place `sheetsage2_bf16.safetensors` in `models/audio_encoders/`.
- Allow microphone access in your browser to record directly.

Obtain the model files separately by following the [official ComfyUI YuE2 guide](https://docs.comfy.org/tutorials/audio/yue2/yue2). VRAM requirements depend on the checkpoint and generation settings. HumComposer uses ComfyUI's Python environment and declares no additional runtime dependencies in `pyproject.toml`.

## Installation

Run these commands from the **ComfyUI folder** that contains `custom_nodes`.

```bash
cd custom_nodes
git clone https://github.com/junhoKim-iib/ComfyUI-YuE2-HumComposer.git
```

Restart ComfyUI and refresh the browser. In **Add Node**, look for the custom nodes under this category.

```text
audio > YuE2 > Hum Composer
```

## Quick start

### A. Generate your first track with the example

1. Load the [example workflow](examples/sheetsage_composition_workflow.json) in ComfyUI.
2. Select your installed YuE2 checkpoint in **Load Checkpoint**. For the first run, use the default style and lyrics and leave all three audio switches off.
3. Run the workflow and listen in **Preview completed audio** (`Preview Audio`). You can change the style and lyrics in the **Song style and structure** and **Complete lyrics (two choruses)** nodes.

### B. Add humming or an audio file to the example

1. Find **Official SheetSage2 model loader** in the **01 Models** group on the left. Select `sheetsage2_bf16.safetensors` and turn on **Use main-theme audio · BOOL**.
2. In **Main-theme audio input**, choose `file` to select an audio file or `microphone` to record a take.
3. Run the workflow again. Check the main-theme analysis and final score, then listen in **Preview completed audio**.

Start with a single short recording for the main theme. To apply melodies to individual sections, turn on **Override Intro · BOOL** or **Override Bridge · BOOL** and select the corresponding audio input.

### C. Build a workflow by hand

1. Load the SheetSage2 audio encoder. Add **Load Audio Encoder** from the node search and select `sheetsage2_bf16.safetensors`.
2. Select a file or record a take in **YuE2 Hum Audio Input**. Connect the encoder's `AUDIO_ENCODER` output and the input node's `AUDIO` output to **YuE2 Hum Transcribe**. Choose `melody` for melody only or `full` for melody and chords.
3. Connect the transcriber's `abc` output to **YuE2 Hum Melody Analyze**. To read the analysis, connect `summary` to the `source` input on **Preview as Text**.
4. To use the melody as the main theme, connect `analysis` to `main_theme` on **YuE2 Hum Song Composer**. To apply a melody to a section, set the ABC and target section in **YuE2 Set Section Melody**. Connect that node to **YuE2 Collect Section Melodies** and send the collected list to `anchors` on the Composer.
5. Connect the `abc` output from **YuE2 Generate ABC** or **YuE2 Hum Generate Required ABC** to `base_abc` on the Composer. If you use **YuE2 Hum Generate Required ABC**, also connect the `main_theme` and `anchors` you want to apply so the generator can check their requirements.
6. Connect the Composer's `final_abc` to `source_abc` on **YuE2 ABC Score Editor**. For audio generation, reuse the example's model, style, and lyrics connections and the **07 Final ABC → YuE2 generation → sampling → audio** group. Connect the Editor's `edited_abc` to `abc` on **YuE2 Generate Music**, run the workflow again, and listen in **Preview Audio**.

### D. Start from an existing ABC score

- **Analyze a melody** — Paste the ABC into **YuE2 Hum Melody Analyze** and connect `summary` to the text preview as shown above.
- **Place a melody in a section** — Enter the melody ABC and target section in **YuE2 Set Section Melody**. Build a list with **YuE2 Collect Section Melodies** and connect it to `anchors` on the Composer. Connect the song's base score to `base_abc`.
- **Edit a score** — Open **Edit ABC directly** in **YuE2 ABC Score Editor** and paste the ABC.
- **Generate audio** — Use a score for the entire song, such as this [full-song ABC example for YuE2](examples/yue2_song.abc). Reuse the example's model, style, lyrics, and audio generation connections. Enter the score directly into `abc` on **YuE2 Generate Music** or connect the Editor's `edited_abc`. Listen in **Preview Audio**. The native song check in **YuE2 ABC Validate** checks compatibility, including the `Vocal` and `Ins` voices and bar lengths.

## Features

- **Microphone or audio file input** — Record directly in ComfyUI or select an existing audio file.
- **Audio-to-ABC transcription** — Transcribe input audio into an ABC score with SheetSage2.
- **Melody analysis** — Analyze a transcribed or handwritten ABC melody.
- **Key, mode, and harmony suggestions** — Rank key and mode candidates and suggest chord progressions.
- **Section melody placement** — Use a recording in a section of the song. For example, replace just the instrumental melody in the first intro.
- **Main-theme placement** — Place a user-supplied theme in compatible sections and repeat or vary it in later sections.
- **ABC score editing** — View staff notation and a piano roll, and edit notes, chords, and voices.

## How it works

SheetSage2 transcribes microphone recordings and audio files. You can use both transcribed and handwritten ABC to analyze melodies, get key and chord suggestions, and place a main theme or section melody.

```text
Base ABC + main theme or section melodies
  ↓
YuE2 Hum Song Composer
  ↓
YuE2 ABC Score Editor → YuE2 ABC Validate
  ↓
YuE2 Generate Music
  ↓
KSampler → VAE Decode Audio → Preview Audio
```

Sampling uses the `CONDITIONING` output from `YuE2 Generate Music`. The `seconds` output goes to **Empty YuE2 Latent Audio** to set the duration for sampling.

## Section melody modes

| Mode | Behavior |
| --- | --- |
| `LOCK` | Replace the melody in the selected section. The score must meet the structural and validation requirements. |
| `VARIATION` | Use the seed and variation settings to generate a variation and apply it to the section. |
| `AI` | Keep the base ABC for the selected section. |

You can choose which occurrence of the section to change, whether to target the vocal or instrumental voice, and how to handle length, key, and harmony. Incompatible settings produce an error.

## Included nodes

Find all HumComposer nodes under `audio/YuE2/Hum Composer`.

| Node | Purpose |
| --- | --- |
| **YuE2 Hum Audio Input** | Select an audio file or record from a microphone |
| **YuE2 Hum Transcribe** | Transcribe audio into ABC with SheetSage2 |
| **YuE2 Hum Melody Analyze** | Analyze a melody in ABC |
| **YuE2 Key & Mode Candidates** | Suggest candidate keys and modes |
| **YuE2 Chord Progression Recommend** | Suggest chord progressions for the melody |
| **YuE2 Set Section Melody** | Choose the melody, target section, and how to apply it |
| **YuE2 Collect Section Melodies** | Collect the melodies to apply to the song's sections |
| **YuE2 Hum Generate Required ABC** | Generate a base YuE2 score and check section and melody requirements |
| **YuE2 Hum Song Composer** | Apply section melodies or a main theme to the base score |
| **YuE2 ABC Validate** | Check ABC syntax and structural constraints |
| **YuE2 ABC Score Editor** | Edit notes, chords, bars, and voices in the score and piano roll |

## Current limitations

- **Audio is regenerated from the score.** The recording supplies a melody through ABC transcription. Native YuE2 uses that score to generate new vocals and accompaniment.
- **Melody reproduction depends on the model.** The rendered audio can differ even when the final ABC preserves the notes.
- **Transcription can contain errors.** SheetSage2 can misidentify pitches, rhythms, chords, and instruments. Review the ABC before composing. The extension can retry a specific transcription-grid error.
- **ABC structure matters.** Section names, meter and bar lengths, ties, voice layout, and token budget can affect composition. The workflow reports an error when it cannot meet an enabled melody requirement.
- **Audio generation requires ComfyUI's native YuE2 pipeline.**

## License

HumComposer is licensed under the [GNU General Public License, version 3](LICENSE) (`GPL-3.0-only`).

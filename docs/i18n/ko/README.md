# ComfyUI-YuE2-HumComposer

[English](../../../README.md) | **한국어**

HumComposer는 **멜로디 기반 음악 작곡**을 위한 ComfyUI 커스텀 노드 확장입니다. 마이크 녹음, 오디오 파일 또는 ABC 악보를 입력해 음악적 특징을 분석하고, 곡의 특정 구간에 멜로디를 반영한 후, 완성된 ABC 악보를 **ComfyUI의 네이티브 YuE2 음악 생성 워크플로**로 전달합니다.

## 요구 사항

- 최신 **ComfyUI**. 네이티브 YuE2는 [ComfyUI v0.36.0 이상](https://docs.comfy.org/tutorials/audio/yue2/yue2)이 필요합니다.
- **Python 3.10 이상** (HumComposer 패키지 메타데이터 기준). ComfyUI 설치 환경에서 사용하는 Python을 따릅니다.
- **YuE2 체크포인트**. 예제 기본값인 `yue2_3b_int8_convrot.safetensors`를 ComfyUI의 `models/checkpoints/`에 넣고 **Load Checkpoint**에서 선택합니다.
- **SheetSage2 (오디오 채보 시)**. `sheetsage2_bf16.safetensors`를 `models/audio_encoders/`에 넣습니다.
- 마이크로 바로 녹음하려면 브라우저에서 마이크 접근을 허용합니다.

모델 파일은 저장소에 포함되어 있지 않습니다. 다운로드와 설치는 [ComfyUI 공식 YuE2 가이드](https://docs.comfy.org/tutorials/audio/yue2/yue2)를 참고하세요. 필요한 VRAM은 체크포인트와 생성 설정에 따라 달라집니다. HumComposer는 ComfyUI의 Python 환경을 사용하며, `pyproject.toml`에 별도 런타임 의존성을 선언하지 않습니다.


## 설치

`custom_nodes`가 있는 **ComfyUI 폴더**에서 아래 명령을 실행합니다.

```bash
cd custom_nodes
git clone https://github.com/junhoKim-iib/ComfyUI-YuE2-HumComposer.git
```

ComfyUI를 재시작하고 브라우저를 새로 고침합니다. Add Node의 다음 카테고리에서 커스텀 노드를 찾을 수 있습니다.

```text
audio > YuE2 > Hum Composer
```

## 빠른 시작

### A. 예제로 첫 음원 생성하기

1. [예제 workflow](../../../examples/sheetsage_composition_workflow.json)를 ComfyUI에서 불러옵니다.
2. **Load Checkpoint**에서 설치한 YuE2 체크포인트를 선택합니다. 첫 실행에서는 기본 스타일·가사를 사용하고 오디오 스위치 세 개를 모두 꺼 둡니다.
3. 워크플로를 실행하고 **완성 오디오 미리보기**(`Preview Audio`)에서 결과를 듣습니다. 스타일과 가사는 예제의 **곡 스타일·구조**와 **전체 가사** 노드에서 바꿀 수 있습니다.

### B. 예제에 허밍이나 오디오 파일 추가하기

1. 예제 왼쪽의 **01 모델** 그룹에서 **공식 SheetSage2 모델 로더**를 찾습니다. `sheetsage2_bf16.safetensors`를 선택하고 **메인 주제 오디오 사용** 의  **BOOL**을 켭니다.
2. **메인 주제 오디오 입력**에서 `file`을 선택해 파일을 지정하거나 `microphone`을 선택해 녹음합니다.
3. 다시 실행한 뒤 메인 테마 분석과 최종 악보를 확인하고, **완성 오디오 미리보기**에서 결과를 듣습니다.

처음에는 짧은 녹음 하나로 메인 테마를 적용해 보세요. 예제의 **Intro 구간 덮어쓰기**와 **Bridge 구간 덮어쓰기** 의 **BOOL** 을 켜고 해당 오디오 입력을 지정하면 구간별로 멜로디를 적용할 수 있습니다.

### C. 워크플로 직접 구성하기

1. SheetSage2 오디오 인코더를 불러옵니다. 노드 검색에서 **오디오 인코더 로더**(영문 UI의 **Load Audio Encoder**)를 추가한 뒤 `sheetsage2_bf16.safetensors`를 선택합니다.
2. **YuE2 Hum Audio Input**에서 파일을 선택하거나 녹음합니다. 오디오 인코더의 `AUDIO_ENCODER` 출력과 오디오 입력 노드의 `AUDIO` 출력을 **YuE2 Hum Transcribe**에 연결합니다. `melody`는 멜로디만, `full`은 멜로디와 코드까지 채보합니다.
3. 채보 노드의 `abc` 출력을 **YuE2 Hum Melody Analyze**에 연결합니다. 분석 결과를 화면에서 보려면 분석 노드의 `summary`를 텍스트 미리보기 노드 **미리보기 아무거나**(영문 **Preview as Text**)의 `source`에 연결합니다.
4. 메인 테마를 사용하려면 분석 노드의 `analysis` 출력을 **YuE2 Hum Song Composer**의 `main_theme`에 연결합니다. 특정 구간에 멜로디를 배치하려면 **YuE2 구간 멜로디 지정**에서 ABC와 적용 구간을 지정합니다. 이 노드의 출력을 **YuE2 구간 멜로디 모으기**에 연결하고, 모은 목록을 Composer의 `anchors`로 보냅니다.
5. **YuE2 Generate ABC** 또는 **YuE2 Hum Generate Required ABC**의 `abc`를 Composer의 `base_abc`에 연결합니다. **YuE2 Hum Generate Required ABC**를 쓸 때는 사용할 `main_theme`와 `anchors`를 그 노드에도 연결하면 생성 단계에서 요구사항을 검사합니다.
6. Composer의 `final_abc`를 **YuE2 ABC Score Editor**의 `source_abc`에 연결합니다. 음원 생성에는 예제의 모델·스타일·가사 연결과 **07 최종 ABC → YuE2 생성 → 샘플링 → 오디오** 그룹을 활용합니다. Editor의 `edited_abc`를 **YuE2 Generate Music**의 `abc`에 연결한 뒤 다시 실행해 **Preview Audio**에서 듣습니다.

### D. 기존 ABC 악보로 시작하기

- **멜로디 분석** — ABC를 **YuE2 Hum Melody Analyze**에 붙여 넣고, 위와 같이 `summary`를 텍스트 미리보기에 연결합니다.
- **구간 배치** — **YuE2 구간 멜로디 지정**에 멜로디 ABC와 적용할 구간을 입력합니다. **YuE2 구간 멜로디 모으기**에서 목록을 만들어 Composer의 `anchors`에 연결하고, 곡의 기본 악보는 `base_abc`에 연결합니다.
- **악보 편집** — **YuE2 ABC Score Editor**에서 **ABC 직접 편집**을 펼친 뒤 ABC를 붙여 넣습니다.
- **음원 생성** — [YuE2용 전체 ABC 예시](../../../examples/yue2_song.abc)처럼 곡 전체가 담긴 악보를 사용합니다. 예제의 모델·스타일·가사와 오디오 생성 연결을 활용하고, **YuE2 Generate Music**의 `abc`에 악보를 직접 입력하거나 Editor의 `edited_abc`를 연결합니다. 결과는 **Preview Audio**에서 듣습니다. **YuE2 ABC Validate**의 네이티브 곡 검사를 사용하면 `Vocal`·`Ins` 성부와 마디 길이 등의 호환성을 확인할 수 있습니다.

## 주요 기능

- **마이크 / 오디오 파일 입력** — ComfyUI에서 직접 녹음하거나 기존 오디오 파일을 선택할 수 있습니다.
- **오디오 → ABC 채보** — SheetSage2가 입력 오디오를 ABC 악보로 옮깁니다.
- **멜로디 분석** — 채보하거나 직접 작성한 ABC 악보의 멜로디를 분석합니다.
- **조성·선법·화성 추천** — 조성 및 선법 후보를 순위화하고, 코드 진행을 추천합니다.
- **구간별 멜로디 지정** — 녹음한 멜로디를 곡의 원하는 구간에 넣을 수 있습니다. 예를 들어 첫 번째 인트로의 악기 멜로디만 바꿀 수 있습니다.
- **메인 테마 배치** — 사용자가 정한 주제 선율을 호환되는 구간에 삽입하고, 이후 등장하는 구간에 반복 또는 변형할 수 있습니다.
- **ABC 악보 편집** — 오선보와 피아노 롤을 확인하고 음표·코드·성부 등을 편집합니다.


## 작동 구조

마이크 녹음과 오디오 파일은 SheetSage2로 채보합니다. 채보한 ABC와 직접 작성한 ABC 모두 멜로디 분석, 조성·코드 진행 추천, 메인 테마나 구간별 멜로디 배치에 사용할 수 있습니다.

```text
기본 ABC + 메인 테마 또는 구간별 멜로디
  ↓
YuE2 Hum Song Composer
  ↓
YuE2 ABC Score Editor → YuE2 ABC Validate
  ↓
YuE2 Generate Music
  ↓
KSampler → VAE Decode Audio → Preview Audio
```

`YuE2 Generate Music`의 `CONDITIONING`은 샘플링에 사용됩니다. `seconds`는 **Empty YuE2 Latent Audio**로 전달되어 샘플링할 오디오 길이를 정합니다.

## 구간별 멜로디 적용 방식

| 모드 | 동작 |
| --- | --- |
| `LOCK` | 악보의 특정 구간을 입력 멜로디로 치환합니다. 악보 구조와 검증 조건이 일치해야 합니다. |
| `VARIATION` | 시드와 변형 파라미터를 사용해 멜로디의 변주를 생성한 뒤 구간에 반영합니다. |
| `AI` | 대상 구간의 기본 ABC를 유지합니다. |

몇 번째 구간에 적용할지, 보컬과 악기 중 어느 파트에 넣을지, 길이·조성·화성을 어떻게 맞출지도 선택할 수 있습니다. 악보 구조와 맞지 않는 설정은 오류로 표시됩니다.

## 포함된 노드

모든 노드는 `audio/YuE2/Hum Composer`에 등록됩니다.

| 노드 | 역할 |
| --- | --- |
| **YuE2 Hum Audio Input** | 오디오 파일 또는 마이크 녹음 선택 |
| **YuE2 Hum Transcribe** | SheetSage2로 오디오를 ABC 악보로 변환 |
| **YuE2 Hum Melody Analyze** | ABC 멜로디 분석 |
| **YuE2 Key & Mode Candidates** | 조성 및 선법 후보 추천 |
| **YuE2 Chord Progression Recommend** | 멜로디에 맞는 코드 진행 추천 |
| **YuE2 구간 멜로디 지정** (YuE2 Set Section Melody) | 사용할 멜로디와 적용할 구간, 적용 방식 지정 |
| **YuE2 구간 멜로디 모으기** (YuE2 Collect Section Melodies) | 곡에 적용할 구간별 멜로디를 한 목록으로 모으기 |
| **YuE2 Hum Generate Required ABC** | 구간과 멜로디 요구사항을 검증하며 기본 YuE2 ABC 악보 생성 |
| **YuE2 Hum Song Composer** | 기본 ABC 악보에 구간별 멜로디 또는 메인 테마 반영 |
| **YuE2 ABC Validate** | ABC 문법 및 구조적 제약 검증 |
| **YuE2 ABC Score Editor** | 악보·피아노 롤에서 음표, 코드, 마디, 성부 편집 |

## 현재 제한 사항

- **직접적인 오디오→오디오 커버 또는 음성 복제 기능이 아닙니다.** 입력 오디오를 ABC로 변환한 뒤 네이티브 YuE2에서 새 음원을 생성합니다.
- **최종 음원에서 멜로디가 완전히 동일하게 재현되는 것을 보장하지 않습니다.** 최종 ABC의 음표를 유지하더라도 오디오 생성 결과는 모델의 영향을 받습니다.
- **채보 오류가 발생할 수 있습니다.** SheetSage2가 음정·리듬·코드·악기를 잘못 분석할 수 있으므로 ABC를 검토해야 합니다. 특정 채보 그리드 오류에 대한 재시도는 있지만 모든 오류를 복구하지는 않습니다.
- **ABC 구조 호환성이 중요합니다.** 구간 이름, 박자·마디 길이, 붙임줄, 성부 구성, 토큰 예산 등에 따라 작곡이 실패할 수 있습니다. 활성화된 멜로디 요구사항을 충족할 수 없으면 오류가 표시됩니다.
- **독립적인 음악 생성 엔진이 아닙니다.** 실제 음원 생성에는 ComfyUI의 네이티브 YuE2가 필요합니다.

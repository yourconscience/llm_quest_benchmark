# Datasheet: LLM-Quest Benchmark

Following the "Datasheets for Datasets" framework (Gebru et al., 2021).

Last updated: 2026-05-05

---

## Motivation

**Why was the dataset created?**

To evaluate LLM agent architectures on interactive fiction decision-making.
Text-based quests require reading comprehension, multi-step planning, state
tracking, and choosing among discrete actions under uncertainty -- capabilities
that static QA benchmarks do not exercise.

**Who created it and on whose behalf?**

The benchmark was created by the LLM Quest Benchmark project (MIT license).
The underlying quest files were created by the Space Rangers game community
over many years and are hosted on GitLab by Vasilii Rogin's
`spacerangers.gitlab.io` project.

**Who funded the creation?**

No external funding. The benchmark is a personal/open-source project.
The quest content is community-created fan work.

---

## Composition

**What does the dataset consist of?**

150 quest files in `.qm` / `.qmm` binary format, organized into 9 collections:

| Collection | Files | Language | Source |
|---|---|---|---|
| sr_2_1_2121_eng | 35 | English | Space Rangers 2 v2.1.2121 |
| kr_1_ru | 26 | Russian | Space Rangers 1 (KR 1) |
| sr_2_dominators_ru | 35 | Russian | SR2 Dominators |
| sr_2_reboot_ru | 21 | Russian | SR2 Dominators Reboot |
| fanmade_ru | 15 | Russian | Fan-made quests |
| sr_2_revolution_fan_ru | 9 | Russian | SR2 HD Revolution (fan) |
| sr_2_revolution_ru | 6 | Russian | SR2 HD Revolution (official) |
| sr_2_1_2170_ru | 1 | Russian | SR2 v2.1.2170 |
| sr_2_2_1_2369_ru | 1 | Russian | SR2 v2.1.2369 |

35 quests are in English; 115 are in Russian.

**What is the .qm format?**

A binary format for interactive quests from the Space Rangers game series.
Each file encodes a directed graph of locations (text passages) and
transitions (player choices), with parameters, conditions, and formulas
controlling game state. The format specification is documented in
`space-rangers-quest/lastqm.txt` (in Russian) and implemented by the
TypeScript quest engine in `space-rangers-quest/src/`.

**What does each instance represent?**

A single quest is a self-contained interactive fiction scenario. The player
reads narrative text and selects from available choices. Quests have one or
more success endings and one or more failure endings. A typical quest has
10-50 decision points, though some are shorter or longer.

**What is the current benchmark scope?**

The published leaderboard uses a comparable 15-quest slice:

Badday_eng, Banket_eng, Boat, Codebox_eng, Depth_eng, Driver_eng,
Edelweiss_eng, Election_eng, Foncers_eng, Leonardo_eng, Ministry_eng,
Pizza_eng, Prison_eng, Robots_eng, Ski_eng

These are the quest IDs with results from all six primary publication
models. Additional exploratory benchmark runs exist in raw benchmark
artifacts but are excluded from the public leaderboard when they do not
support direct model-to-model comparison.

**How many runs exist?**

1615 published leaderboard runs across 6 primary models and 8 taxonomy labels
(as of 2026-05-05).

Model families include Anthropic, DeepSeek, Google, Minimax, Mistral, and
OpenAI.

Taxonomy labels: Minimal prompt, Short-context reasoning,
Full-history reasoning, Compact memory / memo, Prompt hints,
Tools + compact memory, Tools + hints + compact memory, and Planner loop.
Minimal prompt and short-context reasoning have the broadest coverage;
the other labels are reported where they exist and should be read as
intervention experiments rather than a complete rectangular matrix.

**Is there a difficulty distribution?**

Not formally measured. Quest difficulty varies substantially -- some quests
are nearly trivial (one obvious path), others have complex branching with
many failure states. Formal difficulty annotation is TBD.

**Are there label errors or noise?**

Quest outcomes (success/failure) are determined by the quest engine, not
by human annotation, so there are no labeling errors in the traditional
sense. However, some quests may have dead-end paths that are reachable
only through specific parameter combinations, which could appear as
engine bugs rather than intentional design.

**Is the dataset self-contained?**

No. Quest files are downloaded separately via `download_quests.sh` and are
not committed to the benchmark repository. The benchmark code, leaderboard
results, and analysis tools are in the repository; the quest data is fetched
from upstream.

---

## Collection Process

**How was the data acquired?**

Quest files are downloaded from the Space Rangers community GitLab archive:
`https://gitlab.com/spacerangers/spacerangers.gitlab.io`

The `download_quests.sh` script handles acquisition:

1. Clones the GitLab repo (sparse checkout, depth 1) or downloads the ZIP archive.
2. Copies `.qm` and `.qmm` files from `borrowed/qm/` subdirectories.
3. Organizes files into flat per-collection directories under `quests/`.
4. Handles filename collisions by appending `__N` suffixes.

**Who created the quest content?**

The original quests were created by the developers of Space Rangers 1 and 2
(Elemental Games / 1C Company, early 2000s). Fan-made quests were created by
the Space Rangers modding community. Individual quest authors are not
systematically tracked in the .qm files.

**Over what timeframe?**

The original game quests date from 2002-2007. Fan-made quests span roughly
2005-2020s. The GitLab archive is a living collection maintained by the
community.

**Were any ethical review processes conducted?**

No. The quests are sci-fi game content. They contain fictional scenarios
involving alien civilizations, space travel, and planetary adventures.
No real-world personal data is involved.

---

## Preprocessing / Cleaning

**What preprocessing was done?**

- Collections are mapped from their upstream directory names (which include
  Cyrillic characters) to ASCII-safe directory names via the `QUEST_MAP`
  in `download_quests.sh`.
- Duplicate filenames across collections are disambiguated with `__N` suffixes.
- The `Boat.qm` file is copied to the quests root as a default smoke-test quest.

**Was deduplication performed?**

Filename-level deduplication within each collection (collision handling).
Content-level deduplication across collections has not been performed --
some quests may appear in multiple collections (e.g., original vs. remastered).

**How were the public leaderboard quests selected?**

The public leaderboard is a curated comparison slice. A quest is included
only if it parses correctly, presents meaningful choices, terminates within
the step limit, and has results from all six primary publication models.
This removes one-model exploratory quests from the public table while
preserving the raw benchmark artifacts for follow-up analysis.

**Is language detection automated?**

No. Language is determined by collection: `sr_2_1_2121_eng` contains English
quests; all other collections are Russian. This is based on the upstream
archive structure.

---

## Uses

**What is the dataset intended for?**

Benchmarking LLM decision-making in interactive text environments. Specific
use cases:

- Comparing LLM agent architectures (baseline, prompted reasoning,
  knowledge-augmented, planner-based).
- Measuring how different models handle multi-step sequential decisions.
- Evaluating reading comprehension and state tracking under game constraints.

**What should it not be used for?**

- General NLP benchmarks: the quest format is narrow and domain-specific.
- Language model training data: the quests are copyrighted game content.
- Human subject research: no human behavioral data is collected.

**Are there tasks for which the dataset should not be used?**

The quests contain fictional sci-fi scenarios. Some may include mild violence
or morally ambiguous choices typical of adventure games. They are not suitable
as training data for safety-critical decision systems.

---

## Distribution

**How is the dataset distributed?**

- Benchmark code (runner, analysis, leaderboard): MIT license, in this
  repository.
- Quest engine (`space-rangers-quest/` submodule): MIT license, copyright
  Vasilii Rogin (2023).
- Quest files (.qm/.qmm): community-created content from the Space Rangers
  modding community, hosted on GitLab. Downloaded on demand via
  `download_quests.sh`. Not redistributed in this repository.
- Benchmark results (leaderboard.json): included in the repository under
  `site/`.

**Is there a license for the quest content?**

The quest files themselves are game assets and fan-created content. The
upstream GitLab archive does not specify a separate license for the .qm
files. The quest engine that reads them is MIT-licensed. The original game
content is copyrighted by Elemental Games / 1C Company; fan-made content
is community work with no formal licensing.

**Are there export controls or regulatory restrictions?**

None known.

---

## Maintenance

**Who maintains the dataset?**

The benchmark is maintained at:
`https://github.com/yourconscience/llm_quest_benchmark`

The upstream quest archive is maintained by the Space Rangers community at:
`https://gitlab.com/spacerangers/spacerangers.gitlab.io`

**How can the quest corpus be updated?**

Run `./download_quests.sh --refresh` to re-download from the upstream GitLab
archive. New quests added upstream will appear in the appropriate collection
directories.

**Will the dataset be updated?**

The benchmark aims to expand coverage:
- Benchmark all 35 English quests (currently 15).
- Add Russian quest support.
- Formal difficulty annotation.
- Per-quest metadata (author, estimated length, branching factor).

These are aspirational; no fixed timeline.

**Is there a deprecation plan?**

No. The benchmark will remain available as long as the upstream quest
archive exists. If the GitLab archive goes offline, the quest files would
need to be sourced from game installations directly.

---

## Citation

If you use this benchmark, please cite:

```
@software{llm_quest_benchmark,
  title = {LLM-Quest Benchmark},
  url = {https://github.com/yourconscience/llm_quest_benchmark},
  year = {2025}
}
```

For the Datasheets for Datasets framework:

```
@article{gebru2021datasheets,
  title = {Datasheets for Datasets},
  author = {Gebru, Timnit and Morgenstern, Jamie and Vecchione, Brenda
    and Vaughan, Jennifer Wortman and Wallach, Hanna and {Daum{\'e} III},
    Hal and Crawford, Kate},
  journal = {Communications of the ACM},
  volume = {64},
  number = {12},
  pages = {86--92},
  year = {2021}
}
```

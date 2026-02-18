# Benchmark Report

Generated: 2026-02-16T21:29:22

## CLI_benchmark_20260216_212006

| Metric | Value |
|---|---:|
| Total runs | 6 |
| Success | 3 |
| Failure | 3 |
| Timeout | 0 |
| Error | 0 |
| Success rate | 50.0% |
| Avg duration | 28.12s |
| Total tokens | 58761 |
| Estimated cost (USD) | 0.016893 |

### Model Breakdown

| Model | Runs | Success | Failure | Timeout | Error | Success Rate | Tokens | Est. Cost (USD) | Default Decision Rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek-3.2-chat | 6 | 3 | 3 | 0 | 0 | 50.0% | 58761 | 0.016893 | 0.0% |

### Failure Highlights

- run `2064` | model `deepseek-3.2-chat` | quest `Examen` | outcome `FAILURE`
  selected: 1: Броситься на помощь алкарису (трезво оценив свои силы)
  reasoning: Saving intelligent being aligns with heroism, may unlock future assistance or clues.
  observation: Библиотека располагалась на другом конце университетского кампуса. Вы решили срезать себе путь и пройти мимо пустыря позади университетских гаражей. При этом вы случайно увидели, как на пустыре три хулигана издевались...
  summary: `results/llm_deepseek-3.2-chat/Examen/run_2064/run_summary.json`
- run `2058` | model `deepseek-3.2-chat` | quest `Fishing` | outcome `FAILURE`
  selected: 1: Пойти в другой конец пруда
  reasoning: Eastern shore is swampy and overgrown. Changing location may yield better fishing conditions.
  observation: Вы находитесь на восточном берегу пруда. Берег здесь весьма заболочен, а сам пруд зарос камышом. Вы решили не садиться на землю вообще. Что делать дальше?
  summary: `results/llm_deepseek-3.2-chat/Fishing/run_2058/run_summary.json`
- run `2060` | model `deepseek-3.2-chat` | quest `Gobsaur` | outcome `FAILURE`
  selected: 3: Искать диск
  reasoning: Searching for the disc directly addresses mission objective with minimal risk.
  observation: Вы пошли по следам и вскоре пришли к большой пещере, из которой доносился громкий храп. Заглянув внутрь, вы обнаружили разбросанные повсюду кости и в дальнем углу берлоги - огромного монстра. Раз в пять выше вас, зеле...
  summary: `results/llm_deepseek-3.2-chat/Gobsaur/run_2060/run_summary.json`

## CLI_benchmark_20260216_212342

| Metric | Value |
|---|---:|
| Total runs | 6 |
| Success | 4 |
| Failure | 2 |
| Timeout | 0 |
| Error | 0 |
| Success rate | 66.7% |
| Avg duration | 31.06s |
| Total tokens | 62480 |
| Estimated cost (USD) | 0.017958 |

### Model Breakdown

| Model | Runs | Success | Failure | Timeout | Error | Success Rate | Tokens | Est. Cost (USD) | Default Decision Rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek-3.2-chat | 6 | 4 | 2 | 0 | 0 | 66.7% | 62480 | 0.017958 | 0.0% |

### Failure Highlights

- run `2076` | model `deepseek-3.2-chat` | quest `Examen` | outcome `FAILURE`
  selected: 3: Сдавать профессору
  reasoning: Professor may be stricter but offers narrative connection to earlier library study.
  observation: Экзамен по литературе принимали двое: пожилой профессор-гаалец, в котором вы с удивлением узнали ректора, и молодой ассистент-пеленг. Кому вы будете сдавать экзамен?
  summary: `results/llm_deepseek-3.2-chat/Examen/run_2076/run_summary.json`
- run `2072` | model `deepseek-3.2-chat` | quest `Gobsaur` | outcome `FAILURE`
  selected: 1: Искать диск
  reasoning: Searching for disc aligns with mission, avoids unnecessary risk with sleeping creature.
  observation: Вы пошли по следам и вскоре пришли к большой пещере, из которой доносился громкий храп. Заглянув внутрь, вы обнаружили разбросанные повсюду кости и в дальнем углу берлоги - огромного монстра. Раз в пять выше вас, зеле...
  summary: `results/llm_deepseek-3.2-chat/Gobsaur/run_2072/run_summary.json`

## Combined Overview

| Metric | Value |
|---|---:|
| Benchmarks | 2 |
| Total runs | 12 |
| Success rate | 58.3% |
| Total tokens | 121241 |
| Estimated cost (USD) | 0.034851 |

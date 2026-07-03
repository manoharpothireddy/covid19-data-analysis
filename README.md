# Real-Time Toxic Comment Moderation System with Attention-Based Modeling and Safety Override

Production-style moderation system for latency-aware toxic comment moderation using an attention-based sequence model with pretrained embeddings, FastAPI, policy-aware decision logic, safety overrides, real-time streaming, and human-in-the-loop review. The system is designed for CPU inference on free-tier platforms and for IEEE-style experiments that report moderation quality, latency, throughput, and safety behavior.

## Project Structure

```text
.
├── api/
│   ├── decision.py          # Rule-based moderation policy
│   ├── inference.py         # Startup-loaded moderation model/tokenizer pipeline
│   ├── main.py              # FastAPI app with moderation endpoints and /health
│   └── schemas.py           # Request/response contracts
├── evaluation/
│   ├── benchmark_api.py     # 100+ request latency and throughput benchmark
│   └── compare_models.py    # LSTM vs LSTM+Attention and sequence length study
├── model/
│   ├── architecture.py      # Lightweight LSTM and LSTM+Attention models
│   ├── attention.py         # Serializable Keras attention layer
│   ├── glove.py             # GloVe 100d loading and embedding matrix creation
│   └── train.py             # Training, validation, threshold search, artifact export
├── utils/
│   ├── config.py            # Shared constants and artifact paths
│   ├── logging.py           # JSONL moderation decision logging
│   └── text.py              # Fast shared preprocessing and vectorization
├── artifacts/               # Generated model/tokenizer/metadata files
├── data/                    # Local datasets and GloVe files
├── logs/                    # Moderation decision and moderator feedback logs
├── Procfile                 # Render-compatible web command
├── requirements.txt
└── runtime.txt
```

## Architecture

```text
User Input
  -> FastAPI /predict
  -> cached tokenizer + cleaning + pad/truncate
  -> cached attention-based moderation model
  -> rule-based decision engine
  -> structured moderation response
```

The moderation model and tokenizer are loaded once in FastAPI lifespan startup. The service performs a warm-up inference after loading so first user traffic avoids TensorFlow graph initialization cost. If artifacts are missing on a cold free-tier deployment, `/health` returns a degraded state and moderation endpoints return a clear `503` instead of crashing the container.

## System Capabilities

- Real-time comment stream that continuously sends comments through the moderation pipeline.
- Policy-aware moderation decisions: `Blocked`, `Warning`, and `Allowed`.
- Safety override mechanism for explicit high-risk threat language.
- Human-in-the-loop moderation dashboard with pending, approved, and rejected review states.
- Dataset-based evaluation snapshot for precision, recall, F1 score, false positives, and false negatives.
- Attention-based evidence display through important tokens in the Model Insights section.

## Moderation Model Design

- Embeddings: pretrained `glove.6B.100d.txt` only.
- Sequence length: default `100`, configurable for experiments.
- LSTM units: default `96`, kept below the required `128` limit.
- Moderation model output: six sigmoid scores for `toxic`, `severe_toxic`, `obscene`, `threat`, `insult`, `identity_hate`.
- Loss: binary crossentropy.
- Attention: single-vector additive attention over LSTM hidden states.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Download:

- Jigsaw Toxic Comment training CSV with columns `comment_text,toxic,severe_toxic,obscene,threat,insult,identity_hate`.
- `glove.6B.100d.txt` from the official GloVe 6B release.

Public sources used for this workspace:

- Jigsaw train CSV: `https://huggingface.co/datasets/thesofakillers/jigsaw-toxic-comment-classification-challenge`
- GloVe 100d mirror: `https://huggingface.co/datasets/SLU-CSCI4750/glove.6B.100d.txt`
- Official GloVe project: `https://nlp.stanford.edu/projects/glove/`

Place them under `data/`, for example:

```text
data/train.csv
data/glove.6B.100d.txt
```

Validate the files before training:

```powershell
python -m utils.validate_inputs --train-csv data/train.csv --glove-path data/glove.6B.100d.txt
```

## Train

Train the production attention model:

```powershell
python -m model.train --train-csv data/train.csv --glove-path data/glove.6B.100d.txt --model-type attention --max-len 100
```

This writes:

- `artifacts/toxic_lstm_attention.keras`
- `artifacts/tokenizer.pkl`
- `artifacts/metadata.json`

Train a baseline LSTM for comparison:

```powershell
python -m model.train --train-csv data/train.csv --glove-path data/glove.6B.100d.txt --model-type lstm --output-model artifacts/toxic_lstm.keras
```

## Run API

```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Professional web UI:

```text
http://127.0.0.1:8000/ui
```

If you only want to smoke-test the API before downloading the real dataset and GloVe file, generate demo artifacts:

```powershell
python -m model.create_demo_artifacts
```

These demo artifacts use random embeddings and a tiny synthetic dataset. They are useful for API validation only, not for research metrics or production moderation.

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Moderation decision:

```powershell
curl -X POST http://127.0.0.1:8000/predict `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"You are an idiot and nobody wants you here.\"}"
```

Example moderation response:

```json
{
  "model_analysis": {
    "scores": {
    "toxic": 0.912345,
    "severe_toxic": 0.042118,
    "obscene": 0.337411,
    "threat": 0.006102,
    "insult": 0.775311,
    "identity_hate": 0.018442
    },
    "primary_label": "toxic"
  },
  "decision": {
    "action": "block",
    "policy_mode": "balanced",
    "context_mode": "general",
    "rule_applied": "Policy block threshold was crossed by threat score or by content_score with targeting."
  },
  "explanation": {
    "reason": "High content severity with individual targeting."
  },
  "system_info": {
    "latency_ms": 18.734
  }
}
```

Decision policy:

- safety override phrase detected: `block`, severity `critical`
- `threat > 0.6`: `block`
- `toxic > 0.5`: `warn`
- otherwise: `allow`

Safety override examples include:

- `I will hurt you`
- `I will kill you`
- `you should die`
- `go kill yourself`

## Evaluation

Measure API latency over 120 requests:

```powershell
python -m evaluation.benchmark_api --url http://127.0.0.1:8000/predict --requests 120 --concurrency 1
```

Measure concurrent throughput:

```powershell
python -m evaluation.benchmark_api --requests 200 --concurrency 4
```

Compare LSTM vs LSTM+Attention and sequence lengths:

```powershell
python -m evaluation.compare_models --train-csv data/train.csv --glove-path data/glove.6B.100d.txt --sequence-lengths 50 75 100 --epochs 2
```

Measure explainability overhead and enhanced decision behavior:

```powershell
python -m evaluation.explainability_impact --train-csv data/train.csv --sample-size 200
```

Compare model-only versus hybrid safety decisions:

```powershell
python -m evaluation.hybrid_safety_eval --train-csv data/train.csv --sample-size 200
```

Outputs include:

- macro F1-score
- micro F1-score
- latency per sample
- throughput in samples/sec
- explainability latency overhead
- raw vs enhanced decision accuracy
- review-rate for uncertain samples
- critical false negatives for model-only versus hybrid safety logic
- safety override correction count

## Logging

Each moderation decision is appended to `logs/moderation_decisions.jsonl`:

```json
{"timestamp":"2026-04-26T17:45:00.000000+00:00","input_text":"...","moderation_model_scores":{"toxic":0.91},"moderation_decision":"block"}
```

For production, avoid storing raw text if privacy policy disallows it. Replace `input_text` with a hash or redacted representation.

## Free-Tier Deployment

Render-compatible files are included:

- `Procfile`
- `runtime.txt`
- `requirements.txt`

Recommended Render settings:

- Environment: Python
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- Instance type: free CPU tier
- Health endpoint: `/health`

Artifact strategy:

1. Train locally or in a notebook.
2. Upload `artifacts/toxic_lstm_attention.keras`, `artifacts/tokenizer.pkl`, and `artifacts/metadata.json` with the deployment.
3. Keep `glove.6B.100d.txt` out of the deployed app. It is needed for training only.

Cold start behavior:

- TensorFlow import and model loading can take several seconds on free tier.
- FastAPI lifespan loads artifacts once and runs a warm-up moderation decision.
- Set `SKIP_WARMUP=1` only if startup time is more important than first-request latency.

CPU inference guidance:

- Keep `MAX_SEQUENCE_LENGTH <= 100`.
- Keep `LSTM_UNITS <= 128`.
- Use `tensorflow-cpu`.
- Use one worker on very small free-tier instances to avoid duplicate model memory.
- Benchmark after warm-up; target steady-state latency should be below `300 ms` for single requests on modest CPU.

## Research Notes

This implementation separates model accuracy from deployment behavior:

- `model/train.py` reports validation F1 and exports inference artifacts.
- `evaluation/compare_models.py` isolates architecture and sequence-length trade-offs.
- `evaluation/benchmark_api.py` measures end-to-end service latency, including HTTP, preprocessing, inference, decision rules, and logging.

For an IEEE-style paper, report:

- Dataset split and label imbalance.
- Embedding dimension and fixed sequence length.
- LSTM unit count and parameter count.
- Macro/micro F1 for each model variant.
- Mean, p95 latency after warm-up.
- Throughput under concurrency.
- Moderation action distribution under the rule engine.

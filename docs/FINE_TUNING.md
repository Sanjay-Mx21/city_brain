# Fine-Tuning Scaffold

The live application is wired to call an open-source base model through the
`OPEN_SOURCE_LLM_MODEL` setting. The trained model name `citybrain-mistral`
is kept in the project as the future fine-tuned target, but it is not the
default runtime model.

The report target is a QLoRA fine-tuned Mistral-7B-Instruct adapter for 19
Bengaluru civic organizations/categories.

## Dataset Format

Training examples should use JSONL:

```json
{"input":"Huge pothole near Koramangala 80 feet road","output":{"complaints":[{"category":"pothole","department":"BBMP","description":"Huge pothole near Koramangala 80 feet road","location_text":"Koramangala 80 feet road","severity":3,"confidence":0.95}]}}
```

## Current Files

- `backend/training/dataset_examples.jsonl`: starter examples.
- `backend/training/README.md`: dataset and training notes.

## Deployment Path

1. Expand the dataset to at least 1500 labelled complaint examples.
2. Fine-tune with QLoRA using Mistral-7B-Instruct.
3. Export or convert the adapter/model for Ollama or another open-source LLM runtime.
4. Create the trained model as `citybrain-mistral`.
5. Change `OPEN_SOURCE_LLM_MODEL=citybrain-mistral` only when you want to demo the trained model.

The app will keep working if Ollama is unavailable, but classification will fall back to a safe low-confidence route.

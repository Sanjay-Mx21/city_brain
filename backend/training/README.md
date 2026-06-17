# City Brain Fine-Tuning Data

This folder holds the project scaffold for the report's fine-tuned Mistral/QLoRA path.

Use `dataset_examples.jsonl` as the schema reference. Each row contains:

- `input`: raw citizen complaint text.
- `output.complaints`: one or more structured issue objects.
- `category`: one of the supported 19 civic categories.
- `department`: BBMP, BESCOM, BWSSB, BTP, BMTC, or GENERAL.
- `severity`: 1 to 5.

Do not commit private citizen data. Use anonymized or synthetic examples.

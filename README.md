# large-netlogo-pairs-dataset

## Setup with uv

Install uv if you don't have it already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Create and activate virtual environment:

```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
# .venv\Scripts\activate  # On Windows
```

Install dependencies:

```bash
uv pip install -e .
```

## Running the code

```bash
python3 dataset/models-library-parser.py
```

# [dataDM](https://github.com/approximatelabs/datadm) 😏💬📊

[![PyPI](https://img.shields.io/pypi/v/datadm)](https://pypi.org/project/datadm/)
[![tests](https://github.com/approximatelabs/datadm/actions/workflows/test-build-publish.yml/badge.svg)](https://github.com/approximatelabs/datadm/actions/workflows/test-build-publish.yml)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/approximatelabs/datadm/blob/main/notebooks/datadm.ipynb)
[![](https://dcbadge.vercel.app/api/server/kW9nBQErGe?compact=true&style=flat)](https://discord.gg/kW9nBQErGe)

![dataDM](datadm-header.png?raw=true)

DataDM is your private data assistant. A conversational interface for your data where you can load, clean, transform, and visualize without a single line of code. DataDM is open source and can be run entirely locally, keeping your juicy data secrets fully private. Slide into your data's DMs tonight.

## Demo

[ recorded demo video here ]

## Features
- [x] Persistent Juptyer kernel backend for data manipulation during conversation
- [x] Run entirely locally, keeping your data private
- [x] Natural language chat, visualizations/plots, and direct download of data assets
- [x] Easy to use docker-images for one-line deployment
- [x] Load multiple tables directly into the chat
- [x] Option to use OpenAI's GPT-3.5 or GPT-4 (requires API key)
- [ ] [WIP] GGML based mode (CPU only, no GPU required) [/WIP]

## Things you can ask DataDM
- [x] Load data from a URL
- [x] Clean data by removing duplicates, nulls, outliers, etc.
- [x] Join data from multiple tables into a single output table
- [x] Visualize data with plots and charts
- [x] Ask whatever you want to your very own private code-interpreter

## Quickstart

You can use docker, colab, or install locally.

### 1. Docker to run locally
```bash
docker run -e OPENAI_API_KEY={{YOUR_API_KEY_HERE}} -p 7860:7860 -it ghcr.io/approximatelabs/datadm:latest
```

For local-mode using StarChat model (requiring a CUDA device with at least 24GB of RAM)
```bash
docker run --gpus all -p 7860:7860 -it ghcr.io/approximatelabs/datadm:0.1.0-cuda
```

### 2. Colab to run in the cloud
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/approximatelabs/datadm/blob/main/notebooks/datadm.ipynb)


### 3. Install and Run

For local-data, cloud-model mode (no GPU required) - requires an OpenAI API key
```bash
$ pip install datadm
$ datadm
```

For local-mode using StarChat model (requiring a CUDA device with at least 24GB of RAM)
```bash
$ pip install "datadm[cuda]"
$ datadm
```

## Special Thanks

* [starchat-alpha](https://huggingface.co/HuggingFaceH4/starchat-alpha) ([starcoder](https://github.com/bigcode-project/starcoder) with [databricks-dolly](https://huggingface.co/datasets/databricks/databricks-dolly-15k) and [OpenAssistant/oasst1](https://huggingface.co/datasets/OpenAssistant/oasst1))
* [Guidance](https://github.com/microsoft/guidance)
* [HuggingFace](https://huggingface.co/)
* [OpenAI](https://openai.com/)

## Contributions

Contributions are welcome! Feel free to submit a PR or open an issue.

FROM python:3.10.11-bullseye

RUN mkdir /datadm
WORKDIR /datadm

COPY README.md /datadm
COPY pyproject.toml /datadm
COPY datadm/ /datadm/datadm

RUN SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 pip install -e .

CMD ["datadm"]
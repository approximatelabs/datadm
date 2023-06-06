FROM python:3.10.11-bullseye

RUN pip install -U datadm

CMD ["datadm"]
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

RUN pip install -U datadm

CMD ["datadm"]
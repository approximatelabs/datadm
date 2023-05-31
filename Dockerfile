FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

# TODO: actually copy in the folder and build it
# TODO: publish this image to dockerhub (or something) and add to CI
RUN pip install datadm

CMD ["datadm"]
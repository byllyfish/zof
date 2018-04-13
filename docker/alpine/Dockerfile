FROM byllyfish/oftr:v0.47.0-alpine3.6

MAINTAINER William W. Fisher "william.w.fisher@gmail.com"

RUN set -ex \
    && apk add --no-cache git python3 \
    && python3 -m ensurepip \
    && pip3 install git+https://github.com/byllyfish/zof.git \
    && rm -r /root/.cache \
    && apk del git

EXPOSE 6653

CMD ["python3", "-m", "zof.demo.layer2"]

FROM ubuntu:16.04

RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys FFBE06FBB4EDC679174DD2CCD5AA2ED445128570 \
    && echo "deb http://ppa.launchpad.net/byllyfish/oftr/ubuntu xenial main" >> /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        curl \
        oftr \
        python3 \
        python3-pip \
        python3-setuptools \
    && rm -rf /var/lib/apt/lists/* \
    && cd /root \
    && curl -L https://github.com/byllyfish/pylibofp/archive/master.tar.gz | tar -xvz \
    && mv pylibofp-master pylibofp \
    && pip3 install ./pylibofp

EXPOSE 6653

CMD ["python3", "-m", "pylibofp.demo.layer2"]

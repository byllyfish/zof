FROM ubuntu:16.04

RUN set -ex
    && buildDeps=' \
        git \
    ' \
    && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys FFBE06FBB4EDC679174DD2CCD5AA2ED445128570 \
    && echo "deb http://ppa.launchpad.net/byllyfish/oftr/ubuntu xenial main" >> /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        $buildDeps \
        oftr \
        python3 \
        python3-pip \
        python3-setuptools \
    && pip3 install git+https://github.com/byllyfish/ofp_app.git \
    && apt-get purge -y --auto-remove $buildDeps \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 6653

CMD ["python3", "-m", "ofp_app.demo.layer2"]

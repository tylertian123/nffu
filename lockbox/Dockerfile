# Credits to @mincrmatt12

# shamelessly ripped off from the geckdriver image; not extended to avoid having to replicate all the purging crap
FROM debian:buster-slim AS firefox

ARG firefox_ver=83.0
ARG geckodriver_ver=0.28.0

ADD https://ftp.mozilla.org/pub/firefox/releases/${firefox_ver}/linux-x86_64/en-GB/firefox-${firefox_ver}.tar.bz2 /tmp/firefox.tar.bz2
ADD https://github.com/mozilla/geckodriver/releases/download/v${geckodriver_ver}/geckodriver-v${geckodriver_ver}-linux64.tar.gz /tmp/geckodriver.tar.gz

RUN apt-get update \
 && apt-get install -y --no-install-recommends --no-install-suggests \
            ca-certificates \
 && update-ca-certificates \
    \
 && apt-get install -y bzip2 tar \
 # Download and install Firefox
 && tar -xjf /tmp/firefox.tar.bz2 -C /tmp/ \
 && mv /tmp/firefox /opt/firefox \
    \
 # Download and install geckodriver
 && tar -xzf /tmp/geckodriver.tar.gz -C /tmp/ \
 && chmod +x /tmp/geckodriver \
 && mv /tmp/geckodriver /usr/local/bin


# Setup python dependencies + image
FROM debian:buster-slim AS py-compile

# install python deps
RUN apt-get update \
  && apt-get install -y --no-install-recommends --no-install-suggests \
	python3 python3-venv python3-pip python3-dev build-essential gcc

# create a venv 
RUN python3 -m venv /opt/venv
ENV PATH "/opt/venv/bin:$PATH"

WORKDIR /build

# install deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# install package
COPY setup.py .
COPY lockbox/ .
RUN pip install .


# Actually installs everything necessary. Starts with firefox
FROM debian:buster-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends --no-install-suggests \
            ca-certificates \
 && update-ca-certificates \
    \
 # Install dependencies for Firefox
 && apt-get install -y --no-install-recommends --no-install-suggests \
            `apt-cache depends firefox-esr | awk '/Depends:/{print$2}'` \
            # additional 'firefox-esl' dependencies which is not in 'depends' list
            libxt6 \
			# python
			python3 \
    \
 && rm -rf /var/lib/apt/lists/* \
           /tmp/*

# copy in firefox
COPY --from=firefox /opt/firefox /opt/firefox
COPY --from=firefox /usr/local/bin/geckodriver /usr/local/bin/geckodriver

# make sure local time is used correctly
ENV TZ America/Toronto

# copy in package
COPY --from=py-compile /opt/venv /opt/venv

# activate venv
ENV PATH "/opt/venv/bin:$PATH"

# set entrypoint
CMD ["lockbox"]

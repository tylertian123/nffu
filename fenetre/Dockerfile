# build the yarn resources

FROM node AS websrc-build

WORKDIR /opt/build

COPY package.json yarn.lock ./

RUN yarn install

COPY webpack.config.js .babelrc ./
COPY websrc/ ./websrc

RUN mkdir fenetre && mkdir fenetre/static && yarn run build

# build the thingies
FROM debian:buster-slim AS py-build

RUN apt-get update \
 && apt-get install -y --no-install-recommends --no-install-suggests \
            ca-certificates \
 && update-ca-certificates \
 && apt-get install -y python3 python3-venv python3-pip python3-dev build-essential gcc

RUN python3 -m venv /opt/venv
ENV PATH "/opt/venv/bin:$PATH"

WORKDIR /opt/build

# install deps
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY setup.py MANIFEST.in ./
COPY fenetre/ ./fenetre
COPY --from=websrc-build /opt/build/fenetre/static ./fenetre/static

RUN pip install .

FROM debian:buster-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends --no-install-suggests \
            ca-certificates \
 && update-ca-certificates \
 && apt-get install -y python3

COPY --from=py-build /opt/venv /opt/venv
ENV PATH "/opt/venv/bin:$PATH"
ENV QUART_APP "fenetre.app:create_app()"

CMD ["quart", "run", "-h", "0.0.0.0", "-p", "8080"]

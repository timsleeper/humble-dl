FROM python:3.12-slim

ARG VERSION
RUN pip install --no-cache-dir "humble-dl${VERSION:+==$VERSION}"

WORKDIR /library
ENTRYPOINT ["hbd"]

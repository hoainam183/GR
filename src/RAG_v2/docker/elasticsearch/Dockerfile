ARG ES_VERSION=8.7.0

FROM elasticsearch:${ES_VERSION} AS coccoc-builder

USER root
ENV JAVA_HOME=/usr/share/elasticsearch/jdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN if command -v apt-get >/dev/null 2>&1; then \
        apt-get update \
        && apt-get install -y --no-install-recommends \
            cmake \
            g++ \
            gcc \
            git \
            gzip \
            make \
            pkg-config \
            tar \
        && rm -rf /var/lib/apt/lists/*; \
    elif command -v microdnf >/dev/null 2>&1; then \
        microdnf install -y --nodocs \
            cmake \
            gcc \
            gcc-c++ \
            git \
            gzip \
            make \
            pkgconf-pkg-config \
            tar \
            which \
        && microdnf clean all; \
    elif command -v yum >/dev/null 2>&1; then \
        yum install -y \
            cmake \
            gcc \
            gcc-c++ \
            git \
            gzip \
            make \
            pkgconf-pkg-config \
            tar \
            which \
        && yum clean all; \
    else \
        echo "No supported package manager found" >&2; \
        exit 1; \
    fi

WORKDIR /tmp
RUN git clone --depth 1 https://github.com/duydo/coccoc-tokenizer.git \
    && mkdir coccoc-tokenizer/build

WORKDIR /tmp/coccoc-tokenizer/build
RUN cmake -DJAVA_HOME="${JAVA_HOME}" -DBUILD_JAVA=1 .. \
    && make install

FROM elasticsearch:${ES_VERSION}

ARG ES_VERSION=8.7.0
ARG VI_ANALYSIS_PLUGIN_URL=https://github.com/duydo/elasticsearch-analysis-vietnamese/releases/download/v8.7.0/elasticsearch-analysis-vietnamese-8.7.0.zip
ARG COCCOC_INSTALL_PATH=/usr/local
ARG COCCOC_DICT_PATH=${COCCOC_INSTALL_PATH}/share/tokenizer/dicts

USER root
COPY --from=coccoc-builder ${COCCOC_INSTALL_PATH}/lib/libcoccoc_tokenizer_jni.so /usr/lib/libcoccoc_tokenizer_jni.so
COPY --from=coccoc-builder ${COCCOC_DICT_PATH} ${COCCOC_DICT_PATH}

RUN /usr/share/elasticsearch/bin/elasticsearch-plugin install --batch "${VI_ANALYSIS_PLUGIN_URL}"

USER elasticsearch

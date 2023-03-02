FROM public.ecr.aws/lambda/python:3.7 AS cli_deps

COPY requirements-cli.txt requirements-cli.txt
RUN mkdir -p /opt/app/cli \
    && pip3 install --requirement requirements-cli.txt --target /opt/app/cli \
    && rm -rf /root/.cache/pip

FROM amazonlinux:2

# Set up working directories
RUN mkdir -p \
    /opt/app \
    /opt/app/build \
    /opt/app/bin \
    /opt/app/python_deps \
    /opt/app/cli

# Install packages
RUN yum update -y \
    && amazon-linux-extras install epel -y \
    && yum install -y \
      cpio \
      yum-utils \
      tar.x86_64 \
      gzip \
      zip \
      python3-pip \
      shadow-utils.x86_64 \
    && yum clean all \
    && rm -rf /var/cache/yum

# Download libraries we need to run in lambda
WORKDIR /tmp
RUN yumdownloader -x \*i686 --archlist=x86_64 \
      clamav \
      clamav-lib \
      clamav-update \
      clamav-scanner-systemd \
      elfutils-libs \
      json-c \
      lz4 \
      pcre2 \
      systemd-libs \
      libtool-ltdl \
      libxml2 \
      bzip2-libs \
      xz-libs \
      libprelude \
      gnutls \
      nettle \
    && rpm2cpio clamav-0*.rpm | cpio -vimd \
    && rpm2cpio clamav-lib*.rpm | cpio -vimd \
    && rpm2cpio clamav-update*.rpm | cpio -vimd \
    && rpm2cpio json-c*.rpm | cpio -vimd \
    && rpm2cpio pcre*.rpm | cpio -vimd \
    && rpm2cpio libtool-ltdl*.rpm | cpio -vimd \
    && rpm2cpio libxml2*.rpm | cpio -vimd \
    && rpm2cpio bzip2-libs*.rpm | cpio -vimd \
    && rpm2cpio xz-libs*.rpm | cpio -vimd \
    && rpm2cpio libprelude*.rpm | cpio -vimd \
    && rpm2cpio gnutls*.rpm | cpio -vimd \
    && rpm2cpio nettle*.rpm | cpio -vimd \
    && rpm2cpio clamd-0*.rpm | cpio -idmv \
    && rpm2cpio elfutils-libs*.rpm | cpio -idmv \
    && rpm2cpio lz4*.rpm | cpio -idmv \
    && rpm2cpio systemd-libs*.rpm | cpio -idmv \
    && cp -r \
      /tmp/usr/bin/clamdscan \
      /tmp/usr/sbin/clamd \
      /tmp/usr/bin/freshclam \
      /tmp/usr/lib64/* \
      /usr/lib64/libpcre.so* \
      /opt/app/bin/ \
    && rm -rf /tmp/usr

# Fix the freshclam.conf settings
RUN echo "DatabaseMirror database.clamav.net" > /opt/app/bin/freshclam.conf \
    && echo "CompressLocalDatabase yes" >> /opt/app/bin/freshclam.conf \
    && echo "ScriptedUpdates no" >> /opt/app/bin/freshclam.conf \
    && echo "DatabaseDirectory /var/lib/clamav" >> /opt/app/bin/freshclam.conf
# clamd conf with hardened configs to avoid false positives
RUN echo "DatabaseDirectory /tmp/clamav_defs" > /opt/app/bin/scan.conf \
    && echo "PidFile /tmp/clamd.pid" >> /opt/app/bin/scan.conf \
    && echo "LogFile /tmp/clamd.log" >> /opt/app/bin/scan.conf \
    && echo "LocalSocket /tmp/clamd.sock" >> /opt/app/bin/scan.conf \
    && echo "FixStaleSocket yes" >> /opt/app/bin/scan.conf \
    && echo "DetectPUA yes" >> /opt/app/bin/scan.conf \
    && echo "ExcludePUA PUA.Win.Packer" >> /opt/app/bin/scan.conf \
    && echo "ExcludePUA PUA.Win.Trojan.Packed" >> /opt/app/bin/scan.conf \
    && echo "ExcludePUA PUA.Win.Trojan.Molebox" >> /opt/app/bin/scan.conf \
    && echo "ExcludePUA PUA.Win.Packer.Upx" >> /opt/app/bin/scan.conf \
    && echo "ExcludePUA PUA.Doc.Packed" >> /opt/app/bin/scan.conf

RUN groupadd clamav \
    && useradd -g clamav -s /bin/false -c "Clam Antivirus" clamav \
    && useradd -g clamav -s /bin/false -c "Clam Antivirus" clamupdate

ENV LD_LIBRARY_PATH=/opt/app/bin
RUN ldconfig

# Copy in the lambda source
WORKDIR /opt/app
COPY requirements.txt /opt/app/requirements.txt

# This had --no-cache-dir, tracing through multiple tickets led to a problem in wheel
RUN pip3 install --requirement requirements.txt --target /opt/app/python_deps \
    && rm -rf /root/.cache/pip

# Copy fangfrisch CLI from lambda image
COPY --from=cli_deps /opt/app/cli /opt/app/cli

# Create the zip file
COPY ./*.py /opt/app/
COPY fangfrisch.conf /opt/app/fangfrisch.conf
RUN zip -r9 --exclude="*test*" /opt/app/build/lambda.zip *.py *.conf bin cli \
    && cd /opt/app/python_deps \
    && zip -r9 /opt/app/build/lambda.zip *

WORKDIR /opt/app

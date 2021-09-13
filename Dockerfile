FROM amazonlinux:2

# Set up working directories
RUN mkdir -p /opt/app
RUN mkdir -p /opt/app/build
RUN mkdir -p /opt/app/bin/

# Copy in the lambda source
WORKDIR /opt/app
COPY ./*.py /opt/app/
COPY requirements.txt /opt/app/requirements.txt

# Install packages
RUN yum update -y && \
    yum groupinstall -y "Development Tools" && \
    yum install -y yum-utils cpio zip unzip less wget && \
    yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm

# Install amazon-linux-extras in order to install python3.8
RUN yum install -y amazon-linux-extras && \
    amazon-linux-extras enable python3.8 && \
    yum -y install python3.8 && \
    python3.8 -m pip install -r requirements.txt && \
    # This had --no-cache-dir, tracing through multiple tickets led to a problem in wheel
    rm -rf /root/.cache/pip && \
    python3.8 -m pip install -U pytest

# Download libraries we need to run in lambda with python3.8
WORKDIR /tmp
RUN wget https://www.clamav.net/downloads/production/clamav-0.104.0.linux.x86_64.rpm && \
    yumdownloader -x \*i686 --archlist=x86_64 \
          json-c pcre2 libprelude gnutls libtasn1 lib64nettle nettle \
          bzip2-libs libtool-ltdl libxml2 xz-libs

RUN \
    rpm2cpio clamav-0*.rpm | cpio -idmv && \
    rpm2cpio json-c*.rpm | cpio -idmv && \
    rpm2cpio pcre*.rpm | cpio -idmv && \
    rpm2cpio gnutls* | cpio -idmv && \
    rpm2cpio nettle* | cpio -idmv && \
    rpm2cpio lib* | cpio -idmv && \
    rpm2cpio *.rpm | cpio -idmv && \
    rpm2cpio libtasn1* | cpio -idmv && \
    rpm2cpio bzip2-libs*.rpm | cpio -idmv && \
    rpm2cpio libtool-ltdl*.rpm | cpio -idmv && \
    rpm2cpio libxml2*.rpm | cpio -idmv && \
    rpm2cpio xz-libs*.rpm | cpio -idmv

# Copy over the binaries and libraries
RUN cp /tmp/usr/lib64/* \
       /tmp/usr/local/bin/clamscan \
       /tmp/usr/local/bin/freshclam \
       /tmp/usr/local/lib64/libclam* \
       /opt/app/bin/

# Fix the freshclam.conf settings
RUN echo "DatabaseMirror database.clamav.net" > /opt/app/bin/freshclam.conf && \
    echo "CompressLocalDatabase yes" >> /opt/app/bin/freshclam.conf

# Create the zip file
WORKDIR /opt/app
RUN zip -r9 --exclude="*test*" /opt/app/build/lambda.zip *.py bin

# Change path to Python 3.8
WORKDIR /usr/local/lib/python3.8/site-packages
RUN zip -r9 /opt/app/build/lambda.zip *

WORKDIR /opt/app

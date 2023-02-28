FROM amazonlinux:2

# Set up working directories
RUN mkdir -p \
    /opt/app \
    /opt/app/build \
    /opt/app/bin \
    /opt/app/python_deps \
    /opt/app/cli

# Copy in the lambda source
WORKDIR /opt/app
COPY ./*.py /opt/app/
COPY requirements.txt /opt/app/requirements.txt

# Install packages
RUN yum update -y \
    && amazon-linux-extras install epel -y \
    && yum install -y cpio yum-utils tar.x86_64 gzip zip python3-pip shadow-utils.x86_64

# This had --no-cache-dir, tracing through multiple tickets led to a problem in wheel
RUN pip3 install --requirement requirements.txt --target /opt/app/python_deps \
    && rm -rf /root/.cache/pip

COPY requirements-cli.txt /opt/app/
RUN pip3 install --requirement requirements-cli.txt --target /opt/app/cli \
    && rm -rf /root/.cache/pip \
    && sed -i 's~/usr/bin/python3~/var/lang/bin/python3~g' \
        /opt/app/cli/bin/fangfrisch

# Download libraries we need to run in lambda
WORKDIR /tmp
RUN yumdownloader -x \*i686 --archlist=x86_64 \
    clamav \
    clamav-lib \
    clamav-update \
    json-c \
    pcre2 \
    libtool-ltdl \
    libxml2 \
    bzip2-libs \
    xz-libs \
    libprelude \
    gnutls \
    nettle
RUN rpm2cpio clamav-0*.rpm | cpio -vimd \
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
    && rpm2cpio nettle*.rpm | cpio -vimd


# Copy over the binaries and libraries
RUN cp /tmp/usr/bin/clamscan /tmp/usr/bin/freshclam /tmp/usr/lib64/* /usr/lib64/libpcre.so.1 /opt/app/bin/

# Fix the freshclam.conf settings
RUN echo "DatabaseMirror database.clamav.net" > /opt/app/bin/freshclam.conf \
    && echo "CompressLocalDatabase yes" >> /opt/app/bin/freshclam.conf \
    && echo "ScriptedUpdates no" >> /opt/app/bin/freshclam.conf \
    && echo "DatabaseDirectory /var/lib/clamav" >> /opt/app/bin/freshclam.conf \
    && echo "DetectPUA yes" >> /opt/app/bin/freshclam.conf \
    && echo "ExcludePUA PUA.Win.Packer" >> /opt/app/bin/freshclam.conf \
    && echo "ExcludePUA PUA.Win.Trojan.Packed" >> /opt/app/bin/freshclam.conf \
    && echo "ExcludePUA PUA.Win.Trojan.Molebox" >> /opt/app/bin/freshclam.conf \
    && echo "ExcludePUA PUA.Win.Packer.Upx" >> /opt/app/bin/freshclam.conf \
    && echo "ExcludePUA PUA.Doc.Packed" >> /opt/app/bin/freshclam.conf

RUN groupadd clamav \
    && useradd -g clamav -s /bin/false -c "Clam Antivirus" clamav \
    && useradd -g clamav -s /bin/false -c "Clam Antivirus" clamupdate

ENV LD_LIBRARY_PATH=/opt/app/bin
RUN ldconfig

# Create the zip file
COPY fangfrisch.conf /opt/app/fangfrisch.conf
RUN cd /opt/app \
    && zip -r9 --exclude="*test*" /opt/app/build/lambda.zip *.py *.conf bin cli \
    && cd /opt/app/python_deps \
    && zip -r9 /opt/app/build/lambda.zip *

WORKDIR /opt/app

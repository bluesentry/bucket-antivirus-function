FROM docker-upgrade.artifactory.build.upgrade.com/container-base:2.0.20200406.0-205

# Set up working directories
USER root
RUN mkdir /app
RUN chown -R upgrade /app
USER upgrade
RUN mkdir -p /app/build
RUN mkdir -p /app/bin


# Copy in the lambda source
WORKDIR /app
COPY ./*.py /app/
COPY requirements.txt /app/requirements.txt

# Install packages
USER root
RUN yum update -y
RUN yum install -y cpio python3-pip yum-utils zip unzip less
RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm

# This had --no-cache-dir, tracing through multiple tickets led to a problem in wheel
RUN pip3 install -r requirements.txt
RUN rm -rf /root/.cache/pip

# Download libraries we need to run in lambda
WORKDIR /tmp
RUN yumdownloader -x \*i686 --archlist=x86_64 clamav clamav-lib clamav-update json-c pcre2 libprelude gnutls libtasn1 nettle
RUN rpm2cpio clamav-0*.rpm | cpio -idmv
RUN rpm2cpio clamav-lib*.rpm | cpio -idmv
RUN rpm2cpio clamav-update*.rpm | cpio -idmv
RUN rpm2cpio json-c*.rpm | cpio -idmv
RUN rpm2cpio pcre*.rpm | cpio -idmv
RUN rpm2cpio libprelude*.rpm | cpio -idmv
RUN rpm2cpio gnutls*.rpm | cpio -idmv
RUN rpm2cpio libtasn1*.rpm | cpio -idmv
RUN rpm2cpio nettle*.rpm | cpio -idmv

# Copy over the binaries and libraries
RUN cp /tmp/usr/bin/clamscan /tmp/usr/bin/freshclam /tmp/usr/lib64/* /app/bin/

# Fix the freshclam.conf settings
RUN echo "DatabaseMirror database.clamav.net" > /app/bin/freshclam.conf
RUN echo "CompressLocalDatabase yes" >> /app/bin/freshclam.conf

# Create the zip file
WORKDIR /app
RUN zip -r9 --exclude="*test*" /app/build/lambda.zip *.py bin

WORKDIR /usr/local/lib/python3.7/site-packages
RUN zip -r9 /app/build/lambda.zip *

WORKDIR /app

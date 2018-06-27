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
RUN yum update -y
RUN yum install -y cpio python3-pip yum-utils zip unzip less
RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm

# This had --no-cache-dir, tracing through multiple tickets led to a problem in wheel
RUN pip3 install -r requirements.txt
RUN rm -rf /root/.cache/pip

# Download libraries we need to run in lambda
WORKDIR /tmp
RUN yumdownloader -x \*i686 --archlist=x86_64 clamav clamav-lib clamav-update json-c pcre2
RUN rpm2cpio clamav-0*.rpm | cpio -idmv
RUN rpm2cpio clamav-lib*.rpm | cpio -idmv
RUN rpm2cpio clamav-update*.rpm | cpio -idmv
RUN rpm2cpio json-c*.rpm | cpio -idmv
RUN rpm2cpio pcre*.rpm | cpio -idmv

# Copy over the binaries and libraries
RUN cp /tmp/usr/bin/clamscan /tmp/usr/bin/freshclam /tmp/usr/lib64/* /opt/app/bin/

# Fix the freshclam.conf settings
RUN echo "DatabaseMirror database.clamav.net" > /opt/app/bin/freshclam.conf
RUN echo "CompressLocalDatabase yes" >> /opt/app/bin/freshclam.conf

# Create the zip file
WORKDIR /opt/app
RUN zip -r9 --exclude="*test*" /opt/app/build/lambda.zip *.py bin

WORKDIR /usr/local/lib/python3.7/site-packages
RUN zip -r9 /opt/app/build/lambda.zip *

# AWS Lambda Python 3.8 runtime dependencies
RUN mkdir -p /opt/app/lib
WORKDIR /tmp
ENV PYTHON38_LIBS "binutils bzip2-libs libxml2 libprelude gnutls libtool-ltdl libcurl nettle libnghttp2 libidn2 libssh2 openldap libunistring cyrus-sasl-lib nss"
RUN for lib in $PYTHON38_LIBS; do \
	yumdownloader -x \*i686 --archlist=x86_64 $lib; \
	rpm2cpio $lib*.rpm | cpio -idmv; \
	done
RUN cp \
	/tmp/usr/lib64/libbfd*.so \
	/tmp/usr/lib64/libopcodes*.so \
	/tmp/usr/lib64/libbz2.so.1 \
	/tmp/usr/lib64/libxml2.so.2 \
	/tmp/usr/lib64/libprelude.so.28 \
	/tmp/usr/lib64/libgnutls.so.28 \
	/tmp/usr/lib64/libltdl.so.7 \
	/tmp/usr/lib64/libcurl.so.4 \
	/tmp/usr/lib64/libnettle.so.4 \
	/tmp/usr/lib64/libhogweed.so.2 \
	/tmp/usr/lib64/libnghttp2.so.14 \
	/tmp/usr/lib64/libidn2.so.0 \
	/tmp/usr/lib64/libssh2.so.1 \
	/tmp/usr/lib64/libldap-2.4.so.2 \
	/tmp/usr/lib64/liblber-2.4.so.2 \
	/tmp/usr/lib64/libunistring.so.0 \
	/tmp/usr/lib64/libsasl2.so.3 \
	/tmp/usr/lib64/libssl3.so \
	/tmp/usr/lib64/libsmime3.so \
	/tmp/usr/lib64/libnss3.so \
	/opt/app/lib/
RUN cp /tmp/usr/bin/ld.bfd /opt/app/bin/ld
WORKDIR /opt/app
RUN cp /opt/app/build/lambda.zip /opt/app/build/lambda-3.8.zip
RUN zip -r9 /opt/app/build/lambda-3.8.zip lib bin/ld

WORKDIR /opt/app

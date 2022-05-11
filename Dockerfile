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
RUN yum install -y cpio python3-pip yum-utils zip unzip less ghostscript
RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm

# copy the init files in from the yum install
RUN cp -r /usr/share/ghostscript /opt/app/bin/

# This had --no-cache-dir, tracing through multiple tickets led to a problem in wheel
RUN pip3 install -r requirements.txt
RUN rm -rf /root/.cache/pip

# Download libraries we need to run in lambda
WORKDIR /tmp
RUN yumdownloader -x \*i686 --archlist=x86_64 clamav clamav-lib clamav-update json-c pcre2 libprelude gnutls p11-kit libtasn1 lib64nettle nettle ghostscript libgs freetype libpng libidn libpaper openjpeg2
RUN rpm2cpio clamav-0*.rpm | cpio -idmv
RUN rpm2cpio clamav-lib*.rpm | cpio -idmv
RUN rpm2cpio clamav-update*.rpm | cpio -idmv
RUN rpm2cpio json-c*.rpm | cpio -idmv
RUN rpm2cpio pcre*.rpm | cpio -idmv
RUN rpm2cpio gnutls* | cpio -idmv
RUN rpm2cpio p11-kit* | cpio -idmv
RUN rpm2cpio nettle* | cpio -idmv
RUN rpm2cpio lib* | cpio -idmv
RUN rpm2cpio *.rpm | cpio -idmv
RUN rpm2cpio libprelude* | cpio -idmv
RUN rpm2cpio libtasn1* | cpio -idmv
RUN rpm2cpio ghostscript* | cpio -idmv
RUN rpm2cpio libgs* | cpio -idmv
RUN rpm2cpio freetype* | cpio -idmv
RUN rpm2cpio libpng* | cpio -idmv
RUN rpm2cpio libidn* | cpio -idmv
RUN rpm2cpio libpaper* | cpio -idmv
RUN rpm2cpio openjpeg2* | cpio -idmv

# Copy over the binaries and libraries
RUN cp -r /tmp/usr/bin/clamscan /tmp/usr/bin/freshclam /tmp/usr/bin/gs /tmp/usr/lib64/* /opt/app/bin/

# Fix the freshclam.conf settings
RUN echo "DatabaseMirror database.clamav.net" > /opt/app/bin/freshclam.conf
RUN echo "CompressLocalDatabase yes" >> /opt/app/bin/freshclam.conf

# Create the zip file
WORKDIR /opt/app
RUN zip -r9 --exclude="*test*" /opt/app/build/lambda.zip *.py bin

WORKDIR /usr/local/lib/python3.7/site-packages
RUN zip -r9 /opt/app/build/lambda.zip *

WORKDIR /opt/app

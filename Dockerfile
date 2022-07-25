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
RUN amazon-linux-extras install epel -y
RUN yum install -y cpio yum-utils tar.x86_64 gzip zip python3-pip

# This had --no-cache-dir, tracing through multiple tickets led to a problem in wheel
RUN pip3 install -r requirements.txt
RUN rm -rf /root/.cache/pip

# Download libraries we need to run in lambda
WORKDIR /tmp
RUN yumdownloader -x \*i686 --archlist=x86_64 clamav
RUN rpm2cpio clamav-0*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 clamav-lib
RUN rpm2cpio clamav-lib*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 clamav-update
RUN rpm2cpio clamav-update*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 json-c
RUN rpm2cpio json-c*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 pcre2
RUN rpm2cpio pcre*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 libtool-ltdl
RUN rpm2cpio libtool-ltdl*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 libxml2
RUN rpm2cpio libxml2*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 bzip2-libs
RUN rpm2cpio bzip2-libs*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 xz-libs
RUN rpm2cpio xz-libs*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 libprelude
RUN rpm2cpio libprelude*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 gnutls
RUN rpm2cpio gnutls*.rpm | cpio -vimd

RUN yumdownloader -x \*i686 --archlist=x86_64 nettle
RUN rpm2cpio nettle*.rpm | cpio -vimd


# Copy over the binaries and libraries
RUN cp /tmp/usr/bin/clamscan /tmp/usr/bin/freshclam /tmp/usr/lib64/* /usr/lib64/libpcre.so.1 /opt/app/bin/

# Fix the freshclam.conf settings
RUN echo "DatabaseMirror database.clamav.net" > /opt/app/bin/freshclam.conf
RUN echo "CompressLocalDatabase yes" >> /opt/app/bin/freshclam.conf
RUN echo "ScriptedUpdates no" >> /opt/app/bin/freshclam.conf
RUN echo "DatabaseDirectory /var/lib/clamav" >> /opt/app/bin/freshclam.conf

RUN yum install shadow-utils.x86_64 -y

RUN groupadd clamav
RUN useradd -g clamav -s /bin/false -c "Clam Antivirus" clamav
RUN useradd -g clamav -s /bin/false -c "Clam Antivirus" clamupdate

ENV LD_LIBRARY_PATH=/opt/app/bin
RUN ldconfig

# Create the zip file
WORKDIR /opt/app
RUN zip -r9 --exclude="*test*" /opt/app/build/lambda.zip *.py bin

WORKDIR /usr/local/lib/python3.7/site-packages
RUN zip -r9 /opt/app/build/lambda.zip *

WORKDIR /opt/app

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
    amazon-linux-extras install epel -y && \
    yum install -y cpio yum-utils tar gzip zip python3-pip shadow-utils && \
    pip3 install -r requirements.txt && \
    rm -rf /root/.cache/pip

# Download libraries we need to run in lambda
WORKDIR /tmp
RUN yumdownloader -x \*i686 --archlist=x86_64,aarch64 \
        clamav clamav-lib clamav-update json-c \
        pcre2 libtool-ltdl libxml2 bzip2-libs \
        xz-libs libprelude gnutls nettle libcurl \
        libnghttp2 libidn2 libssh2 openldap \
        libunistring cyrus-sasl-lib nss pcre

RUN rpm2cpio clamav-0*.rpm | cpio -vimd && \
    rpm2cpio clamav-lib*.rpm | cpio -vimd && \
    rpm2cpio clamav-update*.rpm | cpio -vimd && \
    rpm2cpio json-c*.rpm | cpio -vimd && \
    rpm2cpio pcre*.rpm | cpio -vimd && \
    rpm2cpio libtool-ltdl*.rpm | cpio -vimd && \
    rpm2cpio libxml2*.rpm | cpio -vimd && \
    rpm2cpio bzip2-libs*.rpm | cpio -vimd && \
    rpm2cpio xz-libs*.rpm | cpio -vimd && \
    rpm2cpio libprelude*.rpm | cpio -vimd && \
    rpm2cpio gnutls*.rpm | cpio -vimd && \
    rpm2cpio nettle*.rpm | cpio -vimd && \
    rpm2cpio libcurl*.rpm | cpio -vimd && \
    rpm2cpio libnghttp2*.rpm | cpio -vimd && \
    rpm2cpio libidn2*.rpm | cpio -vimd && \
    rpm2cpio libssh2*.rpm | cpio -vimd && \
    rpm2cpio openldap*.rpm | cpio -vimd && \
    rpm2cpio libunistring*.rpm | cpio -vimd && \
    rpm2cpio cyrus-sasl-lib-2*.rpm | cpio -vimd && \
    rpm2cpio nss*.rpm | cpio -vimd && \
    rpm2cpio pcre*.rpm | cpio -vimd

# Copy over the binaries and libraries
RUN cp -rf /tmp/usr/bin/clamscan \
       /tmp/usr/bin/freshclam \
       /tmp/usr/lib64/* \
#       /usr/lib64/libpcre.so.1 \
       /opt/app/bin/

# Fix the freshclam.conf settings
RUN echo "DatabaseMirror database.clamav.net" > /opt/app/bin/freshclam.conf && \
    echo "CompressLocalDatabase yes" >> /opt/app/bin/freshclam.conf && \
    echo "ScriptedUpdates no" >> /opt/app/bin/freshclam.conf && \
    echo "DatabaseDirectory /var/lib/clamav" >> /opt/app/bin/freshclam.conf

RUN groupadd clamav
RUN useradd -g clamav -s /bin/false -c "Clam Antivirus" clamav
RUN useradd -g clamav -s /bin/false -c "Clam Antivirus" clamupdate

ENV LD_LIBRARY_PATH=/opt/app/bin
RUN ldconfig

# Create the zip file
WORKDIR /opt/app
RUN zip -r9 --exclude="*test*" /opt/app/build/anti-virus.zip *.py bin

WORKDIR /usr/local/lib/python3.7/site-packages
RUN zip -r9 /opt/app/build/anti-virus.zip *

WORKDIR /opt/app

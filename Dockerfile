FROM amazonlinux:2

ARG clamav_version=0.103.3

RUN amazon-linux-extras install -y python3.8
RUN ln -f /usr/bin/python3.8 /usr/bin/python3 && ln -f /usr/bin/pip3.8 /usr/bin/pip3

# Install packages
RUN yum update -y
RUN yum install -y cpio yum-utils zip unzip less libcurl-devel binutils openssl openssl-devel wget tar && yum groupinstall -y "Development Tools"

# Set up working directories
RUN mkdir -p /var/task/bin/

RUN wget https://github.com/curl/curl/releases/download/curl-7_76_1/curl-7.76.1.tar.bz2 && tar xvfj curl-7.76.1.tar.bz2
RUN pushd curl-7.76.1 && ./configure --prefix=/var/task --disable-shared && make install && popd
RUN wget https://www.clamav.net/downloads/production/clamav-${clamav_version}.tar.gz && tar xvfz clamav-${clamav_version}.tar.gz
RUN pushd clamav-${clamav_version} && ./configure --enable-static=yes --enable-shared=no --disable-unrar --with-libcurl=/var/task/ --prefix=/var/task && make install && popd

# This had --no-cache-dir, tracing through multiple tickets led to a problem in wheel
WORKDIR /var/task
COPY requirements.txt /var/task/requirements.txt
RUN pip3 install -r requirements.txt
RUN rm -rf /root/.cache/pip

# Fix the freshclam.conf settings
RUN echo "DatabaseMirror database.clamav.net" > /var/task/bin/freshclam.conf
RUN echo "CompressLocalDatabase yes" >> /var/task/bin/freshclam.conf

COPY ./*.py /var/task/

# Copy in the lambda source
# Create the zip file
RUN zip -r9 --exclude="*test*" /lambda.zip *.py bin

WORKDIR /usr/local/lib/python3.8/site-packages
RUN zip -r9 /lambda.zip *

RUN mv /lambda.zip /var/task/
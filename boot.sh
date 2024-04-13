# Create and activate virtual Env
sudo apt-get update
sudo apt install -y postgresql
sudo apt install -y redis
/opt/bitnami/python/bin/python3.11 -m venv /home/bitnami/.venv

# Placeholder for vars.
touch /home/bitnami/vars.py

# Create git dir
mkdir /home/bitnami/bookbuilder.git
mkdir /home/bitnami/bookbuilder
cd /home/bitnami/bookbuilder.git
git config --global init.defaultBranch main
git init --bare
cd /home/bitnami

# Create post receive
touch /home/bitnami/bookbuilder.git/hooks/post-receive
cat > /home/bitnami/bookbuilder.git/hooks/post-receive <<- "EOF"
#!/bin/bash
cd ~
git --work-tree="bookbuilder" --git-dir="bookbuilder.git" checkout -f main
source .venv/bin/activate
cd bookbuilder
pip install -r requirements.txt
deactivate
sudo /opt/bitnami/ctlscript.sh restart apache
EOF
chmod +x /home/bitnami/bookbuilder.git/hooks/post-receive

# Apache Server
touch /opt/bitnami/apache/conf/vhosts/bookbuilder-http-vhost.conf
cat > /opt/bitnami/apache/conf/vhosts/bookbuilder-http-vhost.conf <<- "EOF"
<IfDefine !IS_bookbuilder_LOADED>
    Define IS_bookbuilder_LOADED
    WSGIDaemonProcess bookbuilder python-home=/home/bitnami/.venv python-path=/home/bitnami/bookbuilder
</IfDefine>
<VirtualHost 127.0.0.1:80 _default_:80>
ServerAlias *
WSGIProcessGroup bookbuilder
WSGIScriptAlias / /home/bitnami/bookbuilder/bookbuilder/wsgi.py
<Directory /home/bitnami/bookbuilder/bookbuilder>
    <Files wsgi.py>
    Require all granted
    </Files>
</Directory>
</VirtualHost>
EOF

touch /opt/bitnami/apache/conf/vhosts/bookbuilder-https-vhost.conf
cat > /opt/bitnami/apache/conf/vhosts/bookbuilder-https-vhost.conf <<- "EOF"
<IfDefine !IS_bookbuilder_LOADED>
    Define IS_bookbuilder_LOADED
    WSGIDaemonProcess bookbuilder python-home=/home/bitnami/.venv python-path=/home/bitnami/bookbuilder
</IfDefine>
<VirtualHost 127.0.0.1:443 _default_:443>
ServerAlias *
SSLEngine on
SSLCertificateFile "/opt/bitnami/apache/conf/bitnami/certs/server.crt"
SSLCertificateKeyFile "/opt/bitnami/apache/conf/bitnami/certs/server.key"
WSGIProcessGroup bookbuilder
WSGIScriptAlias / /home/bitnami/bookbuilder/bookbuilder/wsgi.py
<Directory /home/bitnami/bookbuilder/bookbuilder>
    <Files wsgi.py>
    Require all granted
    </Files>
</Directory>
</VirtualHost>
EOF

sudo chown -R bitnami /home/bitnami/.venv
sudo chown -R bitnami /home/bitnami/bookbuilder
sudo chown -R bitnami /home/bitnami/bookbuilder.git
# celery -A bookbuilder worker -l INFO


touch /etc/systemd/system/celeryd.service
cat > /etc/systemd/system/celeryd.service <<- "EOF"
[Unit]
Description=Celery Service
After=network.target

[Service]
Type=forking
User=bitnami
Group=bitnami
EnvironmentFile=/etc/default/celeryd
WorkingDirectory=/home/bitnami/bookbuilder
ExecStart=/bin/sh -c '${CELERY_BIN} multi start ${CELERYD_NODES} -A ${CELERY_APP} --pidfile=${CELERYD_PID_FILE} --logfile=${CELERYD_LOG_FILE} --loglevel=${CELERYD_LOG_LEVEL} ${CELERYD_OPTS}'
ExecStop=/bin/sh -c '${CELERY_BIN} multi stopwait ${CELERYD_NODES} --pidfile=${CELERYD_PID_FILE}'
ExecReload=/bin/sh -c '${CELERY_BIN} multi restart ${CELERYD_NODES} -A ${CELERY_APP} --pidfile=${CELERYD_PID_FILE} --logfile=${CELERYD_LOG_FILE} --loglevel=${CELERYD_LOG_LEVEL} ${CELERYD_OPTS}'
Restart=always

[Install]
WantedBy=multi-user.target
EOF

touch /etc/default/celeryd
cat > /etc/default/celeryd <<- "EOF"
# The names of the workers. This example create one worker
CELERYD_NODES="worker1"

# The name of the Celery App, should be the same as the python file
# where the Celery tasks are defined
CELERY_APP="bookbuilder"

# Log and PID directories
CELERYD_LOG_FILE="/var/log/celery/%n%I.log"
CELERYD_PID_FILE="/var/run/celery/%n.pid"

# Log level
CELERYD_LOG_LEVEL=INFO

# Path to celery binary, that is in your virtual environment
CELERY_BIN=/home/bitnami/.venv/bin/celery
EOF

sudo mkdir /var/log/celery /var/run/celery
sudo chown bitnami:bitnami /var/log/celery /var/run/celery

sudo systemctl daemon-reload
sudo systemctl enable celeryd
sudo systemctl start celeryd


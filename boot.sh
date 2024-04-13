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


touch /etc/systemd/system/celery.service
cat > /etc/systemd/system/celery.service <<- "EOF"
[Unit]
Description=Celery Service
After=network.target

[Service]
Type=forking
User=celery
Group=celery
EnvironmentFile=/etc/conf.d/celery
WorkingDirectory=/opt/celery
ExecStart=/bin/sh -c '${CELERY_BIN} -A $CELERY_APP multi start $CELERYD_NODES \
    --pidfile=${CELERYD_PID_FILE} --logfile=${CELERYD_LOG_FILE} \
    --loglevel="${CELERYD_LOG_LEVEL}" $CELERYD_OPTS'
ExecStop=/bin/sh -c '${CELERY_BIN} multi stopwait $CELERYD_NODES \
    --pidfile=${CELERYD_PID_FILE} --logfile=${CELERYD_LOG_FILE} \
    --loglevel="${CELERYD_LOG_LEVEL}"'
ExecReload=/bin/sh -c '${CELERY_BIN} -A $CELERY_APP multi restart $CELERYD_NODES \
    --pidfile=${CELERYD_PID_FILE} --logfile=${CELERYD_LOG_FILE} \
    --loglevel="${CELERYD_LOG_LEVEL}" $CELERYD_OPTS'
Restart=always

[Install]
WantedBy=multi-user.target
EOF

touch /etc/conf.d/celery
cat > /etc/conf.d/celery <<- "EOF"
EOF
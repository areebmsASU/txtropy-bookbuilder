# Create and activate virtual Env
sudo apt-get update
sudo apt install -y python3.10-venv
sudo apt install -y postgresql
sudo apt install -y redis
cd /home/bitnami
python3 -m venv .venv
sudo chown -R bitnami .venv/

# Placeholder for vars.
touch vars.sh
chmod +x vars.sh

# Create git dir
mkdir bookbuilder.git
mkdir bookbuilder
sudo chown -R bitnami bookbuilder.git/
sudo chown -R bitnami bookbuilder/
cd bookbuilder.git
git config --global init.defaultBranch main
git init --bare

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
EOF
chmod +x /home/bitnami/bookbuilder.git/hooks/post-receive

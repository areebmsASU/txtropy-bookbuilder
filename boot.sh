# Create and activate virtual Env
sudo apt-get update
sudo apt install -y python3.10-venv
cd /home/ubuntu
python3 -m venv .venv

# Create git dir
mkdir bookbuilder.git
mkdir bookbuilder
cd bookbuilder.git
git config --global init.defaultBranch main
git init --bare

# Create post receive
touch /home/ubuntu/bookbuilder.git/hooks/post-receive
cat > /home/ubuntu/bookbuilder.git/hooks/post-receive <<- "EOF"
#!/bin/bash
git --work-tree="bookbuilder" --git-dir="bookbuilder.git" checkout -f main
cd ~
source .venv/bin/activate
cd bookbuilder
pip install requirements
deactivate
EOF
chmod +x /home/ubuntu/bookbuilder.git/hooks/post-receive

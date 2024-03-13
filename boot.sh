# Create and activate virtual Env
sudo apt-get update
sudo apt install -y python3.10-venv
sudo apt install postgresql
sudo apt install cron
cd /home/ubuntu
python3 -m venv .venv
sudo chown -R ubuntu .venv/

# Placeholder for vars.
touch vars.sh
chmod +x vars.sh


# Create git dir
mkdir bookbuilder.git
mkdir bookbuilder
sudo chown -R ubuntu bookbuilder.git/
sudo chown -R ubuntu bookbuilder/
cd bookbuilder.git
git config --global init.defaultBranch main
git init --bare

# Create post receive
touch /home/ubuntu/bookbuilder.git/hooks/post-receive
cat > /home/ubuntu/bookbuilder.git/hooks/post-receive <<- "EOF"
#!/bin/bash
cd ~
git --work-tree="bookbuilder" --git-dir="bookbuilder.git" checkout -f main
source .venv/bin/activate
cd bookbuilder
pip install -r requirements.txt
deactivate
EOF
chmod +x /home/ubuntu/bookbuilder.git/hooks/post-receive

touch /etc/cron.hourly/run_routine.sh
cat > /etc/cron.hourly/run_routine.sh <<- "EOF"
cd ~
source vars.sh
source .venv/bin/activate
cd bookbuilder
python manage.py scrape_book_data
echo “Routine completed at $(date)” >> $HOME/log.txt
EOF
chmod +x /etc/cron.hourly/run_routine.sh

#!/bin/bash
# Supervisor: keeps the packer running until it finishes naturally.
# If the process is killed (session teardown, OOM, reboot), it restarts and
# resumes from results/layout.json instead of starting over.

cd "$(dirname "$0")" || exit 1

mkdir -p results

while [ ! -f results/DONE ]; do
    echo "=== $(date '+%F %T') starting/resuming packer ===" >> results/run.log
    python3 -u main.py >> results/run.log 2>&1
    if [ -f results/DONE ]; then
        echo "=== $(date '+%F %T') finished ===" >> results/run.log
        break
    fi
    echo "=== $(date '+%F %T') process died, restarting in 5s ===" >> results/run.log
    sleep 5
done

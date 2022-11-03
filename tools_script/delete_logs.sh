#!/bin/bash

#
# The script to the backup logs ISS3.2.
# Modify by: Nuttapong Kaewnoi (nkaewnoi@celestica.com)

# set time
logs_rsync_name=$(date '+%Y-%m-%d')
delete_log=$(date -d "$1 days" '+%Y%m%d')

# set path
logs_path=/opt/Logs_Robot/archive/

# delete log 
if [ ! -z "$1" ]; then
    echo Delete records logs than $1 days. 
    for entry in "$logs_path"*
    do
        for date_logs in "$entry"/*
        do
            logs_name="$(basename "$date_logs")"
            num_logs="$(basename "$date_logs" | sed 's/-//g')"
            if [[ $delete_log -gt $num_logs ]]
                then
                    rm -rf $date_logs
                    echo -e "Delete logs $date_logs"
            fi
        done
    done
    end_timestamp=`date +"%Y%m%d%s"`

else
    echo -e "\e[93m./delete_logs.sh [days]\e[0m"
fi
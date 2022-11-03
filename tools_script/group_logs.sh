#!/bin/bash

#
# The script to the backup logs ISS3.2.
# Modify by: Nuttapong Kaewnoi (nkaewnoi@celestica.com)

# set path
old_path=/opt/Logs_Robot/archive/
logs_rsync=/opt/Logs_ISS/
tmp_path=/tmp/archive

# create tmp log
for entry in "$old_path"*
do
    date_logs="$(basename "$entry")"
    for path_log in "$entry"/*
    do
        file_name="$(basename "$path_log")"
        product_name="$( cut -d '_' -f 1 <<< "$file_name" )"
        tmp_logs_path=$tmp_path/$product_name/$date_logs

        echo $path_log

        mkdir -p "$tmp_logs_path" && cp "$path_log" "$tmp_logs_path"
    done
done

# rm -rf $old_path*
# rm -rf /opt/Logs_Robot/archive/*
# cp -r $tmp_path/* $old_path
# cp -r /tmp/archive/* /opt/Logs_Robot/archive/

echo "Done"
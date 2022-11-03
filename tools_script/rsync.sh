#!/bin/bash

#
# The script to the backup logs ISS3.2.
# Modify by: Nuttapong Kaewnoi (nkaewnoi@celestica.com)


# set server-log
ip=10.196.66.71
username=tdeadmin

# set time
start_timestamp=`date +"%Y%m%d%s"`
logs_rsync_name=`date +"%Y-%m-%d"`

# set path
src_path=/opt/Logs_Robot/archive/
dest_path=$username@$ip:/opt/Logs_Robot/archive/
logs_rsync=/opt/Logs_ISS

use_ip="-o StrictHostKeyChecking=no -l $username"

# rsync log
/usr/bin/rsync -avz --rsh="ssh $use_ip" $src_path  $dest_path

end_timestamp=`date +"%Y%m%d%s"`

different_time=$(( $end_timestamp - $start_timestamp ))

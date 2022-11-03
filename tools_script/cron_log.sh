#!/bin/bash

#
# The script to the backup logs ISS3.2.
# Modify by: Nuttapong Kaewnoi (nkaewnoi@celestica.com)

# set delete_date
delete_date=7

# set time
start_timestamp=`date +"%Y%m%d%s"`
logs_rsync_name=/opt/Logs_ISS/`date +"%Y-%m-%d"`-rsync.out

echo "Start rsync logs ********************************" >> $logs_rsync_name

/usr/local/bin/rsync.sh >> $logs_rsync_name

echo ""  >> $logs_rsync_name

sleep 10

echo "Start Delete logs *******************************" >> $logs_rsync_name

/usr/local/bin/delete_logs.sh $delete_date  >> $logs_rsync_name

end_timestamp=`date +"%Y%m%d%s"`

echo ""  >> $logs_rsync_name

different_time=$(( $end_timestamp - $start_timestamp ))
echo "runtime = $different_time" >> $logs_rsync_name


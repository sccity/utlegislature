#!/bin/bash
#0 */6 * * * /bin/bash /opt/utlegislature/app.sh > /dev/null 2>&1
python3=/usr/bin/python3

cd /opt/utlegislature

$python3 app.py bills
$python3 app.py billfiless
$python3 app.py analysis
$python3 app.py impact
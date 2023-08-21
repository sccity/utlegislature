#!/bin/bash

python="/usr/bin/python3"
working_directory="/opt/utbilldata"

$python "$working_directory/ut_bill_data.py"
$python "$working_directory/impact_rating.py"
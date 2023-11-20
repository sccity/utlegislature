#!/bin/bash

for year in {2016..2023}
do
    for session in GS S1 S2 S3 S4 S5 Y1 Y2 Y3 Y4 Y5
    do
        python3 app.py billfiles --year $year --session $session
    done
done

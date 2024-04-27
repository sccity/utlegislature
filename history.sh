#!/bin/bash

for year in {2016..2024}
do
    for session in GS S1 S2 S3 S4 S5 S6 Y1 Y2 Y3 Y4 Y5 VOS
    do
        python3 app.py billfiles --year $year --session $session
    done
done

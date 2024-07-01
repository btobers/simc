#!/bin/bash


ipfix=/Users/btober/Drive/work/nps_kennicott/kennicott_202405/radar/proc
pfix=/Users/btober/Drive/work/code/radar/simc/src/simc
opfix=/Users/btober/Drive/work/nps_kennicott/kennicott_202405/radar/proc/sim

for p in $ipfix/*.h5;
do
    echo $p
    python $pfix/main.py ../config/bsi_airipr.ini -n $p -o $opfix/
done
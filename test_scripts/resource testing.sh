##################################
##
## Service Account CLI Testing
## => ENVNAME represents a testing tenant rename
## => CLIPATH is that root path to the python CLI
## => OBJNAME is the object type being tested
##
##################################

CLIPATH=/Users/brendansapience/Documents/git/Twingate-CLI
ENVNAME=staging
OBJNAME=resource

cd ${CLIPATH}

echo "\nObject list"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} list"
echo $CMD
${CMD}

REMNETWORKID=`python3 ./tgcli.py -s ${ENVNAME} -f csv network list | grep -m 1 "API Test Network 2" | awk -F"," '{print $1}'`
RESID=`python3 ./tgcli.py -s ${ENVNAME} -f csv ${OBJNAME} create -a "10.0.0.5" -n "API Created Res2" -r ${REMNETWORKID} -t "RESTRICTED" -c "[[22-23],[443-443]]" | grep "API" | awk -F"," '{print $3}'`

echo "\nObject create"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} list"
echo $CMD
${CMD}

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i $RESID"
echo $CMD
${CMD}

echo "\nObject assign Remote Network"
REMNETWORKID2=`python3 ./tgcli.py -s ${ENVNAME} -f csv network list | grep -m 1 "API Test Network" | awk -F"," '{print $1}'`
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} assignNetwork -i $RESID -n ${REMNETWORKID2}"
echo $CMD
${CMD}

echo "\nObject delete"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} delete -i $RESID"
echo $CMD
${CMD}

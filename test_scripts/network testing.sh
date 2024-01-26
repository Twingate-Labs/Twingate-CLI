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
OBJNAME=network

cd ${CLIPATH}

echo "\nObject list"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} list"
echo $CMD
${CMD}

echo "\nGetting an Object ID"
OBJID=`python3 ./tgcli.py -s ${ENVNAME} -f csv ${OBJNAME} list | grep -m1 "API" | awk -F"," '{print $1}'`

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

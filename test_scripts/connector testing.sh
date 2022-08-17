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
OBJNAME=connector

cd ${CLIPATH}

echo "\nObject list"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} list"
echo $CMD
${CMD}

OBJID=`python3 ./tgcli.py -s ${ENVNAME} -f csv ${OBJNAME} list | grep -m1 "ALIVE" | awk -F"," '{print $1}'`
OBJCURRENTNAME=`python3 ./tgcli.py -s ${ENVNAME} -f csv ${OBJNAME} list | grep -m1 "ALIVE" | awk -F"," '{print $2}'`

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

echo "\nObject update"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} rename -i ${OBJID} -n NewConnName"
echo $CMD
${CMD}

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

echo "\nObject update"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} rename -i ${OBJID} -n ${OBJCURRENTNAME}"
echo $CMD
${CMD}

#echo "\nObject generate tokens"
#CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} generateTokens -i ${OBJID}"
#echo $CMD
#${CMD}
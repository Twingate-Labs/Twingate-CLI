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
OBJNAME=device

cd ${CLIPATH}

echo "\nDevice list"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} list"
echo $CMD
${CMD}

echo "\nGetting a device ID"
OBJID=`python3 ./tgcli.py -s ${ENVNAME} -f csv ${OBJNAME} list | grep -v "id,name" | awk -F"," '{print $1}'`

echo "\nDevice show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

echo "\nDevice update"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} updateTrust -i ${OBJID} -t False"
echo $CMD
${CMD}

echo "\nDevice show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

echo "\nDevice update"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} updateTrust -i ${OBJID} -t True"
echo $CMD
${CMD}

echo "\nDevice show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

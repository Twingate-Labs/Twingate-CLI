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
OBJNAME=group

cd ${CLIPATH}

echo "\nObject list"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} list"
echo $CMD
${CMD}

echo "\nObject create"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} create -g APICreatedGroup"
echo $CMD
${CMD}

echo "\nGetting an object ID"
OBJID=`python3 ./tgcli.py -s ${ENVNAME} -f csv ${OBJNAME} list | grep "APICreated" | awk -F"," '{print $1}'`

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

# create resource and get ID
echo "\ncreate Resource"
REMNETWORKID=`python3 ./tgcli.py -s ${ENVNAME} -f csv network list | grep "API Test" | head -n 1 | awk -F"," '{print $1}'`
echo ${ENVNAME}
echo "Remote Network ID: ${REMNETWORKID}"
RESID=`python3 ./tgcli.py -s ${ENVNAME} -f csv resource create -a "10.0.0.5" -n "API Created Res3" -r ${REMNETWORKID} -t "RESTRICTED" -c "[[22-23],[443-443]]" | grep "API" | awk -F"," '{print $3}'`
echo "Resource ID: ${RESID}"

# add RESOURCE
echo "\nadd Resource"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} addResources -g ${OBJID} -r ${RESID}"
echo $CMD
${CMD}

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

echo "\nremove Resource"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} removeResources -g ${OBJID} -r ${RESID}"
echo $CMD
${CMD}

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

CMD="python3 ./tgcli.py -s ${ENVNAME} -f df resource delete -i $RESID"
#echo $CMD
${CMD}

USERID=`python3 ./tgcli.py -s ${ENVNAME} -f csv user list | grep -v "id,first" -m1 | awk -F"," '{print $1}'`

echo "\nadd User"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} addUsers -g ${OBJID} -u ${USERID}"
echo $CMD
${CMD}

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

echo "\nremove User"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} removeUsers -g ${OBJID} -u ${USERID}"
echo $CMD
${CMD}

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

echo "\nObject delete"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} delete -i ${OBJID}"
echo $CMD
${CMD}

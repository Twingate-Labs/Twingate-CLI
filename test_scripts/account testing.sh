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
OBJNAME=account

# it makes sense to test SA Keys here as well since they only exist in the context of Service Accounts
OTHEROBJNAME=key

cd ${CLIPATH}

#Getting a Res ID
RESID=`python3 ./tgcli.py -s ${ENVNAME} -f csv resource list | grep -v -m1 "id,name" | awk -F"," '{print $1}'`

echo "\nObject create"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} create -n APIServiceAccount -r ${RESID}"
echo $CMD
${CMD}

#Getting the new account ID
OBJID=`python3 ./tgcli.py -s ${ENVNAME} -f csv ${OBJNAME} list | grep -m1 "APIServiceAccount" | awk -F"," '{print $1}'`

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

echo "\nRemove resource"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} removeResources -i ${OBJID} -r ${RESID}"
echo $CMD
${CMD}

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

echo "\nAdd resource"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} addResources -i ${OBJID} -r ${RESID}"
echo $CMD
${CMD}

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} show -i ${OBJID}"
echo $CMD
${CMD}

### Service Account Keys Testing
echo "\nSA Key create"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f csv ${OTHEROBJNAME} create -i ${OBJID} -n APICreatedKey -e 1"
echo ${CMD}
KEYID=`${CMD} | grep -v "ok,error" | awk -F"," '{print $3}'`
echo ${KEYID}

echo "\nObject show"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OTHEROBJNAME} show -i ${KEYID}"
echo $CMD
${CMD}

echo "\nObject rename"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OTHEROBJNAME} rename -i ${KEYID} -n APICreatedKeyNewName"
echo $CMD
${CMD}

echo "\nObject revoke"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OTHEROBJNAME} revoke -i ${KEYID}"
echo $CMD
${CMD}

echo "\nObject delete"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OTHEROBJNAME} delete -i ${KEYID}"
echo $CMD
${CMD}

### End of Service Account Key Testing

echo "\nObject delete"
CMD="python3 ./tgcli.py -s ${ENVNAME} -f df ${OBJNAME} delete -i ${OBJID}"
echo $CMD
${CMD}

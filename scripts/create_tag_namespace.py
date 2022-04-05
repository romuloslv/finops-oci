import oci
import requests

signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
identity = oci.identity.IdentityClient(config={}, signer=signer)

def MakeLog(msg):
    print (msg)

try:
    url = "http://169.254.169.254/opc/v1/instance/"
    data = requests.get(url).json()
except:
    MakeLog("This instance is not running on OCI or does not have Instance Principle permissions")
    exit()

MakeLog("Logged in as: {} @ {}".format("Principle login", data['canonicalRegionName']))

create_tag_namespace_response = identity.create_tag_namespace(
    oci.identity.models.CreateTagNamespaceDetails(
        compartment_id = data['compartmentId'],
        name = 'Periods',
        description = data['displayName'] + ' ' + data['state'] + ' in ' + data['canonicalRegionName']
    )
)

print('Created tag namespace: {}'.format(create_tag_namespace_response.data))
namespaceID = create_tag_namespace_response.data.id

keys = ["AnyDay", "WeekDay", "Weekend", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
print('\nCreated keys: {}\n'.format(keys))

for key in keys:
    create_tag = identity.create_tag(
        namespaceID,
        oci.identity.models.CreateTagDetails(
            name = key,
            description = "Schedule for {}".format(key)
        )
    )
    print('\nCreated tag: {}'.format(create_tag.data))
